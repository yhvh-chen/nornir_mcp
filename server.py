#!/usr/bin/env python3
# server.py
import logging
from mcp.server.fastmcp import FastMCP
from nornir_ops import NornirManager
from validation_models import (
    BGPConfigModel,
    BGPNeighborsDetailModel,
    DeviceNameModel,
    GetConfigModel,
    LLDPNeighborsDetailModel,
    NetworkInstancesModel,
    SendCommandModel,
    TracerouteModel,
    make_validate_params,
)
from sse_starlette.sse import EventSourceResponse

# (Pydantic models and validation helpers moved to validation_models.py)


# --- Server Setup ---

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("nornir_mcp")

# --- Server Setup ---

import os

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("nornir_mcp")

host = os.getenv("MCP_HOST", "127.0.0.1")
port = int(os.getenv("MCP_PORT", "8000"))

try:
    # Make message_path explicit so clients must connect to /mcp/messages/
    # Explicitly set the SSE message path so clients must connect to /sse.
    # This prevents clients from accidentally connecting to the server root and
    # seeing 404s when they expect SSE at /sse (logs showed attempts to / returning 404).
    mcp = FastMCP("Nornir_MCP", host=host, port=port, message_path="/sse")
    nr_mgr = NornirManager()
except Exception as e:
    logger.critical(f"Fatal error during initialization: {e}", exc_info=True)
    exit(1)
# Register validate_params as a tool now that `mcp` and `nr_mgr` exist.
# make_validate_params returns an async function bound to the nr_mgr instance.
try:
    # Register validate_params as an MCP tool with a user-visible description
    # so clients can discover and call it. It validates raw input dicts against
    # the server's Pydantic models and returns validation results, schema and
    # an example payload.
    validate_params = mcp.tool(
        description="Validate input payloads against known Pydantic models; returns success, validation details, model schema, and example."
    )(make_validate_params(nr_mgr))
except Exception as e:
    logger.warning(f"Failed to register 'validate_params' tool: {e}")

# Register prompts from prompts.py so users can add their own prompt_* functions
try:
    from prompts import register_prompts

    register_prompts(mcp)
except Exception as e:
    logger.warning(f"Could not import or register prompts from prompts.py: {e}")
# Register resources from resources.py so users can add resource_* functions
try:
    from resources import register_resources

    register_resources(mcp, nr_mgr)
except Exception as e:
    logger.warning(f"Could not import or register resources from resources.py: {e}")


# --- NAPALM Getter Tools ---


@mcp.tool()
async def get_facts(data: DeviceNameModel):
    """Retrieve high-level facts and information about the device (e.g., vendor, model, serial number, OS version)."""
    logger.info(f"[Tool] 'get_facts' called for {data.device_name}")
    return await nr_mgr.get_napalm_data(data.device_name, "facts")


@mcp.tool()
async def get_vlans(data: DeviceNameModel):
    """Retrieve the VLAN database from the device."""
    logger.info(f"[Tool] 'get_vlans' called for {data.device_name}")
    return await nr_mgr.get_napalm_data(data.device_name, "vlans")


@mcp.tool()
async def get_users(data: DeviceNameModel):
    """Get locally configured users on the device."""
    logger.info(f"[Tool] 'get_users' called for {data.device_name}")
    return await nr_mgr.get_napalm_data(data.device_name, "users")


@mcp.tool()
async def get_arp_table(data: DeviceNameModel):
    """Get the device's ARP (Address Resolution Protocol) table."""
    logger.info(f"[Tool] 'get_arp_table' called for {data.device_name}")
    return await nr_mgr.get_napalm_data(data.device_name, "arp_table")


@mcp.tool()
async def get_bgp_neighbors(data: DeviceNameModel):
    """Get a summary of BGP (Border Gateway Protocol) neighbors."""
    logger.info(f"[Tool] 'get_bgp_neighbors' called for {data.device_name}")
    return await nr_mgr.get_napalm_data(data.device_name, "bgp_neighbors")


