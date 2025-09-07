# nornir_ops.py
import logging
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import yaml
from nornir import InitNornir
from nornir.core import Nornir
from nornir.core.inventory import Host
from nornir.core.task import Result, Task
from nornir_napalm.plugins.tasks import napalm_get
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CommandValidator:
    """Handles validation of commands against a configurable blacklist."""

    def __init__(self, blacklist_file: Path):
        self.blacklist = self._load_blacklist(blacklist_file)

    def _load_blacklist(self, file_path: Path) -> Dict[str, List[str]]:
        """Loads the command blacklist from a YAML file."""
        default_blacklist = {"exact_commands": [], "keywords": [], "disallowed_patterns": []}
        if not file_path.exists():
            logger.warning(f"Blacklist file not found at '{file_path}'. Command validation will be limited.")
            return default_blacklist
        try:
            with open(file_path, "r") as f:
                data = yaml.safe_load(f)
                # Normalize keys and ensure all expected keys are present
                normalized_data = {k.lower(): [str(item).lower() for item in v] for k, v in data.items()}
                # Merge with defaults to ensure all keys exist
                default_blacklist.update(normalized_data)
                logger.info(f"Command blacklist loaded successfully from '{file_path}'.")
                return default_blacklist
        except (yaml.YAMLError, IOError) as e:
            logger.error(f"Failed to load or parse blacklist file '{file_path}': {e}", exc_info=True)
            return default_blacklist

    def validate(self, command: str) -> Optional[str]:
        """
        Validates a command against the blacklist.

        Returns:
            An error message string if the command is invalid, otherwise None.
        """
        command_lower = command.lower().strip()

        # 1. Check for disallowed patterns (e.g., pipes, redirects)
        for pattern in self.blacklist.get("disallowed_patterns", []):
            if pattern in command:
                return f"Command contains disallowed pattern: '{pattern}'"

        # 2. Check for exact blacklisted commands
        if command_lower in self.blacklist.get("exact_commands", []):
            return "Command is explicitly blacklisted."

        # 3. Check for blacklisted keywords
        # Use word boundaries to avoid matching substrings within valid commands (e.g., 'ip' in 'show ip interface')
        for keyword in self.blacklist.get("keywords", []):
            if re.search(rf"\b{re.escape(keyword)}\b", command_lower):
                return f"Command contains blacklisted keyword: '{keyword}'"

        return None

