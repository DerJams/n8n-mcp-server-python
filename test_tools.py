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
)


def mock_client(payload: dict) -> AsyncMock:
    """Return a mock httpx.AsyncClient whose HTTP methods return payload."""
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.return_value = payload

    client = AsyncMock()
    client.get = AsyncMock(return_value=response)
    client.post = AsyncMock(return_value=response)
    client.delete = AsyncMock(return_value=response)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


def refused_client() -> AsyncMock:
    """Return a mock client that raises ConnectError on every HTTP method."""
    client = AsyncMock()
    err = httpx.ConnectError("Connection refused")
    client.get = AsyncMock(side_effect=err)
    client.post = AsyncMock(side_effect=err)
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
