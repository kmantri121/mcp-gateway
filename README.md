# mcp-gateway

A gateway that sits between AI agents and the MCP servers they use, so every tool call is authenticated, permission-checked, rate-limited, and logged. See [PLAN.md](PLAN.md) for the full plan.

## Status

Week 1 is in progress. The notes MCP server (the first upstream) runs in Docker. The gateway itself is not built yet.

| Component | State |
| --- | --- |
| Notes MCP server (`servers/notes`) | Running in Docker, tested with MCP Inspector |
| Open-source reference MCP server | Not started |
| Gateway | Not started |
| PostgreSQL schema | Not started |

## Requirements

- Docker with Compose (developed on OrbStack)
- [uv](https://docs.astral.sh/uv/) for local Python work (Python 3.12, MCP Python SDK pinned to `mcp==2.3.0`)

## Run it

```bash
docker compose up -d --build
```

The notes server listens on `http://localhost:8001/mcp` (Streamable HTTP), bound to the Mac's loopback only. Stop it with `docker compose down`.

### Test with MCP Inspector

```bash
npx @modelcontextprotocol/inspector
```

Open the link it prints, set **Transport Type** to **Streamable HTTP** and **URL** to `http://localhost:8001/mcp`, then **Connect** and open **Tools**.

Without the browser:

```bash
npx @modelcontextprotocol/inspector --cli http://localhost:8001/mcp --transport http --method tools/list
```

## Notes MCP server

A small upstream for the gateway to route calls to.

| Tool | Input | Returns |
| --- | --- | --- |
| `add_note` | `text`: 1 to 2000 characters, not blank | The saved note: `id`, `text`, `created_at` |
| `search_notes` | `query`: 1 to 200 characters; `limit`: 1 to 50, default 10 | Notes containing the query, case-insensitive, newest first |

- Notes are kept in memory and are lost when the container restarts.
- Invalid input returns a tool error (`isError: true`) with the reason, rather than crashing the server.
- Requests whose `Host` or `Origin` header is not local are rejected with HTTP 421 (DNS-rebinding protection).
- `GET /health` returns `{"status": "ok"}` and backs the container's healthcheck.
- The container runs as a non-root user with a 256 MB memory limit.

## Layout

```
compose.yaml              Services for local development
servers/notes/server.py   Notes MCP server
servers/notes/Dockerfile  Two-stage image: uv installs the locked deps, slim runtime runs them
pyproject.toml, uv.lock   One locked set of Python dependencies for the whole repo
PLAN.md                   The 4-week plan and progress
```

## License

MIT, see [LICENSE](LICENSE).
