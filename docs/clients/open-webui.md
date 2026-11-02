# Open WebUI

The knowledge server is independent of Open WebUI and its model provider. Any model with reliable tool calling can use it; no fixed Ollama model or preset is required. Complete [setup](../setup.md) and import data first.

## Local backend on the same machine

1. Start the server in a terminal using the venv Python: `python -m knowledge_mcp.server --transport streamable-http` (use the interpreter path from setup).
2. In Open WebUI's admin settings, open **Integrations → External Tool Servers → Add Connection**.
3. Choose **MCP (Streamable HTTP)**, set the URL to `http://127.0.0.1:8766/mcp`, and choose no authentication for this loopback service.
4. Save, select a model capable of native tool calling, and enable the knowledge tools for the model/chat. Use Native function calling where your version offers that setting.
5. Ask it to call `list_sources`, then search/read `eclipse`. Check the actual tool calls and returned citation.

Optional: paste the [shared grounding guidance](../agent-instructions.md) into the model's system instructions. Restart or refresh tool discovery after configuration changes. Keep the server terminal open, then stop with Ctrl+C when finished.

Native MCP requires Open WebUI v0.6.31+ and supports Streamable HTTP. Do not select OpenAPI or paste a stdio `mcpServers` object into that screen. See the [official integration guide](https://docs.openwebui.com/features/extensibility/mcp/) for current menu locations, permissions and model/tool troubleshooting.

## Docker and remote backends

The connection is made by the **Open WebUI backend**, not your browser. `127.0.0.1` inside a container points to that container, not your Mac/Windows host. This server deliberately has no public bind option or network authentication.

For a containerized setup, run the knowledge process in the same container/network namespace as Open WebUI, install its dependencies there, and mount the database/archive paths there. The loopback URL then works inside that environment. Re-register ZIM files if their paths differ. If using separate containers or a remote backend, provide an authenticated proxy or tunnel with appropriate access restrictions; simply changing the hostname does not establish a secure connection to this loopback-only server. This repository does not provision that topology.

An alternative for hosts that only accept OpenAPI is Open WebUI's [mcpo bridge](https://github.com/open-webui/mcpo), running alongside the backend and launching this server through stdio. That is an OpenAPI connection to the bridge, not a native MCP URL. Follow mcpo's authentication and deployment instructions.

Every user granted access to a shared tool server can potentially retrieve its installed data. Use a database containing only data appropriate for those users. A fully offline chat also needs a locally available model and an appropriately configured UI; this project's offline guarantee covers retrieval.

## Optional Windows helpers

`Connect-OpenWebUI.ps1` registers the default local endpoint through Open WebUI's API. Supply `-CredentialFile` for an explicitly created Windows DPAPI credential file; the default is the historical sibling `open-webui-credential.xml`. Add `-ModelId YOUR_INSTALLED_MODEL` only if you want it to create an optional preset. Existing presets are retained. Manual UI configuration above is the portable route and needs no credential file.

`Test-OpenWebUIGrounding.ps1 -PresetId YOUR_PRESET_ID` is an optional Windows diagnostic that creates test chats and runs inference for the starter Wikipedia/World Bank collection. It needs a compatible preset with the tools enabled. Neither helper is required for installation, and their WebUI API compatibility is separate from the MCP transport tests. Do not commit credential files, tokens or generated chats/reports.
