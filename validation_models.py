#!/usr/bin/env python3
"""Pydantic models and validation helpers moved out of server.py.

Provides a factory `make_validate_params(nr_mgr)` which returns an async
`validate_params` function bound to the provided Nornir manager instance.
"""
import logging
from typing import Any, Dict, List, Optional, get_origin

from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger("nornir_mcp.validation")


# --- Pydantic Models for Input Validation ---
class DeviceNameModel(BaseModel):
    device_name: str = Field(
        ..., description="The unique device name as defined in the Nornir inventory."
    )


class GetConfigModel(DeviceNameModel):
    retrieve: str = Field(default="running")


class SendCommandModel(DeviceNameModel):
    command: Optional[str] = Field(None)
    commands: Optional[List[str]] = Field(None)


class BGPConfigModel(DeviceNameModel):
    group: str = Field(default="")
    neighbor: str = Field(default="")


class BGPNeighborsDetailModel(DeviceNameModel):
    neighbor_address: str = Field(default="")


class LLDPNeighborsDetailModel(DeviceNameModel):
    interface: str = Field(default="")


class NetworkInstancesModel(DeviceNameModel):
    name: str = Field(default="")


class PingModel(DeviceNameModel):
    destination: str
    source: str = ""
    ttl: int = 255
    timeout: int = 2
    size: int = 100
    count: int = 5
    vrf: str = ""
    source_interface: str = ""


class TracerouteModel(DeviceNameModel):
    destination: str
    source: str = ""
    ttl: int = 255
    timeout: int = 2
    vrf: str = ""


# --- Result Models ---
class PingProbe(BaseModel):
    ip_address: str
    rtt: float


class PingSuccess(BaseModel):
    probes_sent: int
    packet_loss: float
    rtt_min: float
    rtt_max: float
    rtt_avg: float
    rtt_stddev: float
    results: List[PingProbe]


class PingResultModel(BaseModel):
    success: Optional[PingSuccess] = None
    error: Optional[str] = None


class TracerouteHop(BaseModel):
    rtt: float
    ip_address: str
    host_name: Optional[str] = None


class TracerouteResultModel(BaseModel):
    success: Optional[Dict[str, TracerouteHop]] = None
    error: Optional[str] = None


# --- Helpers ---
def _example_from_model(cls: BaseModel) -> Dict[str, Any]:
    example: Dict[str, Any] = {}
    # Pydantic v2: use model_fields and FieldInfo.is_required
    fields = getattr(cls, "model_fields", None)
    if fields is None:
        # fallback for older pydantic versions
        fields = getattr(cls, "__fields__", {})

    for name, field in fields.items():
        # FieldInfo in pydantic v2 exposes `is_required`
        is_required = getattr(field, "is_required", None)
        if is_required is None:
            # pydantic v1 compatibility: Field has 'required'
            is_required = getattr(field, "required", False)

        if is_required:
            ft = getattr(field, "annotation", None) or getattr(
                field, "outer_type_", None
            )
            origin = get_origin(ft)
            if ft is int or origin is int:
                example[name] = 0
            elif ft is float or origin is float:
                example[name] = 0.0
            elif ft is bool or origin is bool:
                example[name] = False
            elif origin is list or ft is list:
                example[name] = []
            else:
                example[name] = "<str>"
        else:
            # get default value when present
            default = None
            if hasattr(field, "default"):
                default = getattr(field, "default")
            elif hasattr(field, "get_default"):
                default = field.get_default()
            example[name] = default
    return example


def _format_validation_error(exc: ValidationError) -> Dict[str, Any]:
    errors = exc.errors()
    return {
        "errors": errors,
        "summary": errors[0]["msg"] if errors else "validation failed",
        "json": exc.json(),
    }


# Model map (input + result models)
MODEL_MAP: Dict[str, Any] = {
    "DeviceNameModel": DeviceNameModel,
    "GetConfigModel": GetConfigModel,
    "SendCommandModel": SendCommandModel,
    "BGPConfigModel": BGPConfigModel,
    "BGPNeighborsDetailModel": BGPNeighborsDetailModel,
    "LLDPNeighborsDetailModel": LLDPNeighborsDetailModel,
    "NetworkInstancesModel": NetworkInstancesModel,
    "PingModel": PingModel,
    "TracerouteModel": TracerouteModel,
    # result models
    "PingResultModel": PingResultModel,
    "TracerouteResultModel": TracerouteResultModel,
}


def make_validate_params(nr_mgr):
    """Return an async validate_params function bound to the provided nr_mgr.

    This avoids circular imports: server creates nr_mgr then registers
    mcp.tool()(make_validate_params(nr_mgr)).
    """

    async def validate_params(raw: Dict[str, Any], model_name: str = "DeviceNameModel"):
        logger.info(f"[Tool] validate_params called for model {model_name}")
        model_cls = MODEL_MAP.get(model_name)
        if model_cls is None:
            return {
                "success": False,
                "error": "unknown_model",
                "available_models": list(MODEL_MAP.keys()),
            }

        try:
            model_cls.parse_obj(raw)
            return {
                "success": True,
                "validated": raw,
                "model_schema": model_cls.schema(),
                "model_schema_json": model_cls.schema_json(),
                "correct_example": _example_from_model(model_cls),
            }
        except ValidationError as ve:
            missing_required = []
            if isinstance(raw, dict):
                # pydantic v2: model_fields -> FieldInfo with is_required
                fields = getattr(model_cls, "model_fields", None)
                if fields is None:
                    fields = getattr(model_cls, "__fields__", {})
                for fname, field in fields.items():
                    is_required = getattr(field, "is_required", None)
                    if is_required is None:
                        is_required = getattr(field, "required", False)
                    if is_required and fname not in raw:
                        missing_required.append(fname)

            # Build a helpful suggested_payload when client used common alternate keys
            suggested_payload = None
            if isinstance(raw, dict):
                if "name" in raw and "device_name" in missing_required:
                    suggested_payload = {"device_name": raw.get("name")}
                elif "hostname" in raw and "device_name" in missing_required:
                    try:
                        hosts = nr_mgr.list_hosts()
                        match = next(
                            (
                                h
                                for h in hosts
                                if h.get("hostname") == raw.get("hostname")
                            ),
                            None,
                        )
                        if match:
                            suggested_payload = {"device_name": match.get("name")}
                        else:
                            suggested_payload = {
                                "device_name": f"<name from list_all_hosts for hostname {raw.get('hostname')}>"
                            }
                    except Exception:
                        suggested_payload = {"device_name": "<inventory_name>"}

            formatted = _format_validation_error(ve)
            if "device_name" in missing_required:
                formatted["summary"] = "'device_name' is a required property"
                friendly = formatted.get("friendly", [])
                friendly.insert(0, formatted["summary"])
                formatted["friendly"] = friendly

            return {
                "success": False,
                "validation": formatted,
                "correct_example": _example_from_model(model_cls),
                "model_schema": model_cls.schema(),
                "model_schema_json": model_cls.schema_json(),
                "suggested_payload": suggested_payload,
                "note": "If you provided 'name' or 'hostname', map it to the inventory 'name' and send it as 'device_name'. Call list_all_hosts() to discover inventory names.",
            }

    return validate_params
