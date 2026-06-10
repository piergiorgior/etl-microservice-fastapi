from __future__ import annotations

import asyncio
import uuid

from httpx import AsyncClient

BASE = "/api/v1/pipeline-runs"


# ---------------------------------------------------------------------------
# CREATE
# ---------------------------------------------------------------------------


async def test_create_run_returns_202(authed_client: AsyncClient) -> None:
    response = await authed_client.post(BASE, json={"pipeline_name": "ingest-daily"})

    assert response.status_code == 202
    body = response.json()
    assert body["pipeline_name"] == "ingest-daily"
    assert body["status"] == "PENDING"
    assert "id" in body
    assert "triggered_at" in body
    assert body["started_at"] is None
    assert body["finished_at"] is None
    assert body["error_message"] is None


async def test_create_run_with_metadata(authed_client: AsyncClient) -> None:
    response = await authed_client.post(
        BASE,
        json={
            "pipeline_name": "s3-to-warehouse",
            "metadata": {"source": "s3://bucket/prefix", "partition": "2026-06-10"},
        },
    )

    assert response.status_code == 202
    assert response.json()["metadata"] == {
        "source": "s3://bucket/prefix",
        "partition": "2026-06-10",
    }


async def test_create_run_empty_name_returns_422(authed_client: AsyncClient) -> None:
    response = await authed_client.post(BASE, json={"pipeline_name": ""})
    assert response.status_code == 422


async def test_create_run_no_auth_returns_401(client: AsyncClient) -> None:
    response = await client.post(BASE, json={"pipeline_name": "no-auth"})
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# LIST
# ---------------------------------------------------------------------------


async def test_list_runs_empty(authed_client: AsyncClient) -> None:
    response = await authed_client.get(BASE)
    assert response.status_code == 200
    assert response.json() == []


async def test_list_runs_returns_all(authed_client: AsyncClient) -> None:
    for i in range(3):
        await authed_client.post(BASE, json={"pipeline_name": f"pipeline-{i}"})

    response = await authed_client.get(BASE)
    assert response.status_code == 200
    assert len(response.json()) == 3


async def test_list_runs_pagination(authed_client: AsyncClient) -> None:
    for i in range(5):
        await authed_client.post(BASE, json={"pipeline_name": f"pipeline-{i}"})

    page = await authed_client.get(f"{BASE}?limit=2&offset=0")
    assert page.status_code == 200
    assert len(page.json()) == 2

    page2 = await authed_client.get(f"{BASE}?limit=2&offset=2")
    assert len(page2.json()) == 2

    ids_page1 = {r["id"] for r in page.json()}
    ids_page2 = {r["id"] for r in page2.json()}
    assert ids_page1.isdisjoint(ids_page2)


async def test_list_runs_status_filter(authed_client: AsyncClient) -> None:
    await authed_client.post(BASE, json={"pipeline_name": "pending-pipeline"})

    pending = await authed_client.get(f"{BASE}?status=PENDING")
    assert pending.status_code == 200
    data = pending.json()
    assert len(data) >= 1
    assert all(r["status"] == "PENDING" for r in data)

    running = await authed_client.get(f"{BASE}?status=RUNNING")
    assert running.json() == []


async def test_list_runs_no_auth_returns_401(client: AsyncClient) -> None:
    response = await client.get(BASE)
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET BY ID
# ---------------------------------------------------------------------------


async def test_get_run_by_id(authed_client: AsyncClient) -> None:
    created = (await authed_client.post(BASE, json={"pipeline_name": "lookup-test"})).json()
    run_id = created["id"]

    response = await authed_client.get(f"{BASE}/{run_id}")
    assert response.status_code == 200
    assert response.json()["id"] == run_id
    assert response.json()["pipeline_name"] == "lookup-test"


async def test_get_unknown_id_returns_404(authed_client: AsyncClient) -> None:
    response = await authed_client.get(f"{BASE}/{uuid.uuid4()}")
    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "PipelineRunNotFound"


async def test_get_invalid_uuid_returns_422(authed_client: AsyncClient) -> None:
    response = await authed_client.get(f"{BASE}/not-a-uuid")
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# CANCEL
# ---------------------------------------------------------------------------


async def test_cancel_pending_run(authed_client: AsyncClient) -> None:
    run_id = (await authed_client.post(BASE, json={"pipeline_name": "cancel-me"})).json()["id"]

    delete_response = await authed_client.delete(f"{BASE}/{run_id}")
    assert delete_response.status_code == 204

    get_response = await authed_client.get(f"{BASE}/{run_id}")
    assert get_response.json()["status"] == "CANCELLED"


async def test_cancel_unknown_run_returns_404(authed_client: AsyncClient) -> None:
    response = await authed_client.delete(f"{BASE}/{uuid.uuid4()}")
    assert response.status_code == 404


async def test_cancel_already_cancelled_returns_409(authed_client: AsyncClient) -> None:
    run_id = (await authed_client.post(BASE, json={"pipeline_name": "double-cancel"})).json()["id"]
    await authed_client.delete(f"{BASE}/{run_id}")

    second = await authed_client.delete(f"{BASE}/{run_id}")
    assert second.status_code == 409


# ---------------------------------------------------------------------------
# CONCURRENT TRIGGERS
# ---------------------------------------------------------------------------


async def test_concurrent_pipeline_triggers(authed_client: AsyncClient) -> None:
    """Fire 3 create requests simultaneously; all must succeed with unique IDs."""
    responses = await asyncio.gather(
        *[
            authed_client.post(BASE, json={"pipeline_name": f"concurrent-{i}"})
            for i in range(3)
        ]
    )

    assert all(r.status_code == 202 for r in responses)
    ids = {r.json()["id"] for r in responses}
    assert len(ids) == 3


# ---------------------------------------------------------------------------
# HEALTH (public endpoint — no auth needed)
# ---------------------------------------------------------------------------


async def test_health_check(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
