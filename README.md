# n8n MCP Server (Python)

Control n8n workflows from Claude Desktop via the Model Context Protocol.

---

## Background

I run automation pipelines for clients at [Tech Bridge Consulting](https://techbridgeconsulting.com) — invoice processing, property data aggregation, lead scoring — all built in n8n. Switching between Claude and the n8n UI to trigger or inspect those workflows added unnecessary friction. This server removes that context switch: Claude can list, inspect, and run workflows directly from a conversation.

A TypeScript implementation already exists in the community. This is the Python-native alternative — no Node.js required, built on [FastMCP](https://github.com/jlowin/fastmcp) and `httpx`.

---

## Architecture

```
Claude Desktop    Claude Code CLI
     │                  │
     └──────┬───────────┘
            │  stdio (MCP protocol)
            ▼
  n8n MCP Server (main.py)
            │
            │  HTTP + X-N8N-API-KEY
            ▼
       n8n REST API
   (self-hosted or cloud)
```

---

## Tools

| Tool | Parameters | Description |
|---|---|---|
| `list_workflows` | `active` (optional bool) | List all workflows. Filter by active/inactive status. |
| `get_workflow` | `workflow_id` | Return the full definition of a workflow — nodes, connections, settings. |
| `create_workflow` | `name`, `nodes` (optional list) | Create a new workflow. Nodes default to an empty workflow if omitted. |
| `delete_workflow` | `workflow_id` | Permanently delete a workflow. Returns the deleted object. |
| `execute_workflow` | `workflow_id`, `data` (optional dict) | Trigger an immediate workflow run. Pass input data to the trigger node. |
| `activate_workflow` | `workflow_id` | Activate a workflow so its trigger starts firing. |
| `deactivate_workflow` | `workflow_id` | Deactivate a workflow so its trigger stops firing. |
| `list_executions` | `workflow_id`, `status`, `limit` (all optional) | Return execution history. Status: `success` `error` `waiting` `running`. Default limit: 20. |
| `get_execution` | `execution_id` | Return full execution detail — node outputs, timing, error info. |
| `wait_for_execution` | `execution_id`, `timeout_seconds` (default 60) | Poll until an execution finishes and return the final result. Times out with a clear error if not done in time. |

**Notes on `execute_workflow`**

- **Output location.** The completed execution object returned by `wait_for_execution` contains node output data at `result["data"]["resultData"]["runData"]`, keyed by node name.
- **Execution data must be saved.** If `EXECUTIONS_DATA_SAVE_ON_SUCCESS=none` is set in your n8n environment, the `data` field will be empty even on a successful run. The n8n default is to save execution data, so this only applies if the setting has been explicitly changed.
- **Manual trigger workflows only.** The `/run` endpoint works with workflows that use a manual trigger node. Workflows triggered by a webhook must be called via their webhook URL — the `/run` API endpoint will not fire them.

---

## Requirements

- Python 3.10+
- A running n8n instance (self-hosted or cloud)
- An n8n API key — generate one at **Settings > API** in the n8n UI

---

## Installation

```bash
git clone https://github.com/DerJams/n8n-mcp-server-python.git
cd n8n-mcp-server-python
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install mcp httpx python-dotenv
```

Copy the environment template and fill in your values:

```bash
cp .env.example .env
```

```env
N8N_API_URL=http://localhost:5678/api/v1
N8N_API_KEY=your_api_key_here
```

---

## Configure Claude Desktop

Add an entry to `claude_desktop_config.json`:

**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`  
**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "n8n": {
      "command": "C:/path/to/n8n-mcp-server-python/.venv/Scripts/python.exe",
      "args": ["C:/path/to/n8n-mcp-server-python/main.py"]
    }
  }
}
```

Restart Claude Desktop. The n8n tools will appear in the tool list.

For Claude Code, add the server via `/mcp add` or directly in `.claude/settings.json` under `mcpServers`.

---

## Project structure

```
main.py          # MCP server and all five tool definitions
test_api.py      # Script to verify n8n API connectivity before connecting Claude
start-n8n.bat    # Convenience script to start n8n on Windows
.env.example     # Environment variable template
```
