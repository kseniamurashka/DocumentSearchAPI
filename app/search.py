from elasticsearch import AsyncElasticsearch, NotFoundError
from elasticsearch.helpers import async_scan

from app.config import settings


async def ensure_index(client: AsyncElasticsearch) -> None:
    if await client.indices.exists(index=settings.elasticsearch_index):
        return

    await client.indices.create(
        index=settings.elasticsearch_index,
        settings={
            "number_of_shards": 1,
            "number_of_replicas": 0,
        },
        mappings={
            "dynamic": "strict",
            "properties": {
                "id": {
                    "type": "long",
                },
                "text": {
                    "type": "text",
                    "analyzer": "russian",
                },
            },
        },
    )


async def search_document_ids(
    client: AsyncElasticsearch,
    query: str,
) -> list[int]:
    document_ids = []

    async for hit in async_scan(
        client,
        index=settings.elasticsearch_index,
        query={
            "query": {
                "match": {
                    "text": query
                },
            },
            "_source": False,
        },
        size=500,
    ):
        document_ids.append(int(hit["_id"]))

    return document_ids


async def delete_document_from_index(
    client: AsyncElasticsearch,
    document_id: int,
) -> None:
    try:
        await client.delete(
            index=settings.elasticsearch_index,
            id=str(document_id),
            refresh="wait_for",
        )
    except NotFoundError as exc:
        if (
            isinstance(exc.body, dict)
            and exc.body.get("result") == "not_found"
        ):
            return
        raise

