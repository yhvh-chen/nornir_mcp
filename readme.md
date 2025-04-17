# Nornir MCP Server

A Model Context Protocol (MCP) server for network automation using Nornir and NAPALM.

## Features

- SSE-based data streaming
- Docker containerization
- Persistent configuration via volume mounts
- NAPALM getters for network device information
- Nornir inventory management
- Command execution on network devices
- Environment variable-based authentication

## Prerequisites

- Python 3.10+
- Docker and Docker Compose (for containerized deployment)
- Network devices accessible via SSH

## Installation

### Local Development

1. Create a virtual environment and install dependencies:

```bash
# Using uv (recommended)
uv venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e .

# Or using pip
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e .
```

2. Configure your network devices in the `conf` directory:
   - `hosts.yaml`: Define your network devices
   - `groups.yaml`: Define device groups with shared attributes
   - `defaults.yaml`: Set default values for all devices
   - `config.yaml`: Configure Nornir settings

3. Set up environment variables in `.env` file:

```
NR_USER=your_username
NR_PASS=your_password
NR_ENABLE_PASSWORD=your_enable_password
```

4. Run the MCP server:

```bash
python server.py
```

### Docker Deployment

1. Configure your network devices in the `conf` directory as described above.

2. Set up environment variables in `.env` file.

3. Build and run the Docker container:

```bash
docker-compose up -d
```

## Available MCP Tools

### NAPALM Getters

- `get_facts(hostname)`: Get device facts
- `get_environment(hostname)`: Get device environment information
- `get_config(hostname)`: Get device configuration
- `get_alive(hostname)`: Check if device is alive
- `get_arp_table(hostname)`: Get device ARP table
- `get_bgp_neighbors(hostname)`: Get device BGP neighbors
- `get_interfaces(hostname)`: Get device interfaces
- `get_interfaces_counters(hostname)`: Get device interface counters
- `get_interfaces_ip(hostname)`: Get device interface IP addresses
- `get_mac_address_table(hostname)`: Get device MAC address table
- `get_traceroute(hostname, destination)`: Get traceroute results

### Inventory Management

- `list_all_hosts()`: List all hosts in the inventory
- `list_hosts_in_group(group)`: List all hosts in a specific group
- `get_host_by_name(name)`: Get host information by name
- `get_host_by_hostname(hostname)`: Get host information by hostname

### Command Execution

- `send_command(hostname, command)`: Send a command to a device

## SSE Streaming

The server provides an SSE endpoint at `/updates` for streaming real-time updates.

## Configuration Files

### hosts.yaml

```yaml
router1:
  hostname: 192.168.1.1
  platform: ios
  groups:
    - cisco_ios
```

### groups.yaml

```yaml
cisco_ios:
  platform: ios
  connection_options:
    napalm:
      extras:
        optional_args:
          transport: ssh
          secret: "{{ env.get('NR_ENABLE_PASSWORD', '') }}"
```

### defaults.yaml

```yaml
username: "{{ env.get('NR_USER', '') }}"
password: "{{ env.get('NR_PASS', '') }}"
```

## License

MIT
