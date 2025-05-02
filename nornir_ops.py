# nornir_ops.py
import logging
# import os # Removed os import as it's no longer needed for env vars
from nornir import InitNornir
from nornir.core.task import Result, Task
from nornir_napalm.plugins.tasks import napalm_get, napalm_configure # Import napalm_configure

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("nornir_ops")

class NornirManager:
    """Encapsulates Nornir operations for network device management."""

    def __init__(self):
        """Initialize Nornir with SimpleInventory configuration."""
        logger.info("[Setup] Initializing Nornir manager...")
        try:
            self.nr = InitNornir(
                runner={
                    "plugin": "threaded",
                    "options": {
                        "num_workers": 100,
                    },
                },
                inventory={
                    "plugin": "SimpleInventory",
                    "options": {
                        "host_file": "conf/hosts.yaml",
                        "group_file": "conf/groups.yaml",
                        "defaults_file": "conf/defaults.yaml",
                    },
                },
            )
            logger.info("[Setup] Nornir initialized successfully!")
        except Exception as e:
            logger.error(f"[Error] Failed to initialize Nornir: {str(e)}")
            raise

    async def get_napalm_data(self, hostname: str, getter: str):
        """
        Get data from a device using NAPALM getter.

        Args:
            hostname: The name of the host to query
            getter: The NAPALM getter to use (facts, interfaces, etc.)

        Returns:
            Formatted result dictionary
        """
        logger.info(f"[API] Getting {getter} from {hostname}")
        try:
            host = self.nr.filter(name=hostname)
            if not host.inventory.hosts:
                return {"host": hostname, "success": False, "result": f"Host {hostname} not found"}

            result = host.run(
                task=napalm_get,
                getters=[getter],
                name=f"Get {getter}"
            )
            return self._format_result(result, hostname)
        except Exception as e:
            logger.error(f"[Error] Failed to get {getter} from {hostname}: {str(e)}")
            return {"host": hostname, "success": False, "result": str(e)}

    async def send_command(self, hostname: str, command: str):
        """
        Send a command to a device (typically show commands).

        Args:
            hostname: The name of the host to send the command to
            command: The command to send

        Returns:
            Formatted result dictionary
        """
        logger.info(f"[API] Sending command '{command}' to {hostname}")
        try:
            host = self.nr.filter(name=hostname)
            if not host.inventory.hosts:
                return {"host": hostname, "success": False, "result": f"Host {hostname} not found"}

            result = host.run(
                task=self._send_command_task,
                command=command,
                name="Execute command"
            )
            return self._format_result(result, hostname)
        except Exception as e:
            logger.error(f"[Error] Failed to send command to {hostname}: {str(e)}")
            return {"host": hostname, "success": False, "result": str(e)}

    async def send_config(self, hostname: str, config_commands: list[str]):
        """
        Send configuration commands to a device using NAPALM.

        Args:
            hostname: The name of the host to configure.
            config_commands: A list of configuration commands (strings).

        Returns:
            Formatted result dictionary indicating success/failure and diff (if any).
        """
        logger.info(f"[API] Sending configuration to {hostname}")
        logger.debug(f"Config commands for {hostname}:\n" + "\n".join(config_commands))

        try:
            host = self.nr.filter(name=hostname)
            if not host.inventory.hosts:
                return {"host": hostname, "success": False, "result": f"Host {hostname} not found"}

            # Join the list of commands into a single multi-line string
            config_string = "\n".join(config_commands)

            result = host.run(
                task=napalm_configure,
                configuration=config_string, # Pass the configuration string
                replace=False, # Use merge strategy (default)
                name="Configure device"
            )
            # napalm_configure returns diff, commit status etc.
            return self._format_result(result, hostname)
        except Exception as e:
            logger.error(f"[Error] Failed to send configuration to {hostname}: {str(e)}")
            return {"host": hostname, "success": False, "result": str(e)}

    def _send_command_task(self, task: Task, command: str) -> Result:
        """
        Task to send a command to a device using NAPALM CLI.

        Args:
            task: The Nornir task
            command: The command to send

        Returns:
            Result object with command output
        """
        connection = task.host.get_connection("napalm", task.nornir.config)
        return Result(
            host=task.host,
            result=connection.cli([command])
        )

    def _format_result(self, result, hostname):
        """
        Format the result of a Nornir task.

        Args:
            result: The Nornir result AggregatedResult object
            hostname: The hostname string

        Returns:
            Formatted result dictionary
        """
        if hostname not in result:
            return {"host": hostname, "success": False, "result": "No result returned"}

        host_result = result[hostname] # This is a MultiResult object

        # Check if any task within the MultiResult failed
        failed = any(r.failed for r in host_result)
        # Combine results or exceptions from all tasks for this host
        if failed:
            # Collect all exceptions
            errors = [str(r.exception) for r in host_result if r.failed]
            final_result = "; ".join(errors)
        else:
            # Collect all successful results
            # For single tasks like napalm_get, there's usually one result
            # For napalm_configure, the result contains the diff
            results = [r.result for r in host_result if not r.failed]
            # Handle cases where result might not be easily stringifiable (e.g., complex dicts)
            try:
                final_result = results[0] if len(results) == 1 else results
            except Exception:
                 final_result = str(results) # Fallback to string representation


        return {
            "host": hostname,
            "success": not failed,
            "result": final_result,
        }

    def list_hosts(self, group=None):
        """
        List all hosts or hosts in a specific group.

        Args:
            group: Optional group name to filter hosts

        Returns:
            List of host information dictionaries
        """
        hosts = []
        filtered_hosts = self.nr.inventory.hosts

        if group:
            filtered_hosts = {name: host for name, host in filtered_hosts.items()
                             if group in host.groups}

        for name, host in filtered_hosts.items():
            hosts.append({
                "name": name,
                "platform": host.platform,
                "hostname": host.hostname,
                "groups": list(host.groups)
            })

        return hosts

    def get_host_info(self, name=None, hostname=None):
        """
        Get information about a specific host by name or hostname.

        Args:
            name: The name of the host in the inventory
            hostname: The hostname (IP/FQDN) of the host

        Returns:
            Host information dictionary or None if not found
        """
        if name:
            if name in self.nr.inventory.hosts:
                host = self.nr.inventory.hosts[name]
                return {
                    "name": name,
                    "platform": host.platform,
                    "hostname": host.hostname,
                    "groups": list(host.groups),
                    "data": dict(host.items())
                }
        elif hostname:
            for name, host in self.nr.inventory.hosts.items():
                if host.hostname == hostname:
                    return {
                        "name": name,
                        "platform": host.platform,
                        "hostname": host.hostname,
                        "groups": list(host.groups),
                        "data": dict(host.items())
                    }

        return None