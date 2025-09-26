#!/usr/bin/env python3
"""Prompt definitions for the Nornir MCP server.

Drop your own prompt functions in this file. Any callable whose name
starts with "prompt_" will be automatically registered with the MCP
instance when `register_prompts(mcp)` is called from `server.py`.

Each prompt function should have a signature matching the inputs you
expect from the LLM and should return a List[Message] (the same shape
used by the MCP prompt decorators).
"""
from typing import List
from mcp.server.fastmcp.prompts.base import Message


def prompt_troubleshoot_network_issue(symptom: str, device_name: str) -> List[Message]:
    """A default troubleshooting prompt. Users can edit or add more
    prompt_* functions in this file.
    """
    return [
        {
            "role": "system",
            "content": (
                "You are a senior network engineer. Your task is to troubleshoot and diagnose network issues based on the provided symptom. "
                "Follow a systematic approach. ALWAYS call `list_all_hosts` first to discover available devices. "
                "Use the 'name' field from that output as the 'device_name' parameter for all subsequent tool calls. "
                "Before running deeper commands, clearly state your assumptions."
            ),
        },
        {
            "role": "user",
            "content": f"I observed the following symptom on the device named `{device_name}`: '{symptom}'. Please start the troubleshooting process.",
        },
    ]


def prompt_troubleshoot_bgp(device_name: str, neighbor_ip: str) -> List[Message]:
    """A prompt to troubleshoot a BGP peering session on a Cisco device."""
    return [
        {
            "role": "system",
            "content": (
                "You are a senior network engineer specializing in BGP. Your goal is to troubleshoot a BGP session. "
                "Follow a logical workflow. Start by checking the overall BGP summary, then inspect the specific neighbor, and finally check received and advertised routes. "
                "Use the following commands as a guide on the specified device: "
                "1. `show ip bgp summary` to check the neighbor state. "
                "2. `show ip bgp neighbor {neighbor_ip}` to get detailed information about the session. "
                "3. `show ip bgp neighbor {neighbor_ip} received-routes` to verify prefixes being received. "
                "4. `show running-config | section router bgp` to check the BGP configuration. "
                "Analyze the output of each command to determine the next step. Conclude with a diagnosis and recommended fix."
            ),
        },
        {
            "role": "user",
            "content": f"The BGP session with neighbor `{neighbor_ip}` on device `{device_name}` is not establishing or is flapping. Please investigate.",
        },
    ]


def prompt_troubleshoot_interface(
    device_name: str, interface_name: str
) -> List[Message]:
    """A prompt to troubleshoot a specific interface on a Cisco device."""
    return [
        {
            "role": "system",
            "content": (
                "You are a senior network engineer troubleshooting a problematic network interface. "
                "Your task is to identify the root cause of an interface issue on a Cisco device. "
                "Begin by checking the interface status and protocol state. Then, examine for any errors, review the configuration, and check logs. "
                "Use these commands as your primary toolkit on the specified device: "
                "1. `show ip interface brief` to get a quick overview of all interface statuses. "
                "2. `show interfaces {interface_name}` to check the detailed status, line protocol, and input/output rates. "
                "3. `show interfaces {interface_name} counters errors` to check for specific hardware or protocol errors. "
                "4. `show running-config interface {interface_name}` to validate the configuration. "
                "Based on your findings, provide a clear diagnosis and suggest a solution."
            ),
        },
        {
            "role": "user",
            "content": f"Users are reporting connectivity issues through interface `{interface_name}` on device `{device_name}`. Please find the cause of the problem.",
        },
    ]


def register_prompts(mcp) -> None:
    """Register all prompt_* callables in this module with the given MCP instance.

    The registration uses `mcp.prompt()(callable)` for each matching object.
    """
    import inspect

    # Iterate over module globals and register functions prefixed with `prompt_`
    for name, obj in list(globals().items()):
        if not name.startswith("prompt_"):
            continue
        if not callable(obj):
            continue
        try:
            # Use the mcp.prompt decorator to register the prompt function
            mcp.prompt()(obj)
        except Exception:
            # Keep things robust: log to stdout if registration fails
            # We avoid importing the server logger to prevent circular imports.
            import traceback

            print(f"Failed to register prompt '{name}':")
            traceback.print_exc()
