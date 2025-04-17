#!/usr/bin/env python3
# nornir_ops.py
import logging
from nornir import InitNornir
from nornir.core.task import Result, Task
from nornir_napalm.plugins.tasks import napalm_get
import os

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
            logger.info("[Setup] Nornir initialized successfully")
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
        Send a command to a device.
        
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

    def _send_command_task(self, task: Task, command: str) -> Result:
        """
        Task to send a command to a device.
        
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
            result: The Nornir result
            hostname: The hostname
            
        Returns:
            Formatted result dictionary
        """
        if hostname not in result:
            return {"host": hostname, "success": False, "result": "No result returned"}
            
        return {
            "host": hostname,
            "success": not result[hostname].failed,
            "result": result[hostname].result if not result[hostname].failed else str(result[hostname].exception)
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
