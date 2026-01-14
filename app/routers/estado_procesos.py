from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from servicios import prediccion
from db.database import get_db
import librosa
import tensorflow as tf

router = APIRouter(
    prefix="/v1/estado_procesos",
    tags=["Estado_Procesos"]
)

@router.get("")
def health_check(db: Session = Depends(get_db)):
    estado = {
        "API": "OPERATIVO",
        "BASE DE DATOS": "NO OPERATIVO",
        "MODELO DE INFERENCIA (IA)": "NO OPERATIVO",
        "LIBRERÍAS DE AUDIO": "NO OPERATIVO"
    }

    #Verificar base de datos
    try:
        db.execute(text("SELECT 1"))
        estado["BASE DE DATOS"] = "OPERATIVO"
    except Exception:
        estado["BASE DE DATOS"] = "NO OPERATIVO"

    #Verificar modelo IA
    try:
        model = prediccion.model
        if model is not None:
            estado["MODELO DE INFERENCIA (IA)"] = "MODELO CARGADO"
    except Exception:
        estado["MODELO DE INFERENCIA (IA)"] = "MODELO NO CARGADO"

    #Verificar librerías de audio
    try:
        _ = librosa.__version__
        _ = tf.__version__
        estado["LIBRERÍAS DE AUDIO"] = "OPERATIVO"
    except Exception:
        estado["LIBRERÍAS DE AUDIO"] = "NO OPERATIVO"

    #Estado global
    estado_global = (
        "OK" if all(v == "OPERATIVO" or v == "MODELO CARGADO" for v in estado.values())
        else "DEGRADADO"
    )

    return {
        "ESTADO_SERVIDOR": estado_global,
        "COMPONENTES": estado
    }
