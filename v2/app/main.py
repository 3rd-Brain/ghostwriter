from fastapi import FastAPI

from app.routers import accounts, brands, workflows, templates, source_content, generation, templatize

app = FastAPI(title="Ghostwriter V2", version="2.0.0")

app.include_router(accounts.router)
app.include_router(brands.router)
app.include_router(workflows.router)
app.include_router(templates.router)
app.include_router(source_content.router)
app.include_router(generation.router)
app.include_router(templatize.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
