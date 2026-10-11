"""Notes MCP server: a small upstream for the gateway to route tool calls to.

Notes are kept in memory, so they are lost when the process restarts.
"""

import os
from datetime import UTC, datetime
from typing import Annotated

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import BaseModel, Field
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class Note(BaseModel):
    id: int
    text: str
    created_at: datetime


server = MCPServer(
    "notes",
    version="0.1.0",
    instructions="Store short text notes with add_note and find them with search_notes.",
)

# Tools are async, so they all run on the one event loop thread. Neither tool
# awaits while touching this list, so no lock is needed. Sync tools would run
#  in a thread pool, and two add_note calls could then hand out the same id.
_notes: list[Note] = []


@server.tool()
async def add_note(
    text: Annotated[str, Field(description="The note text.", min_length=1, max_length=2000)],
) -> Note:
    """Save a note and return it with its new id."""
    text = text.strip()
    if not text:
        raise ToolError("Note text must not be blank.")
    note = Note(id=len(_notes) + 1, text=text, created_at=datetime.now(UTC))
    _notes.append(note)
    return note


@server.tool()
async def search_notes(
    query: Annotated[str, Field(description="Text to look for, case-insensitive.", min_length=1, max_length=200)],
    limit: Annotated[int, Field(description="Maximum number of notes to return.", ge=1, le=50)] = 10,
) -> list[Note]:
    """Return notes containing the query, newest first."""
    needle = query.strip().casefold()
    if not needle:
        raise ToolError("Query must not be blank.")
    matches = [note for note in reversed(_notes) if needle in note.text.casefold()]
    return matches[:limit]


@server.custom_route("/health", methods=["GET"])
async def health(request: Request) -> Response:
    return JSONResponse({"status": "ok"})


if __name__ == "__main__":
    server.run(
        "streamable-http",
        # Loopback by default; the container sets HOST=0.0.0.0 so Docker can forward traffic in.
        host=os.environ.get("HOST", "127.0.0.1"),
        port=8000,
        # Binding to 0.0.0.0 turns off the SDK's automatic DNS-rebinding protection,
        # so turn it back on explicitly: reject requests whose Host or Origin isn't local.
        transport_security=TransportSecuritySettings(
            allowed_hosts=["localhost:*", "127.0.0.1:*"],
            allowed_origins=["http://localhost:*", "http://127.0.0.1:*"],
        ),
    )
