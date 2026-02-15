from fastapi import FastAPI

from backend.routers import compress_router, merge_router, rotate_router, split_router

app = FastAPI(title="NLPDF API", version="0.1.0")

# Include routers
app.include_router(compress_router)
app.include_router(split_router)
app.include_router(merge_router)
app.include_router(rotate_router)


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "NLPDF API is running"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy"}
