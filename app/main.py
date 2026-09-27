from contextlib import asynccontextmanager
from typing import Annotated

from aiohttp import client_exceptions
from elastic_transport import TransportError
from elasticsearch import ApiError, AsyncElasticsearch
from fastapi import (
    FastAPI,
    HTTPException,
    Path,
    Query,
    Request,
    Response,
)
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError

from app.config import settings
from app.database import engine, session_factory
from app.models import Document
from app.schemas import DocumentResponse
from app.search import delete_document_from_index, search_document_ids

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        async with AsyncElasticsearch(
            settings.elasticsearch_url,
            request_timeout=30,
        ) as client:
            app.state.elasticsearch = client
            yield
    finally:
        await engine.dispose()

app = FastAPI(
    title="Document Search API",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except (SQLAlchemyError, OSError) as exc:
        raise HTTPException(
            status_code=503,
            detail="Database unavailable",
        ) from exc

    return {"status": "ok", "database": "ok"}


@app.get(
    "/documents/search",
    response_model=list[DocumentResponse],
)
async def search_documents(
    request: Request,
    q: Annotated[str, Query(min_length=1, pattern=r"\S")],
):
    client = request.app.state.elasticsearch

    try:
        document_ids = await search_document_ids(
            client,
            query=q.strip(),
        )
    except (ApiError, TransportError) as exc:
        raise HTTPException(
            status_code=503,
            detail="Search service unavailable",
        ) from exc

    if not document_ids:
        return []

    try:
        async with session_factory() as session:
            result = await session.scalars(
                select(Document)
                .where(Document.id.in_(document_ids))
                .order_by(
                    Document.created_date.desc(),
                    Document.id.asc(),
                )
                .limit(20)
            )
            documents = result.all()
    except (SQLAlchemyError, OSError) as exc:
        raise HTTPException(
            status_code=503,
            detail="Database unavailable",
        ) from exc

    return documents


@app.delete(
    "/documents/{document_id}",
    status_code=204,
)
async def delete_document(
    request: Request,
    document_id: Annotated[int, Path(gt=0)],
):
    client = request.app.state.elasticsearch

    try:
        async with session_factory.begin() as session:
            document = await session.scalar(
                select(Document)
                .where(Document.id == document_id)
                .with_for_update()
            )

            if document is None:
                raise HTTPException(
                    status_code=404,
                    detail="Document not found"
                )
            await delete_document_from_index(
                client,
                document_id,
            )

            await session.delete(document)

    except (ApiError, TransportError) as exc:
        raise HTTPException(
            status_code=503,
            detail="Search service unavailable",
        ) from exc

    except (SQLAlchemyError, OSError) as exc:
        raise HTTPException(
            status_code=503,
            detail="Database unavailable",
        ) from exc

    return Response(status_code=204)