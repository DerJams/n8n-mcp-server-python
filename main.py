import os
import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

N8N_API_URL = os.getenv("N8N_API_URL", "http://localhost:5678/api/v1")
N8N_API_KEY = os.getenv("N8N_API_KEY", "")

mcp = FastMCP("n8n-mcp-server")


def get_client() -> httpx.AsyncClient:
    base_url = N8N_API_URL.rstrip("/") + "/"
    return httpx.AsyncClient(
        base_url=base_url,
        headers={"X-N8N-API-KEY": N8N_API_KEY},
        timeout=30.0,
    )


@mcp.tool()
async def list_workflows(active: bool | None = None) -> dict:
    """List all workflows in n8n.

    Parameters:
        active: Optional filter. Pass True to return only active workflows,
                False for inactive ones, or omit to return all workflows.

    Returns a dict with a 'data' list of workflow objects, each containing
    id, name, active status, and metadata.
    """
    params = {}
    if active is not None:
        params["active"] = str(active).lower()
    async with get_client() as client:
        response = await client.get("workflows", params=params)
        response.raise_for_status()
        return response.json()


@mcp.tool()
async def get_workflow(workflow_id: str) -> dict:
    """Retrieve a single workflow by its ID.

    Parameters:
        workflow_id: The unique identifier of the workflow (e.g. "1" or "abc123").

    Returns the full workflow object including its nodes, connections, and settings.
    """
    async with get_client() as client:
        response = await client.get(f"workflows/{workflow_id}")
        response.raise_for_status()
        return response.json()


@mcp.tool()
async def execute_workflow(workflow_id: str, data: dict | None = None) -> dict:
    """Trigger an immediate execution of a workflow.

    Parameters:
        workflow_id: The unique identifier of the workflow to execute.
        data:        Optional dict of input data passed to the workflow's
                     trigger node (e.g. {"key": "value"}).

    Returns the execution result object, including executionId and status.
    """
    body = data if data is not None else {}
    async with get_client() as client:
        response = await client.post(f"workflows/{workflow_id}/run", json=body)
        response.raise_for_status()
        return response.json()


@mcp.tool()
async def list_executions(
    workflow_id: str | None = None,
    status: str | None = None,
    limit: int = 20,
) -> dict:
    """List workflow executions, optionally filtered by workflow or status.

    Parameters:
        workflow_id: Optional workflow ID to restrict results to a single workflow.
        status:      Optional execution status filter. One of: "success", "error",
                     "waiting", "running".
        limit:       Maximum number of executions to return (default 20, max 250).

    Returns a dict with a 'data' list of execution summary objects.
    """
    params: dict = {"limit": limit}
    if workflow_id is not None:
        params["workflowId"] = workflow_id
    if status is not None:
        params["status"] = status
    async with get_client() as client:
        response = await client.get("executions", params=params)
        response.raise_for_status()
        return response.json()


@mcp.tool()
async def get_execution(execution_id: str) -> dict:
    """Retrieve the details of a single workflow execution by its ID.

    Parameters:
        execution_id: The unique identifier of the execution to fetch.

    Returns the full execution object including status, start/end times,
    the data passed between nodes, and any error information.
    """
    async with get_client() as client:
        response = await client.get(f"executions/{execution_id}")
        response.raise_for_status()
        return response.json()


if __name__ == "__main__":
    mcp.run()
