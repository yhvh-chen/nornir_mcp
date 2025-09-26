# 🌐 Nornir MCP Server

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A [FastMCP](https://github.com/fastmcp/fastmcp) server providing network automation tools powered by [Nornir](https://github.com/nornir-automation/nornir) and [NAPALM](https://github.com/napalm-automation/napalm).

This server acts as a bridge, exposing Nornir/NAPALM network operations as MCP (Massively Concurrent Processing) tools, making them easily accessible from compatible MCP clients.

## ✨ Key Features

* **Concurrent & Multi-vendor**: Leverages Nornir for inventory management and concurrent task execution against network devices using NAPALM for multi-vendor support.
* **Expanded Toolset**: Provides over 20 tools, including a wide range of NAPALM getters (`get_facts`, `get_interfaces`), execution commands (`ping`, `traceroute`), and inventory management (`list_all_hosts`).
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
```

This command starts the Nornir MCP server in a Docker container, accessible on port `8000` of your host machine. The container now uses `run.py` as its entrypoint, which supports both development and production modes.

To run the server locally (without Docker), use:

```bash
python run.py --dev
```

or simply:

```bash
python run.py
```

This will start the server on 0.0.0.0:8000 using the new entrypoint logic.

## 🔌 How to connect an MCP client

This project exposes FastMCP over HTTP using the streamable-http transport. The server provides two useful endpoints:

- HTTP API endpoint:  http://<host>:<port>/mcp
- SSE endpoint (events): http://<host>:<port>/sse

Notes on transports and client setup:

- The MCP server itself is an HTTP application (FastAPI/Starlette) served by Uvicorn. You should connect MCP clients directly to the `/mcp` (primary) endpoints using a client that supports the streamable-http transport.
- You do NOT need to run this project in stdio mode for typical HTTP or SSE clients. Previously included instructions referencing running the server in "stdio mode" and proxying it with Supergateway were inaccurate for the normal usage of this repository.

Example MCP client JSON configuration (HTTP/streamable-http):

```json
{
  "name": "Nornir MCP (HTTP)",
  "url": "http://localhost:8000/mcp",
  "transport": "http"
}
```


## 🧠 Prompts (custom prompt functions)

This server supports registering custom prompt functions that return a list of messages (MCP Prompt format). Prompts let you predefine conversational inputs that MCP clients or LLM-driven agents can call as named prompts. The `FastMCP` API exposes a `@server.prompt()` decorator to register functions.

Key features:

- Register synchronous or async prompt functions using `@server.prompt()`.
- Optionally provide a `name`, `title`, and `description` to make prompts discoverable in MCP clients.
- Prompts can return structured messages including resource references (useful for returning file contents or inventory snippets).

How to add a prompt (example):

```python
@server.prompt(name="list-host-names", title="List Host Names", description="Return a short list of host names from inventory")
def prompt_list_hosts() -> list:
    hosts = nr_mgr.list_hosts()
    return [{"role": "user", "content": f"Available hosts: {', '.join(h['device_name'] for h in hosts)}"}]
```

Async example with a resource:

```python
@server.prompt()
async def show_topology() -> list:
    topo = await server.read_resource("resource://topology")
    return [{"role": "user", "content": {"type": "resource", "resource": topo}}]
```

Usage notes:

- After registering prompts, clients can discover them via the MCP `ListPrompts` request and call them by name.
- Keep prompt functions lightweight and deterministic; avoid long-running operations inside prompts. If you need data gathered from devices, consider registering a tool and calling it from the prompt or returning a short resource reference that the client can fetch.

Security:

- Prompts run inside the server process; do not perform unsafe file operations or execute untrusted code in prompt functions.


Quick start — Docker (recommended)

1) Build and run with docker-compose (from repo root):

```powershell
docker-compose up --build -d
```

This starts the server in the container and exposes it on port 8000 by default.

Quick start — Local

1) Create and activate a virtual environment.

```powershell
& .venv\Scripts\Activate.ps1
# or on Unix: python -m venv .venv; source .venv/bin/activate
```

2) Install runtime dependencies (example):

```powershell
pip install -U pip
pip install nornir==3.5.0 nornir-napalm mcp[cli]==1.15.0 sse-starlette
```

3) Run the server locally (binds to 0.0.0.0:8000 by default):

```powershell
python run.py
```

Or with `uv` (recommended when using the included runner):

```powershell
uv run .\run.py
```

If you need to change host/port use the `--host` and `--port` flags when running `run.py`.
```

Resources provided by the server
- `resource://inventory/hosts` — returns JSON array of hosts with sanitized fields (name, hostname, platform, groups, data). Sensitive keys such as `username`, `password`, and `secret` are removed.
- `resource://inventory/hosts/{keyword}` — same output filtered by a keyword (case-insensitive) that matches name, hostname, platform, group names, or data values.
- `resource://inventory/groups` — returns groups mapping (sanitized).
- `resource://topology` — parsed `resources/topology.json`.
- `resource://cisco_ios_commands` — parsed `resources/cisco_ios_commands.json`.

How to add your own resources
1. Edit `resources.py` and add a function named `resource_<name>` (e.g., `resource_my_tools`).
2. If your function needs the Nornir manager, accept a single parameter named `nr_mgr`.
3. Add an entry to `RESOURCE_MAP` if you want a custom URI; otherwise a default URI `resource://user/<name>` is used.

Example `resources.py` snippet

```python
def resource_my_static():
  return {"hello": "world"}

def resource_my_hosts(nr_mgr):
  # returns a JSON-serializable list of hosts
  return nr_mgr.list_hosts()
```

Security notes
- Inventory YAML files may contain credentials. For production, prefer secrets management (Vault, environment variables, or Nornir secrets plugins) over plaintext YAML.
- The server strips common sensitive keys (`username`, `password`, `secret`) from resources served via `resource://inventory/*`.

Contributing
- Open an issue or PR for changes. Keep changes small and include tests where appropriate.

License
- MIT
