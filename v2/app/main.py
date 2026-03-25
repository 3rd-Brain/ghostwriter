from fastapi import FastAPI

app = FastAPI(title="Ghostwriter V2", version="2.0.0")


@app.get("/health")
async def health():
    return {"status": "ok"}
