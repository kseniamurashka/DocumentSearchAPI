from unittest.mock import AsyncMock

import httpx
import pytest
from elastic_transport import ConnectionError

from app.main import app


@pytest.mark.asyncio
async def test_search_returns_503_when_elasticsearch_is_unavailable(
    monkeypatch,
):
    fake_client = object()

    monkeypatch.setattr(
        app.state,
        "elasticsearch",
        fake_client,
        raising=False,
    )

    search_mock = AsyncMock(
        side_effect=ConnectionError("Elasticsearch unavailable")
    )

    monkeypatch.setattr(
        "app.main.search_document_ids",
        search_mock,
    )

    async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
    ) as client:
        response = await client.get(
            "/documents/search",
            params={"q": "библиотека"},
        )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Search service unavailable",
    }

    search_mock.assert_awaited_once_with(
        fake_client,
        query="библиотека",
    )