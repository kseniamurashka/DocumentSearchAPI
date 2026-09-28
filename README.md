# Document Search API

Асинхронный API для поиска по текстам из CSV и удаления документов по ID. PostgreSQL хранит полные записи, Elasticsearch - `id` и `text`.

## Сборка и запуск

Команды выполняются из корня репозитория. Требуется Docker Compose V2.

1. **Подготовьте настройки.**

   ```sh
   cp .env.example .env
   ```

   Задайте `POSTGRES_PASSWORD` в `.env`. Если файл уже настроен, пропустите этот шаг.

2. **Соберите и запустите сервисы.**

   ```sh
   docker compose up -d --build
   ```

   При запуске API последовательно выполняются миграции, импорт `data/posts.csv` и индексация. В исходном CSV 1500 документов.

3. **Дождитесь готовности API.**

   ```sh
   docker compose logs -f api
   ```

   Когда в логах появится `Application startup complete`, API готов принимать запросы.

После запуска доступны:

- [Swagger UI](http://127.0.0.1:8001/docs) - интерактивная документация и отправка запросов к API.
- [Health](http://127.0.0.1:8001/health) - проверка соединения с PostgreSQL.
- [OpenAPI](http://127.0.0.1:8001/openapi.json) - актуальная схема API в JSON.

Порты на хосте: API - `8001`, PostgreSQL - `5432`, Elasticsearch - `9200`; привязка к `127.0.0.1`. Настройки - в `.env.example`. Compose переопределяет адреса хранилищ для контейнера API.

## API

| Метод | Адрес | Поведение |
| --- | --- | --- |
| GET | `/documents/search?q=...` | Получение до 20 документов по поисковому запросу с полями `id`, `rubrics`, `text`, `created_date` |
| DELETE | `/documents/{document_id}` | Удаление из обоих хранилищ; `204`, при отсутствии записи в PostgreSQL - `404` |
| GET | `/health` | `SELECT 1` в PostgreSQL; Elasticsearch не проверяется |

Поиск: `match`, анализатор `russian`, логика OR по терминам. Все найденные ID передаются в PostgreSQL; итоговый порядок - `created_date DESC, id ASC`, затем `LIMIT 20`. Нет совпадений - `[]`. Параметр `q` обязателен и не может состоять только из пробелов; ID должен быть положительным целым числом.

OpenAPI сохранена в `docs.json`. После изменения API обновите файл из `/openapi.json` работающего сервиса.

## Запуск без контейнера API

Python 3.13 и uv. Хранилища остаются в Docker; используются локальные адреса из `.env`.

```sh
docker compose stop api
docker compose up -d --wait postgres elasticsearch
uv sync --locked
uv run alembic upgrade head
uv run python -m app.import_documents
uv run python -m app.index_documents
uv run uvicorn app.main:app --reload --port 8001
```

## Тесты

```sh
uv sync --locked --group dev
docker compose up -d --wait postgres elasticsearch
```

Однократно создайте тестовую базу (`app` - `POSTGRES_USER` из примера настроек):

```sh
docker compose exec postgres psql -U app -d postgres -c "CREATE DATABASE documents_test;"
```

```sh
uv run python -m pytest -v
```

12 проверок: валидация, поиск и сортировка, лимит выдачи, удаление, повторное удаление и сбои Elasticsearch. Для каждого интеграционного теста создаются временная схема в `documents_test` и отдельный индекс Elasticsearch; после теста они удаляются. Миграции этим набором не проверяются: таблицы создаются из моделей SQLAlchemy.

## Стек

| Компонент | Технологии |
| --- | --- |
| API и валидация | FastAPI, Pydantic |
| База данных | PostgreSQL 17, SQLAlchemy 2.0, asyncpg |
| Миграции | Alembic |
| Поиск | Elasticsearch 8.19 |

Версии Python-зависимостей зафиксированы в `uv.lock`.

## Особенности реализации

- Импорт выполняется только в пустую таблицу. Изменения CSV не обновляют существующие записи. После удаления всех документов следующий запуск контейнера снова загрузит CSV.
- Повторная индексация перезаписывает документы по `_id`, но не очищает записи, отсутствующие в PostgreSQL.
- Сбор всех совпавших ID рассчитан на небольшой набор данных; пагинации нет.
- Удаление сначала выполняется в Elasticsearch, затем фиксируется в PostgreSQL. Общей транзакции нет: при сбое фиксации в PostgreSQL возможна рассинхронизация. Повторный DELETE завершает удаление, даже если документа уже нет в индексе. Фоновой сверки нет.
- Запуск рассчитан на один экземпляр API. Авторизация API и Elasticsearch отключена; Compose предназначен для локальной проверки.
