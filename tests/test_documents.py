import pytest


from elastic_transport import ConnectionError
from unittest.mock import AsyncMock

from app.config import settings
from app.models import Document



@pytest.mark.asyncio
async def test_search_in_empty_index(integration_client):
    health_response = await integration_client.get("/health")

    assert health_response.status_code == 200
    assert health_response.json() == {
        "status": "ok",
        "database": "ok",
    }

    response = await integration_client.get(
        "/documents/search",
        params={"q": "библиотека"},
    )

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_search_returns_20_newest_matching_documents(
    integration_client,
    seeded_documents,
):
    response = await integration_client.get(
        "/documents/search",
        params={"q": "библиотека"},
    )

    assert response.status_code == 200

    expected_ids = [
        25,
        23, 24,
        21, 22,
        19, 20,
        17, 18,
        15, 16,
        13, 14,
        11, 12,
        9, 10,
        7, 8,
        5,
    ]

    documents_by_id = {
        document.id: document
        for document in seeded_documents
    }

    expected_response = [
        {
            "id": document_id,
            "text": documents_by_id[document_id].text,
            "rubrics": documents_by_id[document_id].rubrics,
            "created_date": (
                documents_by_id[document_id].created_date.isoformat()
            ),
        }
        for document_id in expected_ids
    ]

    assert response.json() == expected_response


@pytest.mark.asyncio
async def test_delete_removes_document_from_both_storages(
    integration_client,
    seeded_documents,
    test_session_factory,
    test_elasticsearch,
):
    document_id = 25

    async with test_session_factory() as session:
        document = await session.get(Document, document_id)
        assert document is not None

    exists = await test_elasticsearch.exists(
        index=settings.elasticsearch_index,
        id=str(document_id),
    )
    assert exists

    response = await integration_client.delete(
        f"/documents/{document_id}",
    )

    assert response.status_code == 204
    assert response.content == b""

    # Проверяем результат в новой сессии PostgreSQL
    async with test_session_factory() as session:
        document = await session.get(Document, document_id)
        assert document is None

    # Проверяем результат в Elasticsearch
    exists = await test_elasticsearch.exists(
        index=settings.elasticsearch_index,
        id=str(document_id),
    )
    assert not exists

    # Повторное удаление должно сообщить об отсутствии документа
    repeated_response = await integration_client.delete(
        f"/documents/{document_id}",
    )

    assert repeated_response.status_code == 404
    assert repeated_response.json() == {
        "detail": "Document not found",
    }


@pytest.mark.asyncio
async def test_delete_keeps_document_when_elasticsearch_fails(
    integration_client,
    seeded_documents,
    test_session_factory,
    monkeypatch,
):
    document_id = 25

    delete_mock = AsyncMock(
        side_effect=ConnectionError("Elasticsearch unavailable"),
    )

    monkeypatch.setattr(
        "app.main.delete_document_from_index",
        delete_mock,
    )

    response = await integration_client.delete(
        f"/documents/{document_id}",
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Search service unavailable",
    }

    async with test_session_factory() as session:
        document = await session.get(Document, document_id)
        assert document is not None


@pytest.mark.asyncio
async def test_delete_succeeds_when_document_is_missing_from_index(
    integration_client,
    seeded_documents,
    test_session_factory,
    test_elasticsearch,
):
    document_id = 25

    # в PostgreSQL запись будет, а в индексе - нет.
    await test_elasticsearch.delete(
        index=settings.elasticsearch_index,
        id=str(document_id),
        refresh="wait_for",
    )

    response = await integration_client.delete(
        f"/documents/{document_id}",
    )

    assert response.status_code == 204
    assert response.content == b""

    async with test_session_factory() as session:
        document = await session.get(Document, document_id)
        assert document is None

    exists = await test_elasticsearch.exists(
        index=settings.elasticsearch_index,
        id=str(document_id),
    )
    assert not exists