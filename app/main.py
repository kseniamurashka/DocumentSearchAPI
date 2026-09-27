from contextlib import asynccontextmanager
from typing import Annotated

from elasticsearch import ApiError, AsyncElasticsearch
from fastapi import FastAPI, HTTPException, Query, Request
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError

from app.config import settings
from app.database import engine, session_factory
from app.models import Document
from app.schemas import DocumentResponse
from app.search import search_document_ids

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
    except (ApiError, AsyncElasticsearch) as exc:
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