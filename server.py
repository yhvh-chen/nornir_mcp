#!/usr/bin/env python3
# server.py
import logging
import asyncio
from typing import List # Import List for type hinting
from fastmcp import FastMCP
from nornir_ops import NornirManager #
from nornir_napalm.plugins.tasks import napalm_get #
from sse_starlette.sse import EventSourceResponse

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("nornir_mcp") # Main application logger

# Create an MCP server and Nornir Manager
mcp = FastMCP("Nornir_MCP") #
nr_mgr = NornirManager() #

# --- Helper Function to Register NAPALM Getters ---
def register_napalm_getter(getter_name: str):
    """
    Factory function to create and register an async MCP tool for a NAPALM getter.

    Args:
        getter_name: The name of the NAPALM getter (e.g., "get_facts").
    """
    # Sanitize getter_name slightly for docstring/logging if needed
    friendly_name = getter_name.replace("get_", "").replace("_", " ")

    async def getter_endpoint(hostname: str):
        """Dynamically generated endpoint for a NAPALM getter."""
        # This docstring will be replaced by the one set below
        logger.info(f"[Tool] {getter_name} called for {hostname}")
        return await nr_mgr.get_napalm_data(hostname, getter_name) #

    # Set correct name and docstring for FastMCP/FastAPI discovery
    getter_endpoint.__name__ = getter_name
    getter_endpoint.__doc__ = f"Get device {friendly_name} using NAPALM."

    # Register the dynamically created function with MCP
    mcp.tool(getter_name)(getter_endpoint)
    logger.debug(f"Registered NAPALM getter endpoint: {getter_name}")

# --- Register NAPALM Getter Endpoints ---
# List of standard NAPALM getters to create endpoints for
napalm_getters_to_register = [
    "get_facts",
    "get_vlans", # Note: Original code had get_environment mapped to get_vlans
    "get_users",
    "get_arp_table",
    "get_bgp_neighbors",
    "get_interfaces",
    "get_interfaces_counters",
    "get_interfaces_ip",
    "get_mac_address_table",
    "get_snmp_information",
    # Add other getters here if needed
]

for getter in napalm_getters_to_register:
    register_napalm_getter(getter)


# --- Specific Endpoints (Not covered by the generic getter) ---

@mcp.tool("get_config")
async def get_config(hostname: str, retrieve: str = "running"): #
    """Get device configuration using NAPALM (running, startup, or candidate).""" #
    logger.info(f"[Tool] get_config called for {hostname} (retrieve={retrieve})") #
    # napalm_get handles the 'retrieve' option via optional_args
    # We use the NornirManager instance directly here as it involves specific args
    host = nr_mgr.nr.filter(name=hostname) #
    if not host.inventory.hosts: #
        # Use the same format as NornirManager for consistency
        return {"host": hostname, "success": False, "error_type": "InventoryError", "result": f"Host '{hostname}' not found."}

    # Directly call run and format result, similar to original but ensuring consistency
    # Note: Consider if _format_result needs adjustment if napalm_get errors differ
    # when called this way vs. via get_napalm_data (depends on raise_on_error handling)
    result = host.run( #
        task=napalm_get, #
        getters=["config"], #
        retrieve=retrieve, # Pass retrieve option to napalm_get
        name=f"Get '{retrieve}' config for {hostname}", # Add a descriptive name
        raise_on_error=False # Maintain consistency with get_napalm_data
    )
    # Assuming _format_result can handle this structure
    return nr_mgr._format_result(result, hostname) #


# --- Command and Configuration execution endpoints ---
@mcp.tool("send_command")
async def send_command(hostname: str, command: str): #
    """Send a read-only command to a device.""" #
    logger.info(f"[Tool] send_command called for {hostname}: {command}") #
    return await nr_mgr.send_command(hostname, command) #

# --- Host inventory endpoints ---
@mcp.tool("list_all_hosts")
async def list_all_hosts(): #
    """List all hosts in the inventory.""" #
    logger.info("[Tool] list_all_hosts called") #
    return nr_mgr.list_hosts() #

# --- SSE endpoint for streaming updates ---
@mcp.resource("sse://updates")
async def device_updates(): #
    """Stream device updates using SSE.""" #
    logger.info("[Resource] device_updates accessed") #

    async def event_generator(): #
        while True: #
            # Simple heartbeat event
            yield { #
                "event": "heartbeat", #
                "data": { #
                    "timestamp": asyncio.get_event_loop().time(), #
                    "status": "ok" #
                }
            }
            await asyncio.sleep(10) #

    return EventSourceResponse(event_generator()) #

if __name__ == "__main__":
    logger.info("[Setup] Starting Nornir MCP server...") #
    # Ensure transport matches your deployment needs (e.g., 'sse', 'http')
    # The original code used 'sse', maintaining that here.
    mcp.run(transport='sse') #