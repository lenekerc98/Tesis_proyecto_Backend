from fastapi import FastAPI
from app.routers import estado_procesos
from app.routers import admin
from app.routers import inferencias
from app.routers import usuarios
from fastapi.staticfiles import StaticFiles


app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(estado_procesos.router)
app.include_router(usuarios.router)
app.include_router(inferencias.router)
app.include_router(admin.router)

