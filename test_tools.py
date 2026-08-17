import httpx
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from main import (
    activate_workflow,
    create_workflow,
    deactivate_workflow,
    delete_workflow,
    execute_workflow,
    get_execution,
    get_workflow,
    list_executions,
    list_workflows,
    update_workflow,
)


def _response(payload: dict) -> MagicMock:
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.return_value = payload
    return response


def mock_client(payload: dict) -> AsyncMock:
    """Return a mock httpx.AsyncClient whose HTTP methods return payload."""
    response = _response(payload)

    client = AsyncMock()
    client.get = AsyncMock(return_value=response)
    client.post = AsyncMock(return_value=response)
    client.put = AsyncMock(return_value=response)
    client.delete = AsyncMock(return_value=response)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


def sequential_client(*payloads: dict) -> AsyncMock:
    """Return a mock client whose every HTTP call returns the next payload.

    Useful for tools like update_workflow that issue GET then PUT and expect
    different response bodies. All HTTP methods draw from one shared queue,
    so mixed-method sequences (GET, then PUT) work as long as calls happen
    in the order the payloads were passed.
    """
    responses = iter([_response(p) for p in payloads])

    client = AsyncMock()
    client.get = AsyncMock(side_effect=lambda *a, **kw: next(responses))
    client.post = AsyncMock(side_effect=lambda *a, **kw: next(responses))
    client.put = AsyncMock(side_effect=lambda *a, **kw: next(responses))
    client.delete = AsyncMock(side_effect=lambda *a, **kw: next(responses))
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


def refused_client() -> AsyncMock:
    """Return a mock client that raises ConnectError on every HTTP method."""
    client = AsyncMock()
    err = httpx.ConnectError("Connection refused")
    client.get = AsyncMock(side_effect=err)
    client.post = AsyncMock(side_effect=err)
    client.put = AsyncMock(side_effect=err)
    client.delete = AsyncMock(side_effect=err)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


# ---------------------------------------------------------------------------
# list_workflows
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_workflows_all():
    payload = {"data": [{"id": "1", "name": "Invoice Pipeline", "active": True}]}
    client = mock_client(payload)
    with patch("main.get_client", return_value=client):
        result = await list_workflows()
    assert result == payload
    client.get.assert_called_once_with("workflows", params={})


@pytest.mark.asyncio
async def test_list_workflows_active_filter():
    client = mock_client({"data": []})
    with patch("main.get_client", return_value=client):
        await list_workflows(active=True)
    client.get.assert_called_once_with("workflows", params={"active": "true"})


@pytest.mark.asyncio
async def test_list_workflows_inactive_filter():
    client = mock_client({"data": []})
    with patch("main.get_client", return_value=client):
        await list_workflows(active=False)
    client.get.assert_called_once_with("workflows", params={"active": "false"})


@pytest.mark.asyncio
async def test_list_workflows_connection_refused():
    with patch("main.get_client", return_value=refused_client()):
        result = await list_workflows()
    assert "error" in result
    assert "Cannot connect" in result["error"]


# ---------------------------------------------------------------------------
# get_workflow
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_workflow():
    payload = {"id": "abc", "name": "Lead Scoring", "nodes": [], "active": False}
    client = mock_client(payload)
    with patch("main.get_client", return_value=client):
        result = await get_workflow("abc")
    assert result == payload
    client.get.assert_called_once_with("workflows/abc")


# ---------------------------------------------------------------------------
# create_workflow
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_workflow_no_nodes():
    payload = {"id": "new1", "name": "Empty Workflow", "nodes": []}
    client = mock_client(payload)
    with patch("main.get_client", return_value=client):
        result = await create_workflow("Empty Workflow")
    assert result == payload
    client.post.assert_called_once_with(
        "workflows",
        json={"name": "Empty Workflow", "nodes": [], "connections": {}, "settings": {}},
    )


@pytest.mark.asyncio
async def test_create_workflow_with_nodes():
    nodes = [{"type": "n8n-nodes-base.manualTrigger", "typeVersion": 1,
               "position": [0, 0], "parameters": {}, "id": "node1", "name": "Trigger"}]
    client = mock_client({"id": "new2", "name": "Property Aggregator"})
    with patch("main.get_client", return_value=client):
        await create_workflow("Property Aggregator", nodes=nodes)
    client.post.assert_called_once_with(
        "workflows",
        json={"name": "Property Aggregator", "nodes": nodes, "connections": {}, "settings": {}},
    )


