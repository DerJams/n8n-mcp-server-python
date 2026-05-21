# n8n MCP Server

An MCP (Model Context Protocol) server that gives Claude direct access to an n8n instance. It wraps the n8n REST API so Claude can list, inspect, and trigger workflows without leaving the conversation.

## Why I built this

I use n8n extensively in my consulting work to automate client processes. I wanted Claude to be able to trigger and manage those workflows directly — so instead of switching between tools, I can describe what I need in a conversation and have Claude act on it. This server is the bridge.

## How it works

The server uses [FastMCP](https://github.com/jlowin/fastmcp) to expose n8n API calls as MCP tools. When Claude is connected to this server, it can call those tools to read workflow definitions, check execution history, or fire off a workflow run — all authenticated against your n8n instance via API key.

At runtime, `main.py` starts an MCP server over stdio. An MCP-compatible client (Claude Desktop, Claude Code, etc.) connects to it and gains access to the five tools below.

## Tools

| Tool | Description |
|---|---|
| `list_workflows` | Returns all workflows. Accepts an optional `active` boolean to filter by active/inactive status. |
| `get_workflow` | Returns the full definition of a single workflow by ID, including its nodes, connections, and settings. |
| `execute_workflow` | Triggers an immediate run of a workflow. Accepts an optional `data` dict to pass input to the trigger node. |
| `list_executions` | Returns execution history. Filterable by `workflow_id`, `status` (`success`, `error`, `waiting`, `running`), and `limit` (default 20). |
| `get_execution` | Returns the full detail of a single execution by ID, including per-node data and any error output. |

## Requirements

- Python 3.10+
- A running n8n instance (self-hosted or cloud)
- An n8n API key (Settings > API in the n8n UI)

## Installation

```bash
git clone https://github.com/DerJams/n8n-mcp-server-python.git
cd n8n-mcp-server-python
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate  # macOS/Linux
pip install mcp httpx python-dotenv
```

Copy `.env.example` to `.env` and fill in your values:

```env
N8N_API_URL=http://localhost:5678/api/v1
N8N_API_KEY=your_api_key_here
```

## Running the server

```bash
python main.py
```

The server communicates over stdio and is intended to be launched by an MCP client, not run directly in a terminal. To connect it to Claude Desktop, add an entry to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "n8n": {
      "command": "C:/path/to/.venv/Scripts/python.exe",
      "args": ["C:/path/to/n8n-mcp-server-python/main.py"]
    }
  }
}
```

For Claude Code, add it via `/mcp add` or directly in `.claude/settings.json` under `mcpServers`.

## Project structure

```
main.py          # MCP server and all tool definitions
test_api.py      # Quick script to verify n8n API connectivity
start-n8n.bat    # Convenience script to start n8n on Windows
.env.example     # Environment variable template
```
