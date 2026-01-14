from time import perf_counter
from fastapi import APIRouter, Form, UploadFile, File, Depends, HTTPException
import librosa
from sqlalchemy.orm import Session
from db.modelos import EjecucionInferencia
from servicios.log_errores import registrar_error_sistema
from servicios.hist_inferencias import obtener_inferencias, registrar_inferencia, registrar_metadata_audio
from servicios.seguridad import get_current_user
from servicios.prediccion import TARGET_SR, predecir_audio
from db.database import get_db
import io


router = APIRouter(prefix="/v1/inferencia", tags=["Inferencia"])

ALLOWED_TYPES = ["audio/wav", "audio/mpeg", "audio/webm", "audio/mp3"]
MAX_SIZE_MB = 100
MIN_DURACION = 1.0
MAX_DURACION = 60.0

@router.post("/procesar_inferencia")
async def upload_audio(
    file: UploadFile = File(...),
    latitud: float = Form(None),
    longitud: float = Form(None),
    localizacion: str = Form(None),
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user)
):
    
    # 1. Leer archivo
    try:
        audio_bytes = await file.read()
    except Exception as e:
        registrar_error_sistema(
            db,
            mensaje_error=str(e),
            fuente="lectura_archivo",
            id_usuario=usuario.id_usuario
        )
        raise HTTPException(status_code=400, detail="No se pudo leer el archivo, intente de nuevo.")

    # 2. Validar tipo MIME
    if file.content_type not in ALLOWED_TYPES:
        registrar_error_sistema(
            db,
            mensaje_error=f"Tipo no permitido: {file.content_type}",
            fuente="valida_tipo_archivo",
            id_usuario=usuario.id_usuario
        )
        raise HTTPException(status_code=400, detail="Formato de archivo no soportado, asegurse de subir un archivo de audio válido.")

    # 3. Validar tamaño
    if len(audio_bytes) > MAX_SIZE_MB * 1024 * 1024:
        registrar_error_sistema(
            db,
            mensaje_error=f"Tamaño excedido: {len(audio_bytes)} bytes",
            fuente="valida_tamano_archivo",
            id_usuario=usuario.id_usuario
        )
        raise HTTPException(status_code=413, detail="Archivo demasiado grande, el tamaño máximo es 100 MB.")

    # 4. Cargar audio con librosa
    try:
        y, sr = librosa.load(io.BytesIO(audio_bytes), sr=TARGET_SR)
    except Exception as e:
        registrar_error_sistema(
            db,
            mensaje_error=str(e),
            fuente="carga_audio_librosa",
            id_usuario=usuario.id_usuario
        )
        raise HTTPException(status_code=400, detail="Archivo no es un audio válido, intente con otro archivo.")

    # 5. Validar duración
    duracion = len(y) / sr
    if duracion < MIN_DURACION or duracion > MAX_DURACION:
        registrar_error_sistema(
            db,
            mensaje_error=f"Duración inválida: {duracion:.2f}s",
            fuente="valida_duracion_audio",
            id_usuario=usuario.id_usuario
        )
        raise HTTPException(status_code=400, detail="Duración de audio no válida, debe ser entre 1 y 60 segundos.")

    # 6. Inferencia
    inicio = perf_counter()
    try:
        resultados = predecir_audio(
            y, 
            sr,
            db=db,
            top_n=5
        )
    except Exception as e:
        registrar_error_sistema(
            db,
            mensaje_error=str(e),
            fuente="proceso_inferencia_modelo",
            id_usuario=usuario.id_usuario
        )
        raise HTTPException(status_code=500, detail="Error durante la inferencia, intente de nuevo más tarde.")

    tiempo = perf_counter() - inicio
    prediccion_principal = resultados[0]["nombre_cientifico"]
    confianza = resultados[0]["probabilidad"]

    registrar_inferencia(
       db=db,
       id_usuario=usuario.id_usuario,
       prediccion_especie=prediccion_principal,
       confianza=confianza,
       top_5=resultados,
       tiempo_ejecucion=tiempo
)
    
    registrar_metadata_audio(
        db=db,
        origen="Carga_desde_API",
        formato=file.content_type,
        id_usuario=usuario.id_usuario,
        id_inferencia=db.query(EjecucionInferencia).order_by(EjecucionInferencia.log_id.desc()).first().log_id,
        latitud=latitud if latitud else 0.0,
        longitud=longitud if longitud else 0.0,
        localizacion=localizacion if localizacion else 'No especificada'
    )


    return {
        "usuario": usuario.nombre_completo,
        "archivo": file.filename,
        "duracion_audio": f"{duracion:.2f} segundos.",
        "tiempo_ejecucion": f"{tiempo:.2f} segundos.",
        "predicciones": resultados
    }

@router.get("/historial")
def listar_inferencias(
    db: Session = Depends(get_db),
    usuario = Depends(get_current_user)
):
    inferencias = obtener_inferencias(db, usuario)

    return [
        {
            "log_id": i.log_id,
            "prediccion": i.prediccion_especie,
            "confianza": i.confianza,
            "top_5": i.top_5,
            "tiempo_ejecucion": i.tiempo_ejecucion,
            "fecha": i.fecha_ejecuta
        }
        for i in inferencias
    ]