@pytest.mark.asyncio
async def test_create_workflow_with_connections():
    nodes = [
        {"type": "n8n-nodes-base.manualTrigger", "typeVersion": 1,
         "position": [0, 0], "parameters": {}, "id": "n1", "name": "Trigger"},
        {"type": "n8n-nodes-base.noOp", "typeVersion": 1,
         "position": [200, 0], "parameters": {}, "id": "n2", "name": "NoOp"},
    ]
    connections = {
        "Trigger": {"main": [[{"node": "NoOp", "type": "main", "index": 0}]]}
    }
    client = mock_client({"id": "new3", "name": "Wired"})
    with patch("main.get_client", return_value=client):
        await create_workflow("Wired", nodes=nodes, connections=connections)
    client.post.assert_called_once_with(
        "workflows",
        json={"name": "Wired", "nodes": nodes, "connections": connections, "settings": {}},
    )


# ---------------------------------------------------------------------------
# update_workflow
# ---------------------------------------------------------------------------

def _existing_workflow(**overrides) -> dict:
    """A GET /workflows/{id} response with the readOnly fields n8n returns."""
    base = {
        "id": "abc",
        "name": "Old Name",
        "nodes": [{"id": "n1", "name": "Trigger", "type": "n8n-nodes-base.manualTrigger",
                   "typeVersion": 1, "position": [0, 0], "parameters": {}}],
        "connections": {},
        "settings": {"executionOrder": "v1"},
        "active": False,
        "createdAt": "2026-01-01T00:00:00Z",
        "updatedAt": "2026-01-01T00:00:00Z",
        "versionId": "v-old",
        "triggerCount": 0,
        "isArchived": False,
        "meta": None,
        "tags": [],
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_update_workflow_name_only():
    existing = _existing_workflow()
    client = sequential_client(existing, {**existing, "name": "New Name"})
    with patch("main.get_client", return_value=client):
        result = await update_workflow("abc", name="New Name")
    assert result["name"] == "New Name"
    client.get.assert_called_once_with("workflows/abc")
    client.put.assert_called_once_with(
        "workflows/abc",
        json={
            "name": "New Name",
            "nodes": existing["nodes"],
            "connections": existing["connections"],
            "settings": existing["settings"],
        },
    )


@pytest.mark.asyncio
async def test_update_workflow_replaces_connections():
    existing = _existing_workflow(connections={"Trigger": {"main": [[]]}})
    new_connections = {"Trigger": {"main": [[{"node": "NoOp", "type": "main", "index": 0}]]}}
    client = sequential_client(existing, {**existing, "connections": new_connections})
    with patch("main.get_client", return_value=client):
        await update_workflow("abc", connections=new_connections)
    _, kwargs = client.put.call_args
    assert kwargs["json"]["connections"] == new_connections
    assert kwargs["json"]["name"] == existing["name"]
    assert kwargs["json"]["nodes"] == existing["nodes"]


@pytest.mark.asyncio
async def test_update_workflow_strips_readonly_fields():
    """PUT body must contain ONLY writable fields — n8n's OpenAPI validator
    rejects readOnly extras under additionalProperties: false."""
    existing = _existing_workflow(staticData={"lastId": 5}, pinData={"Trigger": [{"json": {}}]})
    client = sequential_client(existing, {**existing, "name": "Renamed"})
    with patch("main.get_client", return_value=client):
        await update_workflow("abc", name="Renamed")
    _, kwargs = client.put.call_args
    body_keys = set(kwargs["json"].keys())
    assert body_keys == {"name", "nodes", "connections", "settings", "staticData", "pinData"}
    for readonly in ("id", "active", "createdAt", "updatedAt", "versionId",
                     "triggerCount", "isArchived", "meta", "tags"):
        assert readonly not in kwargs["json"]


@pytest.mark.asyncio
async def test_update_workflow_workflow_not_found():
    """If GET fails, PUT is never called and the error propagates."""
    not_found = MagicMock()
    not_found.raise_for_status.side_effect = httpx.HTTPStatusError(
        "404", request=MagicMock(),
        response=MagicMock(status_code=404, text="not found"),
    )
    client = mock_client({})
    client.get = AsyncMock(return_value=not_found)
    with patch("main.get_client", return_value=client):
        result = await update_workflow("missing", name="whatever")
    assert "error" in result
    assert "404" in result["error"]
    client.put.assert_not_called()


@pytest.mark.asyncio
async def test_update_workflow_drops_null_optional_fields():
    """n8n's validator rejects pinData: null on PUT despite the schema
    marking it nullable. We drop top-level nulls to avoid the 400."""
    existing = _existing_workflow(pinData=None, staticData=None)
    client = sequential_client(existing, {**existing, "name": "New"})
    with patch("main.get_client", return_value=client):
        await update_workflow("abc", name="New")
    _, kwargs = client.put.call_args
    assert "pinData" not in kwargs["json"]
    assert "staticData" not in kwargs["json"]


@pytest.mark.asyncio
async def test_update_workflow_empty_dict_clears_field():
    """Passing an empty dict for connections should replace, not preserve."""
    existing = _existing_workflow(connections={"Trigger": {"main": [[]]}})
    client = sequential_client(existing, {**existing, "connections": {}})
    with patch("main.get_client", return_value=client):
        await update_workflow("abc", connections={})
    _, kwargs = client.put.call_args
    assert kwargs["json"]["connections"] == {}


# ---------------------------------------------------------------------------
# delete_workflow
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_workflow():
    payload = {"id": "abc", "name": "Old Workflow"}
    client = mock_client(payload)
    with patch("main.get_client", return_value=client):
        result = await delete_workflow("abc")
    assert result == payload
    client.delete.assert_called_once_with("workflows/abc")


# ---------------------------------------------------------------------------
# execute_workflow
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_workflow_no_data():
    payload = {"executionId": "42", "status": "running"}
    client = mock_client(payload)
    with patch("main.get_client", return_value=client):
        result = await execute_workflow("abc")
    assert result == payload
    client.post.assert_called_once_with("workflows/abc/run", json={})


@pytest.mark.asyncio
async def test_execute_workflow_with_data():
    client = mock_client({"executionId": "43", "status": "running"})
    with patch("main.get_client", return_value=client):
        await execute_workflow("abc", data={"invoice_id": "INV-001"})
    client.post.assert_called_once_with("workflows/abc/run", json={"invoice_id": "INV-001"})


# ---------------------------------------------------------------------------
# activate_workflow
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_activate_workflow():
    payload = {"id": "abc", "name": "Invoice Pipeline", "active": True}
    client = mock_client(payload)
    with patch("main.get_client", return_value=client):
        result = await activate_workflow("abc")
    assert result == payload
    assert result["active"] is True
    client.post.assert_called_once_with("workflows/abc/activate")


# ---------------------------------------------------------------------------
# deactivate_workflow
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_deactivate_workflow():
    payload = {"id": "abc", "name": "Invoice Pipeline", "active": False}
    client = mock_client(payload)
    with patch("main.get_client", return_value=client):
        result = await deactivate_workflow("abc")
    assert result == payload
    assert result["active"] is False
    client.post.assert_called_once_with("workflows/abc/deactivate")


# ---------------------------------------------------------------------------
# list_executions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_executions_defaults():
    payload = {"data": [{"id": "99", "status": "success"}]}
    client = mock_client(payload)
    with patch("main.get_client", return_value=client):
        result = await list_executions()
    assert result == payload
    client.get.assert_called_once_with("executions", params={"limit": 20})


@pytest.mark.asyncio
async def test_list_executions_with_filters():
    client = mock_client({"data": []})
    with patch("main.get_client", return_value=client):
        await list_executions(workflow_id="abc", status="error", limit=5)
    client.get.assert_called_once_with(
        "executions",
        params={"limit": 5, "workflowId": "abc", "status": "error"},
    )


# ---------------------------------------------------------------------------
# get_execution
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_execution():
    payload = {"id": "99", "status": "success", "startedAt": "2026-05-20T10:00:00Z"}
    client = mock_client(payload)
    with patch("main.get_client", return_value=client):
        result = await get_execution("99")
    assert result == payload
    client.get.assert_called_once_with("executions/99")
