import os
from dotenv import load_dotenv
from fastapi import FastAPI

from api.admin import router as admin_router

load_dotenv()

app = FastAPI(title="Centinela API", version="0.1.0")

app.include_router(admin_router)


@app.get("/health")
def health():
    return {"status": "ok"}
