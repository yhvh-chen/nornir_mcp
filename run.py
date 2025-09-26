import sys
import argparse
import os
from importlib import import_module
import anyio  # The original script used anyio, so we will too.


async def start_server(server, host, port):
    """
    Finds and awaits the specific async run method on the server object.
    """
    # This is the specific method the original run.py was designed to find
    # for the 'streamable-http' transport.
    run_fn = getattr(server, "run_streamable_http_async", None)

    if not callable(run_fn):
        # Fallback to the generic .run() if the async one doesn't exist,
        # which will likely fail or bind to localhost, but it's a last resort.
        generic_run = getattr(server, "run", None)
        if callable(generic_run):
            print(
                "Warning: 'run_streamable_http_async' not found. Falling back to generic '.run()'. "
                "Server may not bind to the correct host."
            )
            return generic_run(transport="streamable-http")
        else:
            raise RuntimeError(
                "The 'server' object has no 'run_streamable_http_async' or 'run' method."
            )

    print(f"Starting FastMCP async server on http://{host}:{port}")
    await run_fn()


def main():
    """
    Parses arguments and starts the server using an async runner.
    """
    parser = argparse.ArgumentParser(description="Run Nornir MCP server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind the server to.")
    parser.add_argument(
        "--port", type=int, default=8000, help="Port to run the server on."
    )
    args = parser.parse_args()

    # Set environment variables for the server module
    os.environ["MCP_HOST"] = args.host
    os.environ["MCP_PORT"] = str(args.port)

    try:
        mod = import_module("server")
    except ImportError as e:
        print(f"Error: Failed to import the 'server.py' module: {e}", file=sys.stderr)
        sys.exit(1)

    server = getattr(mod, "server", None)
    if server is None:
        raise RuntimeError("A 'server' object was not found in the 'server.py' module.")

    try:
        anyio.run(start_server, server, args.host, args.port)
    except KeyboardInterrupt:
        print("\nServer stopped.")
    except Exception as e:
        print(f"An error occurred while trying to run the server: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
