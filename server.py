#!/usr/bin/env python3
# server.py
import asyncio
import logging
from typing import Literal, Optional

from fastmcp import FastMCP
from nornir_ops import NornirManager
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

# --- Pydantic Models for Input Validation ---

class HostnameModel(BaseModel):
    """A model for validating a single hostname."""
    hostname: str = Field(..., description="The name of the target device as defined in the Nornir inventory.")

class GetConfigModel(HostnameModel):
    """A model for validating inputs to the get_config tool."""
    retrieve: Literal["running", "startup", "candidate"] = Field(
        default="running",
        description="The type of configuration to retrieve."
    )

class SendCommandModel(HostnameModel):
    """A model for validating inputs to the send_command tool."""
    command: str = Field(..., description="The read-only command to execute on the device.")

class BGPConfigModel(HostnameModel):
    """A model for validating inputs to the get_bgp_config tool."""
    group: str = Field(default="", description="Returns the configuration of a specific BGP group.")
    neighbor: str = Field(default="", description="Returns the configuration of a specific BGP neighbor.")

class BGPNeighborsDetailModel(HostnameModel):
    """A model for validating inputs to the get_bgp_neighbors_detail tool."""
    neighbor_address: str = Field(default="", description="Returns the statistics for a specific BGP neighbor.")

class LLDPNeighborsDetailModel(HostnameModel):
    """A model for validating inputs to the get_lldp_neighbors_detail tool."""
    interface: str = Field(default="", description="The interface to query for LLDP neighbors.")

class NetworkInstancesModel(HostnameModel):
    """A model for validating inputs to the get_network_instances tool."""
    name: str = Field(default="", description="The name of the network instance (e.g., VRF) to query.")

class PingModel(HostnameModel):
    """A model for validating inputs to the ping tool."""
    destination: str
    source: str = ""
    ttl: int = 255
    timeout: int = 2
    size: int = 100
    count: int = 5
    vrf: str = ""

class TracerouteModel(HostnameModel):
    """A model for validating inputs to the traceroute tool."""
    destination: str
    source: str = ""
    ttl: int = 255
    timeout: int = 2
    vrf: str = ""


# --- Server Setup ---

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("nornir_mcp")

try:
    mcp = FastMCP("Nornir_MCP")
    nr_mgr = NornirManager()
except Exception as e:
    logger.critical(f"Fatal error during initialization: {e}", exc_info=True)
    exit(1)


# --- Helper Function to Register NAPALM Getters ---

def register_napalm_getter(getter_name: str, description: str):
    """Factory function to create and register an async MCP tool for a NAPALM getter."""

    async def getter_endpoint(data: HostnameModel):
        """Dynamically generated endpoint for a NAPALM getter."""
        logger.info(f"[Tool] '{getter_name}' called for {data.hostname}")
        return await nr_mgr.get_napalm_data(data.hostname, getter_name)

    getter_endpoint.__name__ = getter_name
    getter_endpoint.__doc__ = description

    mcp.tool(getter_name)(getter_endpoint)
    logger.debug(f"Registered NAPALM getter endpoint: {getter_name}")


