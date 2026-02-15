from fastapi import FastAPI

app = FastAPI(title="NLPDF API")


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "NLPDF API is running"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy"}
