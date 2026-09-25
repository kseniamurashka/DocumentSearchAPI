from fastapi import FastAPI

app = FastAPI(title="Document Search API")


@app.get("/health")
async def health():
    return {"status": "ok"}