# --- Register NAPALM Getter Endpoints ---
napalm_getters_to_register = {
    "get_facts": "Get high-level device facts and information (e.g., vendor, model, serial, OS version).",
    "get_vlans": "Get the VLAN database from the device.",
    "get_users": "Get the locally configured users on the device.",
    "get_arp_table": "Get the device's ARP (Address Resolution Protocol) table.",
    "get_bgp_neighbors": "Get BGP (Border Gateway Protocol) neighbor summary.",
    "get_interfaces": "Get a list of all network interfaces on the device.",
    "get_interfaces_counters": "Get detailed RX/TX counters for all interfaces.",
    "get_interfaces_ip": "Get IP address information for all interfaces.",
    "get_mac_address_table": "Get the device's MAC address table (forwarding database).",
    "get_snmp_information": "Get basic SNMP (Simple Network Management Protocol) configuration.",
    "get_environment": "Get device environmental data (e.g., temperature, power supply status, fan status, CPU/memory usage).",
    "get_ipv6_neighbors_table": "Get the IPv6 Neighbor Discovery Protocol (NDP) table.",
    "get_lldp_neighbors": "Get a summary of LLDP (Link Layer Discovery Protocol) neighbors.",
    "get_ntp_peers": "Get the status of NTP (Network Time Protocol) peers.",
    "get_ntp_servers": "Get the list of configured NTP servers.",
    "get_ntp_stats": "Get NTP time synchronization statistics.",
    "get_optics": "Get diagnostic information from optical transceivers (e.g., SFP, QSFP).",
    "get_probes_config": "Get the configuration of any monitoring probes or tests running on the device.",
    "is_alive": "Check the health and reachability of the device's management interface.",
}
for getter_name, description in napalm_getters_to_register.items():
    register_napalm_getter(getter_name, description)


# --- Specific Tool Endpoints with Validation ---

@mcp.tool("get_config")
async def get_config(data: GetConfigModel):
    """Get a device's configuration (running, startup, or candidate) using NAPALM."""
    logger.info(f"[Tool] get_config called for {data.hostname} (retrieve={data.retrieve})")
    host = nr_mgr.nr.filter(name=data.hostname)
    if not host.inventory.hosts:
        return {"host": data.hostname, "success": False, "error_type": "InventoryError", "result": f"Host '{data.hostname}' not found."}

    from nornir_napalm.plugins.tasks import napalm_get
    result = host.run(
        task=napalm_get,
        getters=["config"],
        retrieve=data.retrieve,
        name=f"Get '{data.retrieve}' config for {data.hostname}",
        raise_on_error=False
    )
    return nr_mgr._format_result(result, data.hostname)

@mcp.tool("get_bgp_config")
async def get_bgp_config(data: BGPConfigModel):
    """Get the BGP configuration from the device."""
    logger.info(f"[Tool] get_bgp_config called for {data.hostname}")
    host = nr_mgr.nr.filter(name=data.hostname)
    if not host.inventory.hosts:
        return {"host": data.hostname, "success": False, "error_type": "InventoryError", "result": f"Host '{data.hostname}' not found."}

    from nornir_napalm.plugins.tasks import napalm_get
    result = host.run(
        task=napalm_get,
        getters=["bgp_config"],
        group=data.group,
        neighbor=data.neighbor,
        name=f"Get BGP config for {data.hostname}",
        raise_on_error=False
    )
    return nr_mgr._format_result(result, data.hostname)

@mcp.tool("get_bgp_neighbors_detail")
async def get_bgp_neighbors_detail(data: BGPNeighborsDetailModel):
    """Get a detailed view of all BGP neighbors."""
    logger.info(f"[Tool] get_bgp_neighbors_detail called for {data.hostname}")
    host = nr_mgr.nr.filter(name=data.hostname)
    if not host.inventory.hosts:
        return {"host": data.hostname, "success": False, "error_type": "InventoryError", "result": f"Host '{data.hostname}' not found."}

    from nornir_napalm.plugins.tasks import napalm_get
    result = host.run(
        task=napalm_get,
        getters=["bgp_neighbors_detail"],
        neighbor_address=data.neighbor_address,
        name=f"Get BGP neighbors detail for {data.hostname}",
        raise_on_error=False
    )
    return nr_mgr._format_result(result, data.hostname)

@mcp.tool("get_lldp_neighbors_detail")
async def get_lldp_neighbors_detail(data: LLDPNeighborsDetailModel):
    """Get a detailed view of all LLDP neighbors."""
    logger.info(f"[Tool] get_lldp_neighbors_detail called for {data.hostname}")
    host = nr_mgr.nr.filter(name=data.hostname)
    if not host.inventory.hosts:
        return {"host": data.hostname, "success": False, "error_type": "InventoryError", "result": f"Host '{data.hostname}' not found."}

    from nornir_napalm.plugins.tasks import napalm_get
    result = host.run(
        task=napalm_get,
        getters=["lldp_neighbors_detail"],
        interface=data.interface,
        name=f"Get LLDP neighbors detail for {data.hostname}",
        raise_on_error=False
    )
    return nr_mgr._format_result(result, data.hostname)

