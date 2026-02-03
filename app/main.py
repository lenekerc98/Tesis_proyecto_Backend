from fastapi import FastAPI
from app.routers import estado_procesos, admin, inferencias, usuarios
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Backend de Tesis de Aves funcionando"}

@app.get("/fast_health_check")
def health():
    return {"status": "ok"}

app.include_router(estado_procesos.router)
app.include_router(usuarios.router)
app.include_router(inferencias.router)
app.include_router(admin.router)

