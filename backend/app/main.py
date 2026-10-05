from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.chat import router as chat_router
from app.api.conversations import router as conversations_router
from app.api.messages import router as messages_router
from app.api.memories import router as memories_router
from app.db.database import init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="Mosaic API", version="0.1.0", lifespan=lifespan)

app.include_router(conversations_router)
app.include_router(messages_router)
app.include_router(memories_router)
app.include_router(chat_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
