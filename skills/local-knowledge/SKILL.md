---
name: local-knowledge
description: Start, stop, restart, or check the user's offline Knowledge MCP service on this Windows machine. Use for requests such as "start local knowledge", "stop local knowledge", or "is local knowledge running", referring to the Wikipedia and World Bank grounding service connected to Open WebUI.
---

# Local Knowledge

Operate the existing offline Knowledge MCP service. Interpret "local knowledge" as this service in this user's setup.

## Installation

- Project: `C:\Users\weiji\LocalLLM\knowledge-mcp`
- Python: `C:\Users\weiji\LocalLLM\knowledge-mcp\.venv\Scripts\python.exe`
- MCP endpoint: `http://127.0.0.1:8766/mcp`
- Open WebUI: `http://127.0.0.1:8080`
- Model preset: **Offline Knowledge (Qwen3.8)**
- WebUI tool ID: `server:mcp:offline_knowledge`
- Private source backup: `https://github.com/weijianzhg/offline-knowledge-mcp`

Use the shell tool with the project as its working directory. This service is independent of Ollama and Open WebUI. A lifecycle request concerns the Knowledge MCP process; if the user asks for the whole local AI stack, handle that broader scope separately.

## Start

Run:

```powershell
& 'C:\Users\weiji\LocalLLM\knowledge-mcp\Start-KnowledgeMCP.ps1'
```

The script starts a hidden background process or identifies an already-running instance. Verify with the MCP probe below. Report that the service is ready and identify the Open WebUI preset. If it is already healthy, leave it running.

## Stop

Run:

```powershell
& 'C:\Users\weiji\LocalLLM\knowledge-mcp\Stop-KnowledgeMCP.ps1'
Get-NetTCPConnection -LocalPort 8766 -State Listen -ErrorAction SilentlyContinue
```

Confirm no Knowledge MCP listener remains before reporting it stopped. The script checks the recorded process identity and handles the Windows virtual-environment launcher and its child interpreter. Never stop all Python processes: Open WebUI also uses Python. Stopping this service leaves the datasets, models, chats, Ollama, and Open WebUI intact.

For "restart local knowledge", stop, verify, then start and probe.

## Status and health verification

A listening port alone does not prove this is the correct service. Use this read-only probe, which discovers the installed sources without loading an LLM or downloading data:

```powershell
$knowledgeProbe = @"
import asyncio, json
from mcp import Client
async def main():
    async with Client('http://127.0.0.1:8766/mcp', read_timeout_seconds=10) as client:
        result = await client.call_tool('list_sources')
        if result.is_error:
            raise RuntimeError('Knowledge catalog tool failed')
        catalog = result.structured_content
        print(json.dumps({'status': 'ready', 'protocol': client.protocol_version,
                          'offline': catalog['offline'],
                          'sources': [s['name'] for s in catalog['sources']]}))
asyncio.run(asyncio.wait_for(main(), timeout=15))
"@
$knowledgeProbe | & 'C:\Users\weiji\LocalLLM\knowledge-mcp\.venv\Scripts\python.exe' -
```

For a status-only request, report the observed state; do not start a stopped service. If the probe fails, check the listener and the service logs before deciding whether it is stopped or unhealthy.

## Troubleshooting and boundaries

- Logs: `logs\server.err.log`, `logs\server.out.log`; launcher PID: `logs\server.pid`, all under the project directory.
- If the scripts report an occupied port or a mismatched/stale PID, inspect `Win32_Process` command lines and parent relationships. Do not terminate an unrelated process or report success based solely on the script's message.
- Missing project/runtime/database: inspect the project `README.md` and explain the missing component. A start/stop request does not call for reinstalling software, rebuilding datasets, or cloning another copy automatically.
- Normal lifecycle operations need no GitHub access, data refresh, inference test, or credential read. The existing MCP registration persists in Open WebUI; do not rerun `Connect-OpenWebUI.ps1` unless repairing that integration is actually needed.
- The server binds to loopback. Preserve that address. No automatic startup or synchronization schedule is installed.
- For an explicit data-update or expansion request, read the project `README.md` for the import commands and `source-manifest.json` for the starter collection. Keep that work separate from start/stop operations.

## Maintain this skill

The installed skill lives at `C:\Users\weiji\.codex\skills\local-knowledge`. Its version-controlled copy is `skills\local-knowledge` in the project. Keep both copies consistent when changing the skill. Follow the user's scope for any GitHub push; routine lifecycle requests do not require a commit.
