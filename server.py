#!/usr/bin/env python3
# server.py
import logging
import asyncio
from typing import List # Import List for type hinting
from fastmcp import FastMCP
from nornir_ops import NornirManager
from nornir_napalm.plugins.tasks import napalm_get
from sse_starlette.sse import EventSourceResponse



# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("nornir_mcp") # Main application logger

# Create an MCP server
mcp = FastMCP("Nornir_MCP")
nr_mgr = NornirManager()

# NAPALM getter endpoints
@mcp.tool("get_facts")
async def get_facts(hostname: str):
    """Get device facts using NAPALM."""
    logger.info(f"[Tool] get_facts called for {hostname}")
    return await nr_mgr.get_napalm_data(hostname, "facts")

@mcp.tool("get_environment")
async def get_environment(hostname: str):
    """Get device environment information using NAPALM."""
    logger.info(f"[Tool] get_environment called for {hostname}")
    return await nr_mgr.get_napalm_data(hostname, "environment")

@mcp.tool("get_config")
async def get_config(hostname: str, retrieve: str = "running"):
    """Get device configuration using NAPALM (running, startup, or candidate)."""
    logger.info(f"[Tool] get_config called for {hostname} (retrieve={retrieve})")
    # napalm_get handles the 'retrieve' option via optional_args
    host = nr_mgr.nr.filter(name=hostname)
    if not host.inventory.hosts:
        return {"host": hostname, "success": False, "result": f"Host {hostname} not found"}
    result = host.run(
        task=napalm_get,
        getters=["config"],
        retrieve=retrieve # Pass retrieve option to napalm_get
    )
    return nr_mgr._format_result(result, hostname)


@mcp.tool("get_alive")
async def get_alive(hostname: str):
    """Check if device is alive using NAPALM."""
    logger.info(f"[Tool] get_alive called for {hostname}")
    return await nr_mgr.get_napalm_data(hostname, "is_alive") # Correct getter is 'is_alive'

@mcp.tool("get_arp_table")
async def get_arp_table(hostname: str):
    """Get device ARP table using NAPALM."""
    logger.info(f"[Tool] get_arp_table called for {hostname}")
    return await nr_mgr.get_napalm_data(hostname, "arp_table")

@mcp.tool("get_bgp_neighbors")
async def get_bgp_neighbors(hostname: str):
    """Get device BGP neighbors using NAPALM."""
    logger.info(f"[Tool] get_bgp_neighbors called for {hostname}")
    return await nr_mgr.get_napalm_data(hostname, "bgp_neighbors")

@mcp.tool("get_interfaces")
async def get_interfaces(hostname: str):
    """Get device interfaces using NAPALM."""
    logger.info(f"[Tool] get_interfaces called for {hostname}")
    return await nr_mgr.get_napalm_data(hostname, "interfaces")

@mcp.tool("get_interfaces_counters")
async def get_interfaces_counters(hostname: str):
    """Get device interface counters using NAPALM."""
    logger.info(f"[Tool] get_interfaces_counters called for {hostname}")
    return await nr_mgr.get_napalm_data(hostname, "interfaces_counters")

@mcp.tool("get_interfaces_ip")
async def get_interfaces_ip(hostname: str):
    """Get device interface IP addresses using NAPALM."""
    logger.info(f"[Tool] get_interfaces_ip called for {hostname}")
    return await nr_mgr.get_napalm_data(hostname, "interfaces_ip")

@mcp.tool("get_mac_address_table")
async def get_mac_address_table(hostname: str):
    """Get device MAC address table using NAPALM."""
    logger.info(f"[Tool] get_mac_address_table called for {hostname}")
    return await nr_mgr.get_napalm_data(hostname, "mac_address_table")

@mcp.tool("get_traceroute")
async def get_traceroute(hostname: str, destination: str):
    """Get traceroute results using NAPALM."""
    logger.info(f"[Tool] get_traceroute called for {hostname} to {destination}")
    # For traceroute, we need to pass optional parameters directly to the task run
    host = nr_mgr.nr.filter(name=hostname)
    if not host.inventory.hosts:
        return {"host": hostname, "success": False, "result": f"Host {hostname} not found"}
    result = host.run(
        task=napalm_get,
        getters=["traceroute"],
        # Pass optional arguments for the specific getter
        getters_options={"traceroute": {"destination": destination}}
    )
    return nr_mgr._format_result(result, hostname)

# Host inventory endpoints
@mcp.tool("list_all_hosts")
async def list_all_hosts():
    """List all hosts in the inventory."""
    logger.info("[Tool] list_all_hosts called")
    return nr_mgr.list_hosts()

@mcp.tool("list_hosts_in_group")
async def list_hosts_in_group(group: str):
    """List all hosts in a specific group."""
    logger.info(f"[Tool] list_hosts_in_group called for {group}")
    return nr_mgr.list_hosts(group=group)

@mcp.tool("get_host_by_name")
async def get_host_by_name(name: str):
    """Get host information by name."""
    logger.info(f"[Tool] get_host_by_name called for {name}")
    return nr_mgr.get_host_info(name=name)

@mcp.tool("get_host_by_hostname")
async def get_host_by_hostname(hostname: str):
    """Get host information by hostname."""
    logger.info(f"[Tool] get_host_by_hostname called for {hostname}")
    return nr_mgr.get_host_info(hostname=hostname)

# Command and Configuration execution endpoints
@mcp.tool("send_command")
async def send_command(hostname: str, command: str):
    """Send a read-only command to a device."""
    logger.info(f"[Tool] send_command called for {hostname}: {command}")
    return await nr_mgr.send_command(hostname, command)

@mcp.tool("send_config")
async def send_config(hostname: str, config_commands: List[str]):
    """
    Send configuration commands to a device.
    Expects a JSON list of strings for config_commands.
    """
    logger.info(f"[Tool] send_config called for {hostname}")
    if not isinstance(config_commands, list):
         logger.error(f"[Tool] send_config failed for {hostname}: config_commands must be a list of strings.")
         return {"host": hostname, "success": False, "result": "Invalid input: config_commands must be a list of strings."}
    return await nr_mgr.send_config(hostname, config_commands)

# SSE endpoint for streaming updates
@mcp.resource("sse://updates")
async def device_updates():
    """Stream device updates using SSE."""
    logger.info("[Resource] device_updates accessed")

    async def event_generator():
        while True:
            # Simple heartbeat event
            yield {
                "event": "heartbeat",
                "data": {
                    "timestamp": asyncio.get_event_loop().time(),
                    "status": "ok"
                }
            }
            await asyncio.sleep(10)

    return EventSourceResponse(event_generator())

if __name__ == "__main__":
    logger.info("[Setup] Starting Nornir MCP server in HTTP mode for SSE")
    mcp.run(transport='sse')