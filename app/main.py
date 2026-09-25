from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.database import engine

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
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