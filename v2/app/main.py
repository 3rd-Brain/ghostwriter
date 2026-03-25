from fastapi import FastAPI

from app.routers import accounts

app = FastAPI(title="Ghostwriter V2", version="2.0.0")

app.include_router(accounts.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
