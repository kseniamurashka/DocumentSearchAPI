from datetime import datetime, timedelta
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from elasticsearch import AsyncElasticsearch
from elasticsearch.helpers import async_bulk
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.schema import CreateSchema, DropSchema

from app.config import settings
from app.database import database_url
from app.main import app
from app.models import Base, Document
from app.search import ensure_index


@pytest_asyncio.fixture
async def test_engine():
    test_url = database_url.set(database="documents_test")
    schema_name = f"test_{uuid4().hex}"

    engine = create_async_engine(
        test_url,
        execution_options={
            "schema_translate_map": {None: schema_name},
        },
    )

    schema_created = False

    try:
        async with engine.begin() as connection:
            await connection.execute(CreateSchema(schema_name))
            await connection.run_sync(Base.metadata.create_all)

        schema_created = True

        yield engine

    finally:
        try:
            if schema_created:
                async with engine.begin() as connection:
                    await connection.execute(
                        DropSchema(schema_name, cascade=True),
                    )
        finally:
            await engine.dispose()


@pytest.fixture
def test_session_factory(test_engine):
    return async_sessionmaker(
        test_engine,
        expire_on_commit=False,
    )


@pytest_asyncio.fixture
async def test_elasticsearch(monkeypatch):
    index_name = f"documents_test_{uuid4().hex}"

    monkeypatch.setattr(
        settings,
        "elasticsearch_index",
        index_name,
    )

    async with AsyncElasticsearch(
        settings.elasticsearch_url,
        request_timeout=30,
    ) as client:
        try:
            await ensure_index(client)

            yield client

        finally:
            await client.options(ignore_status=404).indices.delete(
                index=index_name,
            )


@pytest_asyncio.fixture
async def integration_client(
    monkeypatch,
    test_engine,
    test_session_factory,
    test_elasticsearch,
):
    monkeypatch.setattr(
        "app.main.engine",
        test_engine,
    )
    monkeypatch.setattr(
        "app.main.session_factory",
        test_session_factory,
    )
    monkeypatch.setattr(
        app.state,
        "elasticsearch",
        test_elasticsearch,
        raising=False,
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


@pytest_asyncio.fixture
async def seeded_documents(
    test_session_factory,
    test_elasticsearch,
):
    start_date = datetime(2026, 1, 1)

    documents = [
        Document(
            id=number,
            text=f"Библиотека: документ номер {number}",
            rubrics=["учебные", f"рубрика {number}"],
            created_date=start_date + timedelta(days=(number - 1) // 2),
        )
        for number in range(1, 26)
    ]

    documents.append(
        Document(
            id=100,
            text="Ремонт автомобильной дороги",
            rubrics=["транспорт"],
            created_date=datetime(2026, 2, 1),
        )
    )

    async with test_session_factory.begin() as session:
        session.add_all(documents)

    actions = [
        {
            "_op_type": "index",
            "_index": settings.elasticsearch_index,
            "_id": str(document.id),
            "_source": {
                "id": document.id,
                "text": document.text,
            },
        }
        for document in documents
    ]

    await async_bulk(
        test_elasticsearch,
        actions,
        refresh="wait_for",
    )

    return documents