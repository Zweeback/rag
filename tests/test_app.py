from pathlib import Path
import sys

import pytest
from httpx import ASGITransport, AsyncClient

sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.main import ChatRequest, ChatTurn, app


@pytest.mark.anyio
async def test_health_endpoint_reports_ok_status(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "dummy")
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["api_key"] == "present"
    assert "model" in payload


@pytest.mark.anyio
async def test_health_endpoint_reports_missing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "error"
    assert payload["api_key"] == "missing"


@pytest.mark.anyio
async def test_index_serves_static_landing_page() -> None:
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"].lower()


@pytest.mark.anyio
async def test_chungking_wedding_page_is_available() -> None:
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/chungking-wedding")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"].lower()
    assert "Chungking & Wedding" in response.text


@pytest.mark.anyio
async def test_chat_endpoint_appends_history(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_call(messages):
        return "assistant reply", None

    monkeypatch.setattr("app.main._call_deepseek", fake_call)

    request_body = ChatRequest(
        message="Hallo",
        history=[ChatTurn(role="user", content="Hi"), ChatTurn(role="assistant", content="Hello!")],
        system_prompt="You are a bot",
    )

    payload = (
        request_body.model_dump()
        if hasattr(request_body, "model_dump")
        else request_body.dict()
    )

    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/chat", json=payload)

    assert response.status_code == 200
    payload = response.json()
    assert payload["reply"] == "assistant reply"
    assert len(payload["history"]) == len(request_body.history) + 2
    assert payload["history"][-1]["role"] == "assistant"
    assert payload["history"][-2]["role"] == "user"