@mcp.tool()
async def get_interfaces(data: DeviceNameModel):
    """Get a list of all network interfaces on the device."""
    logger.info(f"[Tool] 'get_interfaces' called for {data.device_name}")
    return await nr_mgr.get_napalm_data(data.device_name, "interfaces")


@mcp.tool()
async def get_interfaces_counters(data: DeviceNameModel):
    """Retrieve detailed RX/TX counters for all interfaces."""
    logger.info(f"[Tool] 'get_interfaces_counters' called for {data.device_name}")
    return await nr_mgr.get_napalm_data(data.device_name, "interfaces_counters")


@mcp.tool()
async def get_interfaces_ip(data: DeviceNameModel):
    """Get IP address information for all interfaces."""
    logger.info(f"[Tool] 'get_interfaces_ip' called for {data.device_name}")
    return await nr_mgr.get_napalm_data(data.device_name, "interfaces_ip")


@mcp.tool()
async def get_mac_address_table(data: DeviceNameModel):
    """Get the device's MAC address table (forwarding database)."""
    logger.info(f"[Tool] 'get_mac_address_table' called for {data.device_name}")
    return await nr_mgr.get_napalm_data(data.device_name, "mac_address_table")


@mcp.tool()
async def get_snmp_information(data: DeviceNameModel):
    """Retrieve basic SNMP (Simple Network Management Protocol) configuration."""
    logger.info(f"[Tool] 'get_snmp_information' called for {data.device_name}")
    return await nr_mgr.get_napalm_data(data.device_name, "snmp_information")


@mcp.tool()
async def get_ipv6_neighbors_table(data: DeviceNameModel):
    """Retrieve the IPv6 Neighbor Discovery (NDP) table."""
    logger.info(f"[Tool] 'get_ipv6_neighbors_table' called for {data.device_name}")
    return await nr_mgr.get_napalm_data(data.device_name, "ipv6_neighbors_table")


@mcp.tool()
async def get_lldp_neighbors(data: DeviceNameModel):
    """Get a summary of LLDP (Link Layer Discovery Protocol) neighbors."""
    logger.info(f"[Tool] 'get_lldp_neighbors' called for {data.device_name}")
    return await nr_mgr.get_napalm_data(data.device_name, "lldp_neighbors")


@mcp.tool()
async def get_ntp_peers(data: DeviceNameModel):
    """Get the status of NTP (Network Time Protocol) peers."""
    logger.info(f"[Tool] 'get_ntp_peers' called for {data.device_name}")
    return await nr_mgr.get_napalm_data(data.device_name, "ntp_peers")


@mcp.tool()
async def get_ntp_servers(data: DeviceNameModel):
    """Retrieve the list of configured NTP servers."""
    logger.info(f"[Tool] 'get_ntp_servers' called for {data.device_name}")
    return await nr_mgr.get_napalm_data(data.device_name, "ntp_servers")


@mcp.tool()
async def get_ntp_stats(data: DeviceNameModel):
    """Get NTP synchronization statistics."""
    logger.info(f"[Tool] 'get_ntp_stats' called for {data.device_name}")
    return await nr_mgr.get_napalm_data(data.device_name, "ntp_stats")


@mcp.tool()
async def get_optics(data: DeviceNameModel):
    """Retrieve diagnostics for optical modules (e.g., SFP, QSFP)."""
    logger.info(f"[Tool] 'get_optics' called for {data.device_name}")
    return await nr_mgr.get_napalm_data(data.device_name, "optics")


@mcp.tool()
async def get_probes_config(data: DeviceNameModel):
    """Get configuration for any monitoring probes or tests running on the device."""
    logger.info(f"[Tool] 'get_probes_config' called for {data.device_name}")
    return await nr_mgr.get_napalm_data(data.device_name, "probes_config")


@mcp.tool()
async def is_alive(data: DeviceNameModel):
    """Check health and reachability of the device management interface."""
    logger.info(f"[Tool] 'is_alive' called for {data.device_name}")
    # Use the explicit check_is_alive method which calls the connection's
    # is_alive() function directly (some drivers expose this as a method
    # on the connection, not as a napalm_get getter).
    return await nr_mgr.check_is_alive(data.device_name)


# --- Specific Tool Endpoints with Validation ---


