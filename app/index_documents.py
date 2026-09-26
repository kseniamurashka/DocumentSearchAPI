import asyncio
from argparse import Action

from elasticsearch import AsyncElasticsearch
from elasticsearch.helpers import async_bulk
from sqlalchemy import select

from app.config import settings
from app.database import engine, session_factory
from app.models import Document
from app.search import ensure_index

async def index_documents(client: AsyncElasticsearch) -> int:
    await ensure_index(client)

    async with session_factory() as session:
        result = await session.execute(
            select(Document.id, Document.text)
        )
        documents = result.all()

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

    indexed_count, _ = await async_bulk(
        client,
        actions,
        chunk_size=500,
        refresh="wait_for",
    )

    return indexed_count


async def main() -> None:
    try:
        async with AsyncElasticsearch(
            settings.elasticsearch_url,
            request_timeout=30,
        ) as client:
            count = await index_documents(client)
            print(f"Проиндексировано документов: {count}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())