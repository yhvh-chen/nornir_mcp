[![MseeP.ai Security Assessment Badge](https://mseep.net/pr/yhvh-chen-nornir-mcp-badge.png)](https://mseep.ai/app/yhvh-chen-nornir-mcp)

# 🌐 Nornir MCP Server

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A [FastMCP](https://github.com/fastmcp/fastmcp) server providing network automation tools powered by [Nornir](https://github.com/nornir-automation/nornir) and [NAPALM](https://github.com/napalm-automation/napalm).

This server acts as a bridge, exposing Nornir/NAPALM network operations as MCP (Massively Concurrent Processing) tools, making them easily accessible from compatible MCP clients (like the FastMCP Web UI).

## ✨ Key Features

* Leverages Nornir for inventory management and concurrent task execution against network devices.
* Uses NAPALM for multi-vendor device interaction (information gathering, command execution).
* Built with FastMCP for seamless integration with MCP clients using various transports (SSE in this configuration).
* Containerized with Docker 🐳 for easy setup and deployment.
* Uses [`uv`](https://github.com/astral-sh/uv) for fast Python dependency management within the container ⚡.

## 🔧 Prerequisites

Before you begin, ensure you have the following installed:

* [Docker](https://docs.docker.com/get-docker/)
* [Docker Compose](https://docs.docker.com/compose/install/) (Usually included with Docker Desktop)

## ⚙️ Configuration

Before running the server, you **must** configure your network inventory and device credentials:

1.  Navigate to the `conf/` directory in the project.
2.  **Edit `hosts.yaml`**: Define your network devices. Specify their management IP/hostname, platform (e.g., `ios`, `junos`, `eos`), credentials (if not using defaults), and assign them to groups if desired.
3.  **Edit `groups.yaml`**: Define device groups with shared properties (like platform or connection options). Settings here can override defaults.
4.  **Edit `defaults.yaml`**: Set default credentials (`username`, `password`) and connection options (like NAPALM `secret` for enable passwords or default `platform`).
    * **⚠️ Important Security Note:** The default configuration uses plaintext credentials in YAML files. This is suitable for testing/lab environments. For production, **strongly consider** using Nornir's built-in secrets management features (e.g., environment variables, HashiCorp Vault plugin) to avoid storing sensitive information directly in configuration files. Modify `nornir_ops.py` and your configuration if you implement a secrets provider.
5.  **Review `config.yaml`**: Ensure the inventory file paths (`host_file`, `group_file`, `defaults_file`) point correctly to the files within the `conf/` directory (they should by default). Adjust runner options (`num_workers`) if needed.

## ▶️ Running the Server

Once configured, you can easily run the server using Docker Compose:

1.  Ensure you have configured the `conf/` directory as described above.
2.  Open a terminal or command prompt in the project's root directory (the same directory as the `Dockerfile` and `docker-compose.yml` files).
3.  Run the following command:
    ```bash
    docker-compose up --build -d
    ```
    * The `--build` flag tells Docker Compose to build the image based on the `Dockerfile` the first time or if any project files (like `.py` files or `pyproject.toml`) have changed.
    * This command will start the Nornir MCP server in a Docker container.
4.  The server logs will be displayed in your terminal. By default, it should be accessible on port `8000` of your host machine (localhost).
5.  To stop the server, press `Ctrl+C` in the terminal where `docker-compose` is running. To remove the container afterwards, run `docker-compose down`.

## 🔌 Adding to MCP Client

To use the tools provided by this server in an MCP client (like the official [FastMCP Web UI](https://github.com/fastmcp/fastmcp-webui) or other compatible clients):

1.  Make sure the Nornir MCP server is running (using `docker-compose up`).
2.  Open your MCP client application.
3.  Find the option to add or manage MCP Server connections.
4.  Add a new connection with the following details:
    * **Server URL**: Since this server uses the SSE (Server-Sent Events) transport and runs on port 8000 by default, the URL will be:
        * `http://localhost:8000/sse`
        * *(If your Docker host has a different IP address accessible by the client, replace `localhost` with that IP, e.g., `http://192.168.1.100:8000/sse`)*
    * **Connection Name**: Give it a descriptive name, for example, `Nornir Lab Server`.
5.  Save and connect to the newly added server.
6.  The MCP client should discover the `Nornir_MCP` service and list all the available tools (like `get_facts`, `send_command`, etc.). You can now use these tools via the client interface! 🎉

## Dify DSL Examples
1. Nornir MCP.yml  - A simple example to chat with your devices.
2. Device Check.yml - An example to run Device Assessment Report.

## 🛠️ Available Tools & Resources

Once connected via an MCP client, the following tools (under the "Nornir_MCP" service name) should typically be available:

* **Inventory:**
    * `list_all_hosts`: Lists devices configured in your Nornir inventory (`conf/hosts.yaml`).
* **NAPALM Getters:** (Retrieve information)
    * `get_facts`
    * `get_interfaces`
    * `get_interfaces_ip`
    * `get_interfaces_counters`
    * `get_config` (with `retrieve` option: running, startup, candidate)
    * `get_arp_table`
    * `get_mac_address_table`
    * `get_users`
    * `get_vlans`
    * `get_snmp_information`
    * `get_bgp_neighbors`
    * *(Availability depends on device platform and NAPALM driver support)*
* **Execution:**
    * `send_command`: Send a single, read-only command to a device and get the output.
* **Streaming Resource:**
    * `sse://updates`: Provides a simple heartbeat event stream. (Can be subscribed to by clients supporting SSE resources).

## 📄 License

This project is licensed under the MIT License.

## 🙌 Contributing

Contributions, issues, and feature requests are welcome! Please feel free to submit them via the project's repository.