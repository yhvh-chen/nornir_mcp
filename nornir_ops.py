# nornir_ops.py
import logging
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import yaml
from nornir import InitNornir
from nornir.core import Nornir
from nornir.core.task import Result, Task
from nornir_napalm.plugins.tasks import napalm_get, napalm_ping

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class CommandValidator:
    """Handles validation of commands against a configurable blacklist."""

    def __init__(self, blacklist_file: Path):
        self.blacklist = self._load_blacklist(blacklist_file)

    def _load_blacklist(self, file_path: Path) -> Dict[str, List[str]]:
        default_blacklist = {
            "exact_commands": [],
            "keywords": [],
            "disallowed_patterns": [],
        }
        if not file_path.exists():
            logger.warning(
                f"Blacklist file not found at '{file_path}'. Command validation will be limited."
            )
            return default_blacklist
        try:
            with open(file_path, "r") as f:
                data = yaml.safe_load(f)
                normalized_data = {
                    k.lower(): [str(item).lower() for item in v]
                    for k, v in data.items()
                }
                default_blacklist.update(normalized_data)
                logger.info(
                    f"Command blacklist loaded successfully from '{file_path}'."
                )
                return default_blacklist
        except (yaml.YAMLError, IOError) as e:
            logger.error(
                f"Failed to load or parse blacklist file '{file_path}': {e}",
                exc_info=True,
            )
            return default_blacklist

    def validate(self, command: str) -> Optional[str]:
        command_lower = command.lower().strip()
        for pattern in self.blacklist.get("disallowed_patterns", []):
            if pattern in command:
                return f"Command contains disallowed pattern: '{pattern}'"
        if command_lower in self.blacklist.get("exact_commands", []):
            return "Command is explicitly blacklisted."
        for keyword in self.blacklist.get("keywords", []):
            if re.search(rf"\b{re.escape(keyword)}\b", command_lower):
                return f"Command contains blacklisted keyword: '{keyword}'"
        return None


class NornirManager:
    """Encapsulates Nornir operations for network device management."""

    def __init__(self, config_file: str = "conf/config.yaml"):
        logger.info(
            f"[Setup] Initializing Nornir manager with config: {config_file}..."
        )
        self.nr: Optional[Nornir] = None
        try:
            self.nr = InitNornir(config_file=config_file)
            logger.info("[Setup] Nornir initialized successfully!")
        except Exception as e:
            logger.error(
                f"[Error] Failed to initialize Nornir from {config_file}: {e}",
                exc_info=True,
            )
            raise
        blacklist_path = Path("conf/blacklist.yaml")
        self.command_validator = CommandValidator(blacklist_path)

    def _validate_host_exists(self, device_name: str) -> bool:
        if not self.nr:
            logger.error("Nornir is not initialized. Cannot validate host.")
            return False
        if device_name not in self.nr.inventory.hosts:
            logger.warning(f"Device '{device_name}' not found in Nornir inventory.")
            return False
        return True

    async def _run_host_task(
        self,
        device_name: str,
        task_func: Callable[..., Result],
        task_name: str,
        **task_kwargs,
    ) -> Dict[str, Any]:
        if not self.nr:
            return {
                "host": device_name,
                "success": False,
                "error_type": "NornirInitError",
                "result": "NornirManager not initialized.",
            }
        if not self._validate_host_exists(device_name):
            return {
                "host": device_name,
                "success": False,
                "error_type": "InventoryError",
                "result": f"Device '{device_name}' not found.",
            }

        logger.debug(
            f"Running task '{task_name}' on device '{device_name}' with args: {task_kwargs}"
        )
        target_inventory = self.nr.filter(name=device_name)
        try:
            # Run the requested task and return the raw payload to the LLM (no filtering/regexing).
            result = target_inventory.run(
                task=task_func, name=task_name, raise_on_error=False, **task_kwargs
            )

            # Convert AggregatedResult / Result shapes into simple serializable payloads.
            serializable: Dict[str, Any] = {}
            if hasattr(result, "items"):
                for host_key, host_res in result.items():
                    try:
                        # host_res commonly is a list of Result objects; prefer first.result if present
                        first = host_res[0]
                        payload = getattr(first, "result", first)
                    except Exception:
                        payload = host_res
                    serializable[host_key] = payload
            elif hasattr(result, "result"):
                serializable = getattr(result, "result")
            else:
                serializable = str(result)

            # If single-host call, return that host's payload for convenience
            if (
                isinstance(serializable, dict)
                and len(serializable) == 1
                and device_name in serializable
            ):
                return {
                    "host": device_name,
                    "success": True,
                    "result": serializable[device_name],
                }

            return {"host": device_name, "success": True, "result": serializable}
        except Exception as e:
            logger.error(
                f"[Error] Unexpected error during task run for {task_name} on {device_name}: {e}",
                exc_info=True,
            )
            return {
                "host": device_name,
                "success": False,
                "error_type": type(e).__name__,
                "result": f"Unexpected error: {e}",
            }
        finally:
            # Best-effort: close per-host napalm connection(s) after data is returned.
            # DO NOT call target_inventory.close_connections() (mutates shared state).
            logger.debug(
                f"Releasing napalm connections for device '{device_name}' (best-effort)."
            )
            try:
                inv = getattr(target_inventory, "inventory", None)
                cfg = getattr(target_inventory, "config", None)
                if inv and getattr(inv, "hosts", None):
                    for host_obj in inv.hosts.values():
                        try:
                            # Prefer host-level close_connections if provided
                            if hasattr(host_obj, "close_connections"):
                                try:
                                    host_obj.close_connections()
                                except Exception:
                                    logger.debug(
                                        "Ignoring error closing host_obj.close_connections()",
                                        exc_info=True,
                                    )
                                continue

                            # Otherwise try to close the napalm connection object if exposed
                            try:
                                conn = host_obj.get_connection("napalm", cfg)
                                if conn is not None:
                                    if hasattr(conn, "close"):
                                        try:
                                            conn.close()
                                        except Exception:
                                            logger.debug(
                                                "Ignoring error calling conn.close()",
                                                exc_info=True,
                                            )
                                    elif hasattr(conn, "close_connection"):
                                        try:
                                            conn.close_connection()
                                        except Exception:
                                            logger.debug(
                                                "Ignoring error calling conn.close_connection()",
                                                exc_info=True,
                                            )
                            except Exception:
                                logger.debug(
                                    "Ignoring error while attempting to fetch/close connection for host",
                                    exc_info=True,
                                )
                        except Exception:
                            logger.debug(
                                "Ignoring unexpected error during per-host connection close",
                                exc_info=True,
                            )
            except Exception:
                logger.debug(
                    "Failed to run per-host connection cleanup (best-effort)",
                    exc_info=True,
                )

    # _format_result removed; returning raw Nornir results from _run_host_task as requested

    async def get_napalm_data(self, device_name: str, getter: str) -> Dict[str, Any]:
        logger.info(f"[API] Attempting to get '{getter}' from device: {device_name}")
        return await self._run_host_task(
            device_name=device_name,
            task_func=napalm_get,
            task_name=f"Get '{getter}' for {device_name}",
            getters=[getter],
        )

    async def ping(
        self,
        device_name: str,
        destination: str,
        source: str = "",
        ttl: int = 255,
        timeout: int = 2,
        size: int = 100,
        count: int = 5,
        vrf: str = "",
        source_interface: str = "",
    ) -> Dict[str, Any]:
        """Execute a ping on the device using napalm_ping and return the PingResultDict.

        The returned value will be the inner ping dict containing either 'success' or 'error'.
        """
        logger.info(
            f"[API] Attempting ping to '{destination}' from device: {device_name}"
        )
        if not self.nr:
            return {
                "host": device_name,
                "success": False,
                "error_type": "NornirInitError",
                "result": "NornirManager not initialized.",
            }
        if not self._validate_host_exists(device_name):
            return {
                "host": device_name,
                "success": False,
                "error_type": "InventoryError",
                "result": f"Device '{device_name}' not found.",
            }

        host = self.nr.filter(name=device_name)
        try:
            # Note: many nornir_napalm versions' napalm_ping task does not accept a
            # `source_interface` kwarg. Omit it for compatibility.
            result = host.run(
                task=napalm_ping,
                dest=destination,
                source=source,
                ttl=ttl,
                timeout=timeout,
                size=size,
                count=count,
                vrf=vrf,
                name=f"Ping {destination} from {device_name}",
                raise_on_error=False,
            )
        except Exception as e:
            logger.error(
                f"Unexpected error running ping on {device_name}: {e}", exc_info=True
            )
            return {
                "host": device_name,
                "success": False,
                "error_type": type(e).__name__,
                "result": f"Unexpected error: {e}",
            }

        # Extract the single-host result payload
        try:
            keys = list(result.keys())
            if not keys:
                return {
                    "host": device_name,
                    "success": False,
                    "error_type": "ResultMissingHost",
                    "result": "No result found for host.",
                }
            host_key = keys[0]
            host_res = result[host_key]
            # host_res is usually a list of Task Result objects; take first.result
            try:
                first = host_res[0]
                payload = getattr(first, "result", first)
            except Exception:
                payload = host_res

            # payload should be a dict with 'success' or 'error'
            return payload
        except Exception as e:
            logger.exception("Failed to extract ping payload", exc_info=True)
            return {
                "host": device_name,
                "success": False,
                "error_type": "ResultFormatError",
                "result": str(e),
            }

    async def traceroute(
        self,
        device_name: str,
        destination: str,
        source: str = "",
        ttl: int = 255,
        timeout: int = 2,
        vrf: str = "",
    ) -> Dict[str, Any]:
        """Execute a traceroute on the device using napalm_traceroute and return the TracerouteResultDict.

        The returned value will be the inner traceroute dict containing either 'success' or 'error'.
        """
        logger.info(
            f"[API] Attempting traceroute to '{destination}' from device: {device_name}"
        )
        if not self.nr:
            return {
                "host": device_name,
                "success": False,
                "error_type": "NornirInitError",
                "result": "NornirManager not initialized.",
            }
        if not self._validate_host_exists(device_name):
            return {
                "host": device_name,
                "success": False,
                "error_type": "InventoryError",
                "result": f"Device '{device_name}' not found.",
            }

        host = self.nr.filter(name=device_name)
        try:
            # Use our compatibility traceroute task which will either call a native traceroute
            # on the napalm connection or fall back to a CLI traceroute.
            result = host.run(
                task=self._traceroute_task,
                dest=destination,
                source=source,
                ttl=ttl,
                timeout=timeout,
                vrf=vrf,
                name=f"Traceroute {destination} from {device_name}",
                raise_on_error=False,
            )
        except Exception as e:
            logger.error(
                f"Unexpected error running traceroute on {device_name}: {e}",
                exc_info=True,
            )
            return {
                "host": device_name,
                "success": False,
                "error_type": type(e).__name__,
                "result": f"Unexpected error: {e}",
            }

        # Extract the single-host result payload
        try:
            keys = list(result.keys())
            if not keys:
                return {
                    "host": device_name,
                    "success": False,
                    "error_type": "ResultMissingHost",
                    "result": "No result found for host.",
                }
            host_key = keys[0]
            host_res = result[host_key]
            try:
                first = host_res[0]
                payload = getattr(first, "result", first)
            except Exception:
                payload = host_res

            # payload should be a dict with 'success' or 'error'
            return payload
        except Exception as e:
            logger.exception("Failed to extract traceroute payload", exc_info=True)
            return {
                "host": device_name,
                "success": False,
                "error_type": "ResultFormatError",
                "result": str(e),
            }

    async def send_command(self, device_name: str, command: Any) -> Any:
        """Send either a single command (str) or a list of commands to the device.

        Returns the raw Nornir result (AggregatedResult) from the task run. The task
        result payload for multiple commands will be a dict mapping command->output.
        """
        # Allow either a single command string or a list of commands
        cmds = command if isinstance(command, (list, tuple)) else [command]

        # Validate each command (CommandValidator expects a single command string)
        for cmd in cmds:
            validation_error = self.command_validator.validate(str(cmd))
            if validation_error:
                logger.warning(
                    f"Command validation failed for '{cmd}': {validation_error}"
                )
                return {
                    "host": device_name,
                    "success": False,
                    "error_type": "CommandValidationError",
                    "result": validation_error,
                }

        return await self._run_host_task(
            device_name=device_name,
            task_func=self._send_command_task,
            task_name=f"Execute command(s) on {device_name}",
            command=cmds,
        )

    @staticmethod
    def _send_command_task(task: Task, command: Any) -> Result:
        """Execute one or more CLI commands via the NAPALM connection.

        'command' may be a list of strings or a single string. When multiple
        commands are provided, connection.cli() typically returns a dict mapping
        command -> output. For a single command we return the raw string output.
        """
        try:
            connection = task.host.get_connection("napalm", task.nornir.config)
            # Normalize to list
            cmds = command if isinstance(command, (list, tuple)) else [command]
            output_dict = connection.cli(list(cmds))

            # If caller passed a single command, return its string output (if present)
            if len(cmds) == 1:
                single = cmds[0]
                command_output = output_dict.get(single)
                if command_output is None:
                    raise ValueError(
                        f"No output received from device for command: {single}"
                    )
                return Result(host=task.host, result=command_output)

            # Multiple commands: return the whole mapping (command -> output)
            return Result(host=task.host, result=output_dict)
        except Exception:
            logger.debug(
                f"Exception within _send_command_task for {task.host.name}",
                exc_info=True,
            )
            raise

    @staticmethod
    def _traceroute_task(
        task: Task,
        dest: str,
        source: str = "",
        ttl: int = 255,
        timeout: int = 2,
        vrf: str = "",
    ) -> Result:
        """Execute a traceroute using the NAPALM connection if supported, otherwise fall back to a CLI traceroute.

        This provides compatibility for nornir_napalm distributions that don't expose a napalm_traceroute helper.
        The method returns a Result whose payload is either the structured traceroute dict (if the connection
        provides a traceroute method) or the raw CLI output string.
        """
        try:
            connection = task.host.get_connection("napalm", task.nornir.config)

            # Prefer a native traceroute method on the connection (some drivers may implement this)
            traceroute_fn = getattr(connection, "traceroute", None)
            if callable(traceroute_fn):
                # Some drivers may accept different argument names; try a best-effort call
                try:
                    result = traceroute_fn(
                        dest, source=source or None, ttl=ttl, timeout=timeout, vrf=vrf
                    )
                except TypeError:
                    # Fallback to calling with only mandatory args
                    result = traceroute_fn(dest)
                return Result(host=task.host, result=result)

            # Fallback: try issuing a CLI traceroute command via connection.cli()
            # This is a conservative invocation -- device-specific flags are not used here.
            cmd = f"traceroute {dest}"
            output = connection.cli([cmd])
            # connection.cli commonly returns a dict mapping command->output
            if isinstance(output, dict):
                return Result(host=task.host, result=output.get(cmd, output))
            return Result(host=task.host, result=output)
        except Exception:
            logger.debug(
                f"Exception within _traceroute_task for {task.host.name}", exc_info=True
            )
            raise

    @staticmethod
    def _task_is_alive(task: Task) -> Result:
        """Nornir task: call the napalm connection's is_alive() method.

        This runs in the Nornir worker context and returns a Result whose
        payload is a boolean indicating the connection health.
        """
        try:
            connection = task.host.get_connection("napalm", task.nornir.config)
            # Support both callable is_alive() and a truthy attribute if present
            attr = getattr(connection, "is_alive", None)
            if callable(attr):
                alive_status = attr()
            else:
                alive_status = bool(attr)
            return Result(host=task.host, result=alive_status)
        except Exception:
            logger.debug(
                f"Exception within _task_is_alive for {task.host.name}", exc_info=True
            )
            raise

    async def check_is_alive(self, device_name: str) -> Dict[str, Any]:
        """Run the _is_alive_task against a single device and format the result.

        Returns the same dictionary structure as other API methods (host, success, result/error).
        """
        logger.info(f"[API] Checking is_alive for device: {device_name}")
        return await self._run_host_task(
            device_name=device_name,
            task_func=self._task_is_alive,
            task_name=f"Check is_alive for {device_name}",
        )

    def list_hosts(self) -> List[Dict[str, Any]]:
        if not self.nr:
            logger.error("Nornir is not initialized. Cannot list hosts.")
            return []
        logger.info("Listing all hosts in inventory")
        hosts_info = []
        sensitive_keys = {"password", "secret"}
        for name, host_obj in self.nr.inventory.hosts.items():
            safe_data = {
                k: v
                for k, v in (host_obj.data or {}).items()
                if k not in sensitive_keys
            }
            hosts_info.append(
                {
                    "name": name,
                    "hostname": host_obj.hostname,
                    "platform": host_obj.platform,
                    "groups": list(host_obj.groups) if host_obj.groups else [],
                    "data": safe_data,
                }
            )
        return hosts_info

    def _format_result(self, raw_result: Any, device_name: str) -> Dict[str, Any]:
        """Compatibility helper: convert common Nornir result shapes into a
        consistent dict: {host, success, result} or an error payload.

        This mirrors the lightweight coercion logic used elsewhere in the
        codebase so server endpoints that still call `_format_result` work.
        """
        try:
            # AggregatedResult-like mapping
            if hasattr(raw_result, "items"):
                keys = list(raw_result.keys())
                if not keys:
                    return {
                        "host": device_name,
                        "success": False,
                        "error_type": "ResultMissingHost",
                        "result": "No result found for host.",
                    }
                host_key = keys[0]
                host_res = raw_result[host_key]
                try:
                    first = host_res[0]
                    payload = getattr(first, "result", first)
                except Exception:
                    payload = host_res
                return {"host": device_name, "success": True, "result": payload}

            # Result-like object
            if hasattr(raw_result, "result"):
                return {
                    "host": device_name,
                    "success": True,
                    "result": getattr(raw_result, "result"),
                }

            # Fallback: try to coerce to dict/str
            if isinstance(raw_result, dict) or isinstance(raw_result, list):
                return {"host": device_name, "success": True, "result": raw_result}

            return {"host": device_name, "success": True, "result": str(raw_result)}
        except Exception as e:
            logger.exception("_format_result failed", exc_info=True)
            return {
                "host": device_name,
                "success": False,
                "error_type": "FormatError",
                "result": str(e),
            }