@mcp.tool("get_network_instances")
async def get_network_instances(data: NetworkInstancesModel):
    """Get a list of network instances (e.g., VRFs)."""
    logger.info(f"[Tool] get_network_instances called for {data.hostname}")
    host = nr_mgr.nr.filter(name=data.hostname)
    if not host.inventory.hosts:
        return {"host": data.hostname, "success": False, "error_type": "InventoryError", "result": f"Host '{data.hostname}' not found."}

    from nornir_napalm.plugins.tasks import napalm_get
    result = host.run(
        task=napalm_get,
        getters=["network_instances"],
        name=data.name,
        raise_on_error=False
    )
    return nr_mgr._format_result(result, data.hostname)

@mcp.tool("ping")
async def ping(data: PingModel):
    """Execute a ping command from the device to a specified destination."""
    logger.info(f"[Tool] ping called for {data.hostname} to {data.destination}")
    host = nr_mgr.nr.filter(name=data.hostname)
    if not host.inventory.hosts:
        return {"host": data.hostname, "success": False, "error_type": "InventoryError", "result": f"Host '{data.hostname}' not found."}

    from nornir_napalm.plugins.tasks import napalm_ping
    result = host.run(
        task=napalm_ping,
        dest=data.destination,
        source=data.source,
        ttl=data.ttl,
        timeout=data.timeout,
        size=data.size,
        count=data.count,
        vrf=data.vrf,
        name=f"Ping {data.destination} from {data.hostname}",
        raise_on_error=False
    )
    return nr_mgr._format_result(result, data.hostname)

@mcp.tool("traceroute")
async def traceroute(data: TracerouteModel):
    """Execute a traceroute command from the device to a specified destination."""
    logger.info(f"[Tool] traceroute called for {data.hostname} to {data.destination}")
    host = nr_mgr.nr.filter(name=data.hostname)
    if not host.inventory.hosts:
        return {"host": data.hostname, "success": False, "error_type": "InventoryError", "result": f"Host '{data.hostname}' not found."}

    from nornir_napalm.plugins.tasks import napalm_traceroute
    result = host.run(
        task=napalm_traceroute,
        dest=data.destination,
        source=data.source,
        ttl=data.ttl,
        timeout=data.timeout,
        vrf=data.vrf,
        name=f"Traceroute to {data.destination} from {data.hostname}",
        raise_on_error=False
    )
    return nr_mgr._format_result(result, data.hostname)

@mcp.tool("send_command")
async def send_command(data: SendCommandModel):
    """Send a validated, read-only command to a device."""
    logger.info(f"[Tool] send_command called for {data.hostname} with command: '{data.command}'")
    return await nr_mgr.send_command(data.hostname, data.command)

@mcp.tool("list_all_hosts")
async def list_all_hosts():
    """List all hosts in the Nornir inventory."""
    logger.info("[Tool] list_all_hosts called")
    return nr_mgr.list_hosts()

# --- SSE Endpoint for Streaming Updates ---
@mcp.resource("sse://updates")
async def device_updates():
    """Stream device updates using Server-Sent Events (SSE)."""
    logger.info("[Resource] device_updates accessed")

    async def event_generator():
        while True:
            yield {
                "event": "heartbeat",
                "data": {
                    "timestamp": asyncio.get_event_loop().time(),
                    "status": "ok"
                }
            }
            await asyncio.sleep(15)

    return EventSourceResponse(event_generator())

if __name__ == "__main__":
    logger.info("[Setup] Starting Nornir MCP server...")
    mcp.run(transport='sse', host='0.0.0.0', port=8000)