@mcp.tool()
async def get_config(data: GetConfigModel):
    """Use NAPALM to retrieve device configurations (running, startup, or candidate)."""
    logger.info(
        f"[Tool] get_config called for {data.device_name} (retrieve={data.retrieve})"
    )
    host = nr_mgr.nr.filter(name=data.device_name)
    if not host.inventory.hosts:
        return {
            "host": data.device_name,
            "success": False,
            "error_type": "InventoryError",
            "result": f"Device '{data.device_name}' not found.",
        }
    from nornir_napalm.plugins.tasks import napalm_get

    result = host.run(
        task=napalm_get,
        getters=["config"],
        retrieve=data.retrieve,
        name=f"Get '{data.retrieve}' config for {data.device_name}",
        raise_on_error=False,
    )
    return nr_mgr._format_result(result, data.device_name)


@mcp.tool()
async def get_bgp_config(data: BGPConfigModel):
    """Retrieve BGP configuration from the device."""
    logger.info(f"[Tool] get_bgp_config called for {data.device_name}")
    host = nr_mgr.nr.filter(name=data.device_name)
    if not host.inventory.hosts:
        return {
            "host": data.device_name,
            "success": False,
            "error_type": "InventoryError",
            "result": f"Device '{data.device_name}' not found.",
        }
    from nornir_napalm.plugins.tasks import napalm_get

    result = host.run(
        task=napalm_get,
        getters=["bgp_config"],
        group=data.group,
        neighbor=data.neighbor,
        name=f"Get BGP config for {data.device_name}",
        raise_on_error=False,
    )
    return nr_mgr._format_result(result, data.device_name)


@mcp.tool()
async def get_bgp_neighbors_detail(data: BGPNeighborsDetailModel):
    """Obtain a detailed view of all BGP neighbors."""
    logger.info(f"[Tool] get_bgp_neighbors_detail called for {data.device_name}")
    host = nr_mgr.nr.filter(name=data.device_name)
    if not host.inventory.hosts:
        return {
            "host": data.device_name,
            "success": False,
            "error_type": "InventoryError",
            "result": f"Device '{data.device_name}' not found.",
        }
    from nornir_napalm.plugins.tasks import napalm_get

    result = host.run(
        task=napalm_get,
        getters=["bgp_neighbors_detail"],
        neighbor_address=data.neighbor_address,
        name=f"Get BGP neighbors detail for {data.device_name}",
        raise_on_error=False,
    )
    return nr_mgr._format_result(result, data.device_name)


@mcp.tool()
async def get_lldp_neighbors_detail(data: LLDPNeighborsDetailModel):
    """Obtain a detailed view of all LLDP neighbors."""
    logger.info(f"[Tool] get_lldp_neighbors_detail called for {data.device_name}")
    host = nr_mgr.nr.filter(name=data.device_name)
    if not host.inventory.hosts:
        return {
            "host": data.device_name,
            "success": False,
            "error_type": "InventoryError",
            "result": f"Device '{data.device_name}' not found.",
        }
    from nornir_napalm.plugins.tasks import napalm_get

    result = host.run(
        task=napalm_get,
        getters=["lldp_neighbors_detail"],
        interface=data.interface,
        name=f"Get LLDP neighbors detail for {data.device_name}",
        raise_on_error=False,
    )
    return nr_mgr._format_result(result, data.device_name)


@mcp.tool()
async def get_network_instances(data: NetworkInstancesModel):
    """Retrieve a list of network instances (e.g., VRFs)."""
    logger.info(f"[Tool] get_network_instances called for {data.device_name}")
    host = nr_mgr.nr.filter(name=data.device_name)
    if not host.inventory.hosts:
        return {
            "host": data.device_name,
            "success": False,
            "error_type": "InventoryError",
            "result": f"Device '{data.device_name}' not found.",
        }
    from nornir_napalm.plugins.tasks import napalm_get

    result = host.run(
        task=napalm_get,
        getters=["network_instances"],
        name=data.name,
        raise_on_error=False,
    )
    return nr_mgr._format_result(result, data.device_name)


