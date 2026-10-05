from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db.database import init_db
from app.api.conversations import router as conversations_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="Mosaic API", version="0.1.0", lifespan=lifespan)

app.include_router(conversations_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
