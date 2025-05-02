# nornir_ops.py
import logging
from typing import Any, Dict, List, Optional, Callable

from nornir import InitNornir
from nornir.core import Nornir
from nornir.core.inventory import Host
from nornir.core.task import Result, Task
# from nornir.core.exceptions import NornirExecutionError # Keep for InitNornir
# from nornir.core.processor import Processor # Required if using Processors later
# from nornir.core.runners import Runner # Required if implementing custom runners
from nornir_napalm.plugins.tasks import napalm_get # Keep napalm_get

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Define a standard error response structure
ERROR_RESPONSE = Dict[str, Any]

class NornirManager:
    """Encapsulates Nornir operations for network device management."""

    def __init__(self, config_file: str = "conf_test/config.yaml"):
        """Initialize Nornir."""
        logger.info("[Setup] Initializing Nornir manager with config: %s...", config_file)
        self.nr: Optional[Nornir] = None # Initialize as None
        try:
            self.nr = InitNornir(config_file=config_file)
            logger.info("[Setup] Nornir initialized successfully!")
        except Exception as e:
            logger.error(f"[Error] Failed to initialize Nornir from {config_file}: {str(e)}", exc_info=True)
            # You might want to prevent the manager from being used if init fails
            # raise or ensure subsequent calls check self.nr is not None
            raise # Re-raise the exception to signal failed initialization

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

        Handles host validation, task execution with raise_on_error=False,
        and result formatting.
        """
        if not self.nr:
             logger.error("Nornir is not initialized. Cannot run task.")
             return {"host": hostname, "success": False, "error_type": "NornirInitError", "result": "NornirManager not initialized."}

        if not self._validate_host_exists(hostname):
            return {"host": hostname, "success": False, "error_type": "InventoryError", "result": f"Host '{hostname}' not found."}

        logger.debug(f"Running task '{task_name}' on host '{hostname}' with args: {task_kwargs}")

        target_inventory = self.nr.filter(name=hostname)
        if not target_inventory.inventory.hosts:
            logger.error(f"Host '{hostname}' not found in Nornir inventory after filtering.")
            return {"host": hostname, "success": False, "error_type": "InventoryError", "result": f"Host '{hostname}' not found after filtering."}
        try:
            # Run the task on the specific host, preventing errors from stopping execution
            result = target_inventory.run(
                task=task_func,
                name=task_name,
                raise_on_error=False, # Let Nornir handle task exceptions internally
                **task_kwargs # Pass through specific arguments for the task
            )
            # Format the result (handles both success and failure stored in the result object)
            return self._format_result(result, hostname)

        except Exception as e:
            # Catch unexpected errors outside the Nornir task execution itself
            logger.error(f"[Error] Unexpected error during task run setup/processing for {task_name} on {hostname}: {type(e).__name__}", exc_info=True)
            return {"host": hostname, "success": False, "error_type": type(e).__name__, "result": f"Unexpected error during task processing: {str(e)}"}


    def _format_result(self, result, hostname: str) -> Dict[str, Any]:
        """Formats Nornir AggregatedResult for a single host. Handles raise_on_error=False."""
        if not result: # Check if the result object itself is empty/None
             logger.error(f"Received empty result object for host '{hostname}'.")
             return {"host": hostname, "success": False, "error_type": "EmptyResult", "result": "Nornir returned an empty result object."}

        if hostname not in result:
            # This might happen if the filter somehow failed silently or the host died before processing
            logger.error(f"Host '{hostname}' not found in Nornir AggregatedResult keys: {list(result.keys())}")
            # Check if maybe the run failed globally?
            failed_globally = getattr(result, 'failed', False) # Nornir results might have a global fail status
            if failed_globally:
                 logger.error("The Nornir run failed globally.")
                 # Potentially extract global error if available
            return {"host": hostname, "success": False, "error_type": "ResultMissingHost", "result": f"No result found for host '{hostname}' in the returned AggregatedResult."}

        host_result = result[hostname] # This is a MultiResult for the specific host

        # Check the MultiResult's failed status first
        if host_result.failed:
            error_type = "TaskFailed"
            error_msg = f"Task failed for host '{hostname}'."
            exception_details = None

            # Try to extract details from the actual task Result within MultiResult
            if not host_result: # Check if MultiResult is empty
                 logger.warning(f"Host {hostname} result marked failed, but no task results found in MultiResult.")
                 error_msg = f"Nornir indicated failure for {hostname}, but no specific task details could be extracted."
            else:
                 try:
                     # Assume one task per .run() call as per _run_host_task structure
                     task_result = host_result[0]
                     if task_result.exception:
                         exception_details = task_result.exception
                         error_type = type(exception_details).__name__
                         error_msg = str(exception_details)
                         # Log the specific error type and message
                         logger.warning(f"Task '{task_result.name}' failed on {hostname}: {error_type} - {error_msg}", exc_info=False) # Log traceback only if needed via higher level debug settings
                         # Special handling for known non-critical 'failures'
                         if isinstance(exception_details, NotImplementedError):
                             error_msg = f"Feature not implemented for '{task_result.name}' on this device/platform."
                     elif task_result.result is not None: # Check if failure info is in the result field
                         error_msg = f"Task '{task_result.name}' failed. Result/Error: {task_result.result}"
                         logger.warning(error_msg)
                     else: # Fallback if no exception or result data
                         error_msg = f"Task '{task_result.name}' failed on host {hostname} with no specific exception or result data."
                         logger.warning(error_msg)

                 except IndexError:
                     logger.error(f"Host {hostname} result marked failed, but could not access task result index 0 in MultiResult.")
                     error_msg = f"Nornir indicated failure for {hostname}, but specific task details could not be extracted due to result structure."
                 except Exception as e: # Catch any other error during formatting
                     logger.error(f"Error formatting failed result for {hostname}: {e}", exc_info=True)
                     error_type = "ResultFormatError"
                     error_msg = f"Could not format the failure result: {str(e)}"

            return {"host": hostname, "success": False, "error_type": error_type, "result": error_msg}
        else:
            # Task succeeded (host_result.failed is False)
            if not host_result: # Should not happen if failed is False, but check anyway
                 logger.error(f"Result formatting error: No task results found for successful run on host {hostname}.")
                 return {"host": hostname, "success": False, "error_type": "ResultFormatError", "result": "Task completed successfully but MultiResult was empty."}

            try:
                # Assume one task per .run() call
                final_result = host_result[0].result
                logger.info(f"Task '{host_result[0].name}' succeeded on {hostname}.")
                return {"host": hostname, "success": True, "result": final_result}
            except IndexError:
                 logger.error(f"Result formatting error: No task result found at index 0 for successful run on host {hostname}.")
                 return {"host": hostname, "success": False, "error_type": "ResultFormatError", "result": "Task completed successfully but returned no result data structure."}
            except Exception as e:
                 logger.error(f"Unexpected error processing successful result for {hostname}: {e}", exc_info=True)
                 return {"host": hostname, "success": False, "error_type": "ResultProcessingError", "result": f"Error processing successful result: {str(e)}"}


    async def get_napalm_data(self, hostname: str, getter: str) -> Dict[str, Any]:
        """Get data using a specific NAPALM getter."""
        logger.info(f"[API] Attempting to get '{getter}' from host: {hostname}")
        return await self._run_host_task(
            hostname=hostname,
            task_func=napalm_get,
            task_name=f"Get '{getter}' for {hostname}",
            getters=[getter] # Pass 'getters' list as expected by napalm_get
        )

    async def send_command(self, hostname: str, command: str) -> Dict[str, Any]:
        """Send a command to a device using NAPALM CLI."""
        logger.info(f"[API] Attempting to send command '{command}' to host: {hostname}")
        return await self._run_host_task(
            hostname=hostname,
            task_func=self._send_command_task,
            task_name=f"Execute command on {hostname}",
            command=command # Pass 'command' as expected by _send_command_task
        )

    def _send_command_task(self, task: Task, command: str) -> Result:
        """
        Nornir Task to send a command via NAPALM CLI.
        This is called by _run_host_task. Errors are handled by raise_on_error=False.
        """
        try:
            # Get the NAPALM connection object
            connection = task.host.get_connection("napalm", task.nornir.config)
            # Execute the command
            output_dict = connection.cli([command]) # Returns {command: output}
            command_output = output_dict.get(command) # Extract output

            if command_output is None:
                # This indicates an issue with NAPALM's response format
                logger.error(f"NAPALM cli output for command '{command}' on host {task.host.name} did not contain the command key. Output: {output_dict}")
                raise ValueError(f"No output received in dict for command: {command}")

            return Result(
                host=task.host,
                result=command_output # Return only the command's output string
            )
        except Exception as e:
             # Catching exceptions here allows Nornir (with raise_on_error=False)
             # to record the specific error for this task. Re-raise it so Nornir catches it.
             logger.debug(f"Exception within _send_command_task for {task.host.name}: {e}")
             raise # Nornir will catch this and store it since raise_on_error=False

    # --- Inventory Information Methods ---

    def list_hosts(self, group: str = None) -> List[Dict[str, Any]]:
        """Lists hosts from the Nornir inventory, optionally filtered by group."""
        if not self.nr:
             logger.error("Nornir is not initialized. Cannot list hosts.")
             return []

        hosts_info = []
        target_inventory = self.nr.inventory

        if group:
            # Ensure group filtering is robust
            try:
                target_inventory = target_inventory.filter(filter_func=lambda h, g=group: g in h.groups)
                logger.info(f"Listing hosts filtered by group: {group}")
            except Exception as e:
                logger.error(f"Failed to filter inventory by group '{group}': {e}", exc_info=True)
                return [] # Return empty list on filter error
        else:
            logger.info("Listing all hosts in inventory")

        # Filter out sensitive keys when preparing the host list
        sensitive_keys = {'password', 'secret'}

        for name, host_obj in target_inventory.hosts.items():
            # Ensure host_obj.data exists and is a dict before filtering
            safe_data = {}
            if isinstance(host_obj.data, dict):
                 safe_data = {k: v for k, v in host_obj.data.items() if k not in sensitive_keys}

            hosts_info.append({
                "name": name,
                "hostname": host_obj.hostname,
                "platform": host_obj.platform,
                "groups": list(host_obj.groups) if host_obj.groups else [],
                "data": safe_data
            })

        logger.info(f"Found {len(hosts_info)} hosts matching criteria.")
        return hosts_info


    def get_host_info(self, name: Optional[str] = None, hostname: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Retrieves detailed information about a specific host from the inventory."""
        if not self.nr:
             logger.error("Nornir is not initialized. Cannot get host info.")
             return None
        if not name and not hostname:
            logger.warning("get_host_info called without name or hostname.")
            return None

        host_obj: Optional[Host] = None
        search_key = ""
        found_name = name # Keep track of the host's inventory name

        if name:
            search_key = f"name '{name}'"
            host_obj = self.nr.inventory.hosts.get(name)
        elif hostname:
            search_key = f"hostname '{hostname}'"
            # More efficient lookup if hostname is unique and indexed, but iterating is safe
            for h_name, h_obj in self.nr.inventory.hosts.items():
                if h_obj.hostname == hostname:
                    host_obj = h_obj
                    found_name = h_name # Update name based on hostname lookup
                    break
        # No need for else block due to the initial check

        if host_obj:
            logger.info(f"Found host info for {search_key}")
            # Explicitly list desired fields, avoid leaking unexpected data
            # Do NOT include password/secret here
            host_data = {
                "name": found_name,
                "hostname": host_obj.hostname,
                "platform": host_obj.platform,
                "username": host_obj.username, # Might be None if using defaults
                "groups": list(host_obj.groups) if host_obj.groups else [],
                "port": host_obj.port, # Might be None if using defaults
                "connection_options": dict(host_obj.connection_options), # Be cautious about sensitive data within options
                "data": dict(host_obj.data) # Already filtered in list_hosts, but filter again for safety? Usually data is non-sensitive.
            }
            # Consider further filtering connection_options/data if needed
            return host_data
        else:
            logger.warning(f"Host not found in inventory using {search_key}")
            return None