@mcp.tool()
async def traceroute(data: TracerouteModel):
    """Execute the traceroute command from the device to the specified destination."""
    logger.info(
        f"[Tool] traceroute called for {data.device_name} to {data.destination}"
    )
    # Delegate to NornirManager.traceroute which returns the inner traceroute dict (success or error)
    return await nr_mgr.traceroute(
        device_name=data.device_name,
        destination=data.destination,
        source=data.source,
        ttl=data.ttl,
        timeout=data.timeout,
        vrf=data.vrf,
    )


@mcp.tool()
async def send_command(data: SendCommandModel):
    """Send a validated read-only command or list of commands to the device."""
    # Normalize input: prefer `commands` list when present, otherwise use `command` as single-item list
    if data.commands:
        cmds = data.commands
    elif data.command:
        cmds = [data.command]
    else:
        logger.warning("send_command called without 'command' or 'commands' field")
        return {
            "host": data.device_name,
            "success": False,
            "error_type": "ValidationError",
            "result": "Either 'command' or 'commands' must be provided.",
        }

    logger.info(
        f"[Tool] send_command called for {data.device_name} with commands: {cmds}"
    )
    result = await nr_mgr.send_command(data.device_name, cmds)

    # Normalize common Nornir shapes into command -> output dict
    try:
        # AggregatedResult-like mapping
        if hasattr(result, "items"):
            host_key = next(iter(result.keys()), None)
            if host_key is not None:
                host_res = result[host_key]
                if isinstance(host_res, (list, tuple)) and host_res:
                    first = host_res[0]
                    payload = getattr(first, "result", first)
                    if isinstance(payload, dict):
                        return payload
                    if isinstance(payload, str) and len(cmds) == 1:
                        return {cmds[0]: payload}
                    return payload
        # Single Result object
        if hasattr(result, "result"):
            payload = getattr(result, "result")
            if isinstance(payload, dict):
                return payload
            if isinstance(payload, str) and len(cmds) == 1:
                return {cmds[0]: payload}
            return payload
    except Exception:
        logger.exception("Unable to coerce nr_mgr result into serializable structure")

    # Fallback: return raw object
    return result


@mcp.tool()
async def list_all_hosts():
    """Return a minimal discovery list containing only the inventory device_name.

    Output format: [{"device_name": "R1"}, {"device_name": "R2"}, ...]
    This makes it explicit to clients/LLMs what identifier to use for tool calls.
    """
    logger.info("[Tool] list_all_hosts called")
    try:
        hosts_raw = nr_mgr.list_hosts()
        # support nr_mgr returning a JSON string
        if isinstance(hosts_raw, str):
            import json

            try:
                hosts = json.loads(hosts_raw)
            except Exception:
                logger.exception(
                    "Failed to parse hosts JSON string from nr_mgr.list_hosts()"
                )
                return {"success": False, "error": "invalid_inventory_format"}
        else:
            hosts = hosts_raw

        # coerce single-host dict into list
        if isinstance(hosts, dict):
            hosts = [hosts]

        if not isinstance(hosts, list):
            logger.warning(
                "Unexpected hosts structure from nr_mgr.list_hosts(): %s",
                type(hosts).__name__,
            )
            return {"success": False, "error": "unexpected_inventory_shape"}

        result = []
        for h in hosts:
            # ensure dict-like
            if not isinstance(h, dict):
                # try to parse string entries
                try:
                    import json

                    h = json.loads(h)
                except Exception:
                    logger.warning("Skipping non-dict host entry: %s", type(h).__name__)
                    continue

            # prefer existing device_name, fall back to 'name'
            device = h.get("device_name") or h.get("name")
            if device:
                result.append({"device_name": device})

        logger.debug("[Tool:list_all_hosts] returning %d hosts", len(result))
        return result
    except Exception as e:
        logger.exception("Unexpected error in list_all_hosts: %s", e)
        return {"success": False, "error": "internal_error", "detail": str(e)}


# Expose the MCP server instance for run.py and other entrypoints
server = mcp

if __name__ == "__main__":
    logger.info("[Setup] Starting Nornir MCP server...")
    mcp.run(transport="streamable-http")
