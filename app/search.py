from elasticsearch import AsyncElasticsearch

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