class NornirManager:
    """Encapsulates Nornir operations for network device management."""

    def __init__(self, config_file: str = "conf/config.yaml"):
        """Initialize Nornir and the command validator."""
        logger.info(f"[Setup] Initializing Nornir manager with config: {config_file}...")
        self.nr: Optional[Nornir] = None
        try:
            self.nr = InitNornir(config_file=config_file)
            logger.info("[Setup] Nornir initialized successfully!")
        except Exception as e:
            logger.error(f"[Error] Failed to initialize Nornir from {config_file}: {e}", exc_info=True)
            raise

        blacklist_path = Path("conf/blacklist.yaml")
        self.command_validator = CommandValidator(blacklist_path)


    def _validate_host_exists(self, hostname: str) -> bool:
        """Check if a host exists in the inventory."""
        if not self.nr:
            logger.error("Nornir is not initialized. Cannot validate host.")
            return False
        if hostname not in self.nr.inventory.hosts:
            logger.warning(f"Host '{hostname}' not found in Nornir inventory.")
            return False
        return True

    async def _run_host_task(self, hostname: str, task_func: Callable[..., Result], task_name: str, **task_kwargs) -> Dict[str, Any]:
        """
        Runs a single task on a specific host and formats the result.
        Handles host validation, task execution, and unified result formatting.
        """
        if not self.nr:
            return {"host": hostname, "success": False, "error_type": "NornirInitError", "result": "NornirManager not initialized."}

        if not self._validate_host_exists(hostname):
            return {"host": hostname, "success": False, "error_type": "InventoryError", "result": f"Host '{hostname}' not found."}

        logger.debug(f"Running task '{task_name}' on host '{hostname}' with args: {task_kwargs}")
        target_inventory = self.nr.filter(name=hostname)

        try:
            result = target_inventory.run(
                task=task_func,
                name=task_name,
                raise_on_error=False,
                **task_kwargs
            )
            return self._format_result(result, hostname)
        except Exception as e:
            logger.error(f"[Error] Unexpected error during task run for {task_name} on {hostname}: {e}", exc_info=True)
            return {"host": hostname, "success": False, "error_type": type(e).__name__, "result": f"Unexpected error: {e}"}
        finally:
            # FIX: Ensure connections for the target host are closed after every task.
            # This prevents a single failed connection from poisoning the connection pool
            # for all subsequent tasks.
            logger.debug(f"Closing connections for host '{hostname}' after task run.")
            target_inventory.close_connections()

    def _format_result(self, result, hostname: str) -> Dict[str, Any]:
        """Formats a Nornir AggregatedResult for a single host, handling errors gracefully."""
        if not result or hostname not in result:
            logger.error(f"Host '{hostname}' not found in Nornir result keys: {list(result.keys())}")
            return {"host": hostname, "success": False, "error_type": "ResultMissingHost", "result": "No result found for host."}

        host_result = result[hostname]

        if host_result.failed:
            error_msg = "Task failed with an unknown error."
            error_type = "TaskFailed"
            if host_result and host_result[0].exception:
                exception = host_result[0].exception
                error_type = type(exception).__name__
                error_msg = str(exception)
                logger.warning(f"Task '{host_result[0].name}' failed on {hostname}: {error_type} - {error_msg}")
            return {"host": hostname, "success": False, "error_type": error_type, "result": error_msg}
        else:
            if not host_result: # Should not happen if failed is False, but for safety
                return {"host": hostname, "success": False, "error_type": "ResultFormatError", "result": "Task succeeded but result was empty."}
            final_result = host_result[0].result
            logger.info(f"Task '{host_result[0].name}' succeeded on {hostname}.")
            return {"host": hostname, "success": True, "result": final_result}

    async def get_napalm_data(self, hostname: str, getter: str) -> Dict[str, Any]:
        """Get data using a specific NAPALM getter."""
        logger.info(f"[API] Attempting to get '{getter}' from host: {hostname}")
        return await self._run_host_task(
            hostname=hostname,
            task_func=napalm_get,
            task_name=f"Get '{getter}' for {hostname}",
            getters=[getter]
        )

    async def send_command(self, hostname: str, command: str) -> Dict[str, Any]:
        """Send a validated, read-only command to a device using NAPALM CLI."""
        logger.info(f"[API] Attempting to send command '{command}' to host: {hostname}")

        # Validate the command before sending it
        validation_error = self.command_validator.validate(command)
        if validation_error:
            logger.warning(f"Command validation failed for '{command}': {validation_error}")
            return {"host": hostname, "success": False, "error_type": "CommandValidationError", "result": validation_error}

        return await self._run_host_task(
            hostname=hostname,
            task_func=self._send_command_task,
            task_name=f"Execute command on {hostname}",
            command=command
        )

    @staticmethod
    def _send_command_task(task: Task, command: str) -> Result:
        """Nornir Task to send a command via NAPALM CLI."""
        try:
            connection = task.host.get_connection("napalm", task.nornir.config)
            output_dict = connection.cli([command])
            command_output = output_dict.get(command)

            if command_output is None:
                raise ValueError(f"No output received from device for command: {command}")

            return Result(host=task.host, result=command_output)
        except Exception:
            logger.debug(f"Exception within _send_command_task for {task.host.name}", exc_info=True)
            raise

    def list_hosts(self) -> List[Dict[str, Any]]:
        """Lists hosts from the Nornir inventory, filtering sensitive data."""
        if not self.nr:
            logger.error("Nornir is not initialized. Cannot list hosts.")
            return []

        logger.info("Listing all hosts in inventory")
        hosts_info = []
        sensitive_keys = {'password', 'secret'}

        for name, host_obj in self.nr.inventory.hosts.items():
            safe_data = {k: v for k, v in (host_obj.data or {}).items() if k not in sensitive_keys}
            hosts_info.append({
                "name": name,
                "hostname": host_obj.hostname,
                "platform": host_obj.platform,
                "groups": list(host_obj.groups) if host_obj.groups else [],
                "data": safe_data
            })
        return hosts_info