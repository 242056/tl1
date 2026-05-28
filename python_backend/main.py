from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from python_backend.core.api import router

app = FastAPI(title="VTB MVP Python")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(router)
app.mount("/", StaticFiles(directory="frontend/src", html=True), name="static")
