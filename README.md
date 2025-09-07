# 🌐 Nornir MCP Server

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A [FastMCP](https://github.com/fastmcp/fastmcp) server providing network automation tools powered by [Nornir](https://github.com/nornir-automation/nornir) and [NAPALM](https://github.com/napalm-automation/napalm).

This server acts as a bridge, exposing Nornir/NAPALM network operations as MCP (Massively Concurrent Processing) tools, making them easily accessible from compatible MCP clients.

## ✨ Key Features

* **Concurrent & Multi-vendor**: Leverages Nornir for inventory management and concurrent task execution against network devices using NAPALM for multi-vendor support.
* **Expanded Toolset**: Provides over 20 tools, including a wide range of NAPALM getters (`get_facts`, `get_interfaces`, `get_environment`), execution commands (`ping`, `traceroute`), and inventory management (`list_all_hosts`).
* **Robust Input Validation**: Uses **Pydantic** models to validate all incoming data for tools, ensuring type safety and preventing errors from invalid inputs.
* **Secure Command Execution**: Features a configurable **command blacklist** (`conf/blacklist.yaml`) to prevent accidental or malicious execution of dangerous commands like `reload` or `erase startup-config` via the `send_command` tool.
* **Containerized & Fast**: Containerized with Docker 🐳 for easy setup and uses [`uv`](https://github.com/astral-sh/uv) for lightning-fast Python dependency management within the container ⚡.

## 🔧 Prerequisites

Before you begin, ensure you have the following installed:

* [Docker](https://docs.docker.com/get-docker/)
* [Docker Compose](https://docs.docker.com/compose/install/) (Usually included with Docker Desktop)

## ⚙️ Configuration

Before running the server, you **must** configure your network inventory and device credentials:

1.  Navigate to the `conf/` directory in the project.
2.  **Edit `hosts.yaml`**: Define your network devices, including their management IP, platform, credentials, and groups.
3.  **Edit `groups.yaml`**: Define device groups with shared properties.
4.  **Edit `defaults.yaml`**: Set default credentials and connection options.
    * **⚠️ Important Security Note:** For production, strongly consider using Nornir's secrets management features to avoid storing plaintext credentials in YAML files.
5.  **Review `blacklist.yaml`**: Customize the list of blocked commands and patterns to fit your security policies.

## ▶️ Running the Server

Once configured, you can easily run the server using Docker Compose:

```bash
docker-compose up --build -d
````

This command starts the Nornir MCP server in a Docker container, accessible on port `8000` of your host machine.

## 🔌 Adding to MCP Client (SSE Mode)

To use the tools in an MCP client, you need to add the server as a **Server-Sent Events (SSE)** connection.

1.  Make sure the Nornir MCP server is running.
2.  Open your MCP client and find the option to add a new server connection.
3.  Select **SSE** as the transport/connection mode.
4.  Enter the server URL:
      * `http://localhost:8000/sse`
      * *(Replace `localhost` with your Docker host's IP if connecting from another machine)*
5.  Give the connection a descriptive name, like `Nornir Lab Server`.

### JSON Configuration Example

If your MCP client supports importing server configurations from JSON, you can use the following template:

```json
{
  "name": "Nornir Lab Server",
  "url": "http://localhost:8000/sse",
  "transport": "sse"
}
```

After connecting, the client will discover the `Nornir_MCP` service and all its available tools. 🎉

## 🛠️ Available Tools & Resources

Once connected, the following tools are available:

  * **Inventory:**
      * `list_all_hosts`: Lists all devices from your Nornir inventory.
  * **Execution:**
      * `send_command`: Securely send a single, read-only command.
      * `ping`: Execute a ping from a device.
      * `traceroute`: Execute a traceroute from a device.
  * **NAPALM Getters:** (A partial list)
      * `get_facts`
      * `get_environment`
      * `get_config` (running, startup, candidate)
      * `get_interfaces`, `get_interfaces_ip`, `get_interfaces_counters`
      * `get_arp_table`, `get_mac_address_table`
      * `get_bgp_config`, `get_bgp_neighbors`, `get_bgp_neighbors_detail`
      * `get_lldp_neighbors`, `get_lldp_neighbors_detail`
      * `is_alive`
  * **Streaming Resource:**
      * `sse://updates`: Provides a simple heartbeat event stream.

## 📄 License

This project is licensed under the MIT License.