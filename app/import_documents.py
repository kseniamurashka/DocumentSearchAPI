import ast
import asyncio
import csv
from datetime import datetime
from pathlib import Path
from sqlalchemy import select

from app.database import engine, session_factory
from app.models import Document

def read_document(path: Path) -> list[Document]:
    documents = []

    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)

        for number, row in enumerate(reader, start=1):
            try:
                rubrics = ast.literal_eval(row["rubrics"])

                if not isinstance(rubrics, list) or not all(
                        isinstance(rubric, str) for rubric in rubrics
                ):
                    raise ValueError("rubrics должен быть списком строк")

                document = Document(
                    text=row["text"],
                    rubrics=rubrics,
                    created_date=datetime.fromisoformat(row["created_date"]),
                )
            except (ValueError, SyntaxError, TypeError, KeyError) as exc:
                raise ValueError(
                    f"Ошибка в записи CSV №{number}: {exc}"
                ) from exc

            documents.append(document)

    return documents


async def import_documents(path: Path) -> int:
    documents = read_document(path)

    async with session_factory.begin() as session:
        existing_id = await session.scalar(
            select(Document.id).limit(1)
        )

        if existing_id is not None:
            return 0

        session.add_all(documents)

    return len(documents)


async def main() -> None:
    csv_path = Path(__file__).resolve().parents[1] / "data" / "posts.csv"

    try:
        count = await import_documents(csv_path)
        print(f"Добавлено документов: {count}")
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())