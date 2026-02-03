from fastapi import FastAPI
from app.routers import estado_procesos
from app.routers import admin
from app.routers import inferencias
from app.routers import usuarios
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles


app = FastAPI()

#app.mount("../static", StaticFiles(directory="static"), name="static")

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
app.include_router(estado_procesos.router)
app.include_router(usuarios.router)
app.include_router(inferencias.router)
app.include_router(admin.router)

if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port)