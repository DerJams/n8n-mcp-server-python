import asyncio
import os
import time
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


async def _request(method: str, path: str, **kwargs) -> dict:
    try:
        async with get_client() as client:
            response = await getattr(client, method)(path, **kwargs)
            response.raise_for_status()
            return response.json()
    except httpx.ConnectError:
        return {"error": f"Cannot connect to n8n at {N8N_API_URL}. Check that n8n is running and N8N_API_URL is correct."}
    except httpx.TimeoutException:
        return {"error": f"Request to n8n timed out ({N8N_API_URL}). The server may be overloaded or unreachable."}
    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        if status == 401:
            return {"error": "Authentication failed (401). Check that N8N_API_KEY is set correctly."}
        if status == 404:
            return {"error": f"Resource not found (404): {path}"}
        return {"error": f"n8n returned HTTP {status}: {e.response.text}"}


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
    return await _request("get", "workflows", params=params)


@mcp.tool()
async def get_workflow(workflow_id: str) -> dict:
    """Retrieve a single workflow by its ID.

    Parameters:
        workflow_id: The unique identifier of the workflow (e.g. "1" or "abc123").

    Returns the full workflow object including its nodes, connections, and settings.
    """
    return await _request("get", f"workflows/{workflow_id}")


@mcp.tool()
async def execute_workflow(workflow_id: str, data: dict | None = None) -> dict:
    """Trigger an immediate execution of a workflow.

    Parameters:
        workflow_id: The unique identifier of the workflow to execute.
        data:        Optional dict of input data passed to the workflow's
                     trigger node (e.g. {"key": "value"}).

    Returns the execution result object, including executionId and status.
    """
    return await _request("post", f"workflows/{workflow_id}/run", json=data or {})


@mcp.tool()
async def create_workflow(
    name: str,
    nodes: list | None = None,
    connections: dict | None = None,
) -> dict:
    """Create a new workflow in n8n.

    Parameters:
        name:        Display name for the new workflow.
        nodes:       Optional list of node definition dicts. Defaults to an
                     empty workflow if omitted. Each node must include at
                     least 'type', 'typeVersion', 'position', 'parameters',
                     'id', and 'name'.
        connections: Optional n8n connections object wiring node outputs to
                     inputs. Keyed by source node NAME (not id). Shape:
                       {
                         "Trigger": {
                           "main": [[{"node": "Next", "type": "main", "index": 0}]]
                         }
                       }
                     Defaults to {} (nodes remain unconnected).

    Returns the created workflow object including its assigned ID.
    """
    body = {
        "name": name,
        "nodes": nodes or [],
        "connections": connections or {},
        "settings": {},
    }
    return await _request("post", "workflows", json=body)


_UPDATABLE_FIELDS = ("name", "nodes", "connections", "settings", "staticData", "pinData")


@mcp.tool()
async def update_workflow(
    workflow_id: str,
    name: str | None = None,
    nodes: list | None = None,
    connections: dict | None = None,
    settings: dict | None = None,
) -> dict:
    """Update an existing workflow in n8n.

    n8n's API replaces the whole workflow (PUT /workflows/{id}), so this
    tool first GETs the current workflow, overlays any fields you provide,
    then PUTs the full object back. Fields you omit are preserved. Pass an
    empty dict or list to explicitly clear a field.

    Parameters:
        workflow_id: The unique identifier of the workflow to update.
        name:        Optional new display name.
        nodes:       Optional replacement list of node definitions.
        connections: Optional replacement connections object
                     (see create_workflow for the shape).
        settings:    Optional replacement settings dict.

    Returns the updated workflow object.
    """
    current = await _request("get", f"workflows/{workflow_id}")
    if "error" in current:
        return current

    # Drop null-valued optional fields (pinData/staticData): n8n's OpenAPI
    # validator rejects them with 400 "must NOT have additional properties"
    # even though the schema marks them nullable.
    body = {
        field: current[field]
        for field in _UPDATABLE_FIELDS
        if field in current and current[field] is not None
    }
    overrides = {"name": name, "nodes": nodes, "connections": connections, "settings": settings}
    for field, value in overrides.items():
        if value is not None:
            body[field] = value

    for required in ("name", "nodes", "connections", "settings"):
        if required not in body:
            return {
                "error": (
                    f"Cannot update workflow {workflow_id}: current workflow is missing "
                    f"required field '{required}' and none was provided."
                )
            }

    return await _request("put", f"workflows/{workflow_id}", json=body)


@mcp.tool()
async def delete_workflow(workflow_id: str) -> dict:
    """Delete a workflow permanently.

    Parameters:
        workflow_id: The unique identifier of the workflow to delete.

    Returns the deleted workflow object as it existed before deletion.
    """
    return await _request("delete", f"workflows/{workflow_id}")


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
    return await _request("get", "executions", params=params)


@mcp.tool()
async def activate_workflow(workflow_id: str) -> dict:
    """Activate a workflow so it responds to its trigger.

    Parameters:
        workflow_id: The unique identifier of the workflow to activate.

    Returns the updated workflow object with active set to true.
    """
    return await _request("post", f"workflows/{workflow_id}/activate")


@mcp.tool()
async def deactivate_workflow(workflow_id: str) -> dict:
    """Deactivate a workflow so its trigger stops firing.

    Parameters:
        workflow_id: The unique identifier of the workflow to deactivate.

    Returns the updated workflow object with active set to false.
    """
    return await _request("post", f"workflows/{workflow_id}/deactivate")


@mcp.tool()
async def get_execution(execution_id: str) -> dict:
    """Retrieve the details of a single workflow execution by its ID.

    Parameters:
        execution_id: The unique identifier of the execution to fetch.

    Returns the full execution object including status, start/end times,
    the data passed between nodes, and any error information.
    """
    return await _request("get", f"executions/{execution_id}")


@mcp.tool()
async def wait_for_execution(execution_id: str, timeout_seconds: int = 60) -> dict:
    """Poll an execution until it finishes, then return the final execution object.

    Calls get_execution every 2 seconds until the status is no longer
    'running' or 'waiting'. Useful after execute_workflow when you need
    the output data rather than just the execution ID.

    Parameters:
        execution_id:    The unique identifier of the execution to wait for.
        timeout_seconds: Maximum seconds to wait before giving up (default 60).

    Returns the completed execution object, or an error dict if the execution
    did not finish within timeout_seconds.
    """
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        result = await get_execution(execution_id)
        if "error" in result:
            return result
        if result.get("status") not in ("running", "waiting"):
            return result
        await asyncio.sleep(2)
    return {
        "error": (
            f"Execution {execution_id} did not complete within {timeout_seconds}s. "
            "Check its current status with get_execution."
        )
    }


if __name__ == "__main__":
    mcp.run()
