"""MCP stdio and authenticated Streamable HTTP entry points."""

import asyncio
import contextlib
import hmac
import json
import logging
import os
import sys
import time

import httpx
import jsonschema
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import CallToolResult, TextContent
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from .plane import Plane, PlaneError
from .schema import BY_NAME, TOOLS

log = logging.getLogger("sikku")


def build_server(client, base_url, workspace):
    server = Server(
        "sikku",
        version="0.1.0",
        instructions="Plane tickets: list_issues to search, get_issue for detail, save_issue to create/update. Use project names and ticket identifiers. Results are bounded; follow cursors/offsets when present.",
    )

    @server.list_tools()
    async def list_tools():
        return TOOLS

    @server.call_tool(validate_input=False)
    async def call_tool(name, arguments):
        started = time.monotonic()
        failed = False
        try:
            if name not in BY_NAME:
                raise PlaneError("unknown_tool", "Unknown tool.")
            jsonschema.validate(
                arguments,
                BY_NAME[name].inputSchema,
                format_checker=jsonschema.FormatChecker(),
            )
            result = await Plane(client, base_url, workspace).dispatch(name, arguments)
        except jsonschema.ValidationError as exc:
            failed = True
            result = {
                "error": "invalid_arguments",
                "message": "Input does not match the tool schema.",
                "field": ".".join(str(x) for x in exc.absolute_path),
                "rule": exc.validator,
            }
        except PlaneError as exc:
            failed = True
            result = exc.payload
        except Exception:  # noqa: BLE001 -- protocol boundary must not expose secrets
            failed = True
            result = {
                "error": "internal_error",
                "message": "Unexpected response from Plane. Read back writes before retrying.",
            }
            log.error("Unexpected error in %s", name)  # no data/credential logging
        encoded = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
        log.info(
            json.dumps(
                {
                    "tool": name,
                    "error": failed,
                    "duration_ms": round((time.monotonic() - started) * 1000),
                    "response_bytes": len(encoded.encode()),
                }
            )
        )
        # One representation only: structuredContent would duplicate the payload in some hosts.
        return CallToolResult(
            content=[TextContent(type="text", text=encoded)], isError=failed
        )

    return server


def config():
    base = os.environ["PLANE_BASE_URL"].rstrip("/")
    if not base.startswith("https://") and not base.startswith("http://127.0.0.1:"):
        raise ValueError("PLANE_BASE_URL must use HTTPS (except local testing)")
    return base, os.environ["PLANE_WORKSPACE_SLUG"], os.environ["PLANE_API_KEY"]


def create_app():
    base, workspace, key = config()
    token = os.environ["SIKKU_MCP_TOKEN"]
    if len(token) < 32:
        raise ValueError("SIKKU_MCP_TOKEN must have at least 32 characters")
    client = httpx.AsyncClient(
        headers={"x-api-key": key}, timeout=30, follow_redirects=False
    )
    server = build_server(client, base, workspace)
    allowed = os.getenv("SIKKU_ALLOWED_HOSTS", "localhost:*,127.0.0.1:*").split(",")
    manager = StreamableHTTPSessionManager(
        server,
        json_response=True,
        stateless=True,
        security_settings=TransportSecuritySettings(
            allowed_hosts=allowed, allowed_origins=[]
        ),
    )

    @contextlib.asynccontextmanager
    async def lifespan(app):
        async with client, manager.run():
            yield

    async def health(request):
        return JSONResponse({"status": "ok", "version": "0.1.0"})

    async def authenticated(scope, receive, send):
        headers = dict(scope.get("headers", []))
        auth = headers.get(b"authorization", b"")
        if not hmac.compare_digest(auth, ("Bearer " + token).encode()):
            await JSONResponse({"error": "unauthorized"}, status_code=401)(
                scope, receive, send
            )
            return
        try:
            declared_length = int(headers.get(b"content-length", b"0"))
        except ValueError:
            await JSONResponse({"error": "invalid_content_length"}, status_code=400)(
                scope, receive, send
            )
            return
        if declared_length > 1048576:
            await JSONResponse({"error": "request_too_large"}, status_code=413)(
                scope, receive, send
            )
            return
        messages, received = [], 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            received += len(message.get("body", b""))
            if received > 1048576:
                await JSONResponse({"error": "request_too_large"}, status_code=413)(
                    scope, receive, send
                )
                return
            messages.append(message)
            if not message.get("more_body", False):
                break

        async def replay():
            return messages.pop(0) if messages else await receive()

        await manager.handle_request(scope, replay, send)

    # Mount handles ASGI directly; /mcp/ avoids redirecting authenticated POSTs.
    return Starlette(
        routes=[
            Route("/healthz", health),
            Route("/mcp/healthz", health),
            Mount("/mcp", app=authenticated),
        ],
        lifespan=lifespan,
    )


async def stdio():
    base, workspace, key = config()
    async with httpx.AsyncClient(
        headers={"x-api-key": key}, timeout=30, follow_redirects=False
    ) as client:
        server = build_server(client, base, workspace)
        async with stdio_server() as (read, write):
            await server.run(read, write, server.create_initialization_options())


def main():
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
    log.setLevel(logging.INFO)
    if "--http" in sys.argv:
        import uvicorn

        uvicorn.run(
            create_app(),
            host="0.0.0.0",
            port=int(os.getenv("PORT", "8000")),
            access_log=False,
        )
    else:
        asyncio.run(stdio())


if __name__ == "__main__":
    main()
