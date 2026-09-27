import httpx
import pytest

from app.main import app

@pytest.mark.asyncio
@pytest.mark.parametrize("query", [None, "", "   "])
async def test_search_rejects_invalid_query(query):
    params = {} if query is None else {"q": query}

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/documents/search",
            params=params,
        )

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["query", "q"]


@pytest.mark.asyncio
@pytest.mark.parametrize("document_id", ["0", "-1", "abc"])
async def test_delete_rejects_invalid_id(document_id):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.delete(
            f"/documents/{document_id}",
        )

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == [
        "path",
        "document_id",
    ]


