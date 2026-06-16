"""Serveur MCP stdio — expose les tools du pipeline Zaynb."""

from __future__ import annotations

import json
import sys
from typing import Any, Dict, Optional

from src.mcp.tools_registry import list_mcp_tools
from src.mcp.bridge import MCPToolBridge


class ZaynbMCPServer:
    """Serveur MCP minimal (JSON-RPC lignes) pour intégration Cursor / agents."""

    PROTOCOL_VERSION = "2024-11-05"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.bridge = MCPToolBridge(config)
        self._handlers = {
            "initialize": self._handle_initialize,
            "tools/list": self._handle_tools_list,
            "tools/call": self._handle_tools_call,
        }

    def _handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "protocolVersion": self.PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "zaynb-pipeline", "version": "1.0.0"},
        }

    def _handle_tools_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {"tools": list_mcp_tools()}

    def _handle_tools_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        name = params.get("name", "")
        arguments = params.get("arguments") or {}
        text = self.bridge.call_tool(name, arguments)
        return {"content": [{"type": "text", "text": text}]}

    def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        req_id = request.get("id")
        method = request.get("method", "")
        params = request.get("params") or {}
        try:
            handler = self._handlers.get(method)
            if not handler:
                return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Unknown: {method}"}}
            result = handler(params)
            return {"jsonrpc": "2.0", "id": req_id, "result": result}
        except Exception as e:
            return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32000, "message": str(e)}}

    def serve_stdio(self) -> None:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            req = json.loads(line)
            resp = self.handle_request(req)
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()


def main() -> None:
    ZaynbMCPServer().serve_stdio()


if __name__ == "__main__":
    main()
