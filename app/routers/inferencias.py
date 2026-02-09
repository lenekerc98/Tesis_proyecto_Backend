from time import perf_counter
from fastapi import APIRouter, Form, UploadFile, File, Depends, HTTPException
import librosa
from sqlalchemy.orm import Session
from servicios.sesiones import obtener_aves, obtener_predicciones_mas_frecuentes, obtener_predicciones_mas_frecuentes_usuario
from db import modelos
from db.modelos import EjecucionInferencia
from servicios.log_errores import registrar_error_sistema
from servicios.hist_inferencias import obtener_inferencias, registrar_inferencia, registrar_metadata_audio
from servicios.seguridad import get_current_user
from servicios.prediccion import TARGET_SR, obtener_imagen_ave, predecir_audio
from db.database import get_db
import io
import subprocess


router = APIRouter(prefix="/v1/inferencia", tags=["Inferencia"])

# 1. AMPLIAMOS TIPOS PERMITIDOS PARA IPHONE (MP4)
ALLOWED_TYPES = [
    "audio/wav", "audio/mpeg", "audio/mp3", 
    "audio/webm", "video/webm", 
    "audio/mp4", "video/mp4", "audio/aac"
]
MAX_SIZE_MB = 100
MIN_DURACION = 1.0
MAX_DURACION = 60.0
FFMPEG_PATH = "ffmpeg"

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
        registrar_error_sistema(db, str(e), "lectura_archivo", usuario.id_usuario)
        raise HTTPException(status_code=400, detail="No se pudo leer el archivo.")

    # 2. Validar tipo MIME
    if file.content_type not in ALLOWED_TYPES:
        registrar_error_sistema(db, f"Tipo no permitido: {file.content_type}", "valida_tipo_archivo", usuario.id_usuario)
        raise HTTPException(status_code=400, detail=f"Formato {file.content_type} no soportado.")

    # 3. Validar tamaño
    if len(audio_bytes) > MAX_SIZE_MB * 1024 * 1024:
        registrar_error_sistema(db, f"Tamaño excedido", "valida_tamano_archivo", usuario.id_usuario)
        raise HTTPException(status_code=413, detail="Archivo demasiado grande.")

    # 4. CARGA Y CONVERSIÓN DINÁMICA
    try:
        # Si no es WAV, lo pasamos por FFmpeg para asegurar compatibilidad y calidad
        if file.content_type != "audio/wav":
            # Esta función ahora maneja webm, mp4, mp3, etc.
            audio_bytes = convertir_audio_a_wav(audio_bytes)

        y, sr = librosa.load(
            io.BytesIO(audio_bytes),
            sr=TARGET_SR,
            mono=True
        )
    except Exception as e:
        registrar_error_sistema(db, str(e), "carga_audio", usuario.id_usuario)
        raise HTTPException(status_code=400, detail="Error al procesar el audio.")

    # 5. Validar duración
    duracion = len(y) / sr
    if duracion < MIN_DURACION or duracion > MAX_DURACION:
        raise HTTPException(status_code=400, detail="El audio debe durar entre 1 y 60 segundos.")

    # 6. Inferencia
    inicio = perf_counter()
    try:
        resultados = predecir_audio(y, sr, db=db, top_n=5)
    except Exception as e:
        registrar_error_sistema(db, str(e), "proceso_inferencia_modelo", usuario.id_usuario)
        raise HTTPException(status_code=500, detail="Error en el modelo de IA.")

    tiempo = perf_counter() - inicio
    prediccion_principal = resultados[0]["nombre_cientifico"]
    confianza = resultados[0]["probabilidad"]
    imagen_url = obtener_imagen_ave(db, prediccion_principal)

    # Registrar en DB
    registrar_inferencia(
       db=db,
       id_usuario=usuario.id_usuario,
       prediccion_especie=prediccion_principal,
       confianza=confianza,
       top_5=resultados,
       tiempo_ejecucion=tiempo
    )
    
    log_id_actual = db.query(EjecucionInferencia).order_by(EjecucionInferencia.log_id.desc()).first().log_id

    registrar_metadata_audio(
        db=db,
        origen="Carga_desde_API",
        formato=file.content_type,
        id_usuario=usuario.id_usuario,
        id_inferencia=log_id_actual,
        latitud=latitud if latitud else 0.0,
        longitud=longitud if longitud else 0.0,
        localizacion=localizacion if localizacion else 'No especificada'
    )

    return {
        "prediccion_principal": {
            "usuario": usuario.nombre_completo,
            "archivo": file.filename,
            "duracion_audio": f"{duracion:.2f} s",
            "tiempo_ejecucion": f"{tiempo:.2f} s",
            "especie": prediccion_principal,
            "probabilidad": confianza,
            "url_imagen": imagen_url
        },
        "top_5_predicciones": resultados
    }

#--------------------------------------------------
# MEJORA: FUNCIÓN DE CONVERSIÓN UNIVERSAL
#--------------------------------------------------
def convertir_audio_a_wav(audio_bytes: bytes) -> bytes:
    """Convierte cualquier formato de audio a WAV PCM usando FFmpeg en memoria"""
    try:
        proceso = subprocess.Popen(
            [
                FFMPEG_PATH,
                "-loglevel", "error",
                "-i", "pipe:0", # Entrada desde memoria
                "-ar", "44100", # Subimos a 44.1kHz para mejor calidad de captura
                "-ac", "1",     # Mono para el modelo
                "-f", "wav",
                "pipe:1"        # Salida a memoria
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        wav_bytes, stderr = proceso.communicate(audio_bytes)

        if proceso.returncode != 0:
            raise RuntimeError(stderr.decode())

        return wav_bytes

    except Exception as e:
        raise RuntimeError(f"Error en FFmpeg: {str(e)}")

#--------------------------------------------------
# LISTAR HISTORIAL DE INFERENCIAS
#--------------------------------------------------

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
            "tiempo_ejecucion": i.tiempo_ejecucion,
            "fecha": i.fecha_ejecuta,
            "usuario": db.query(modelos.Usuario).filter(modelos.Usuario.id_usuario == i.id_usuario).first().nombre_completo if i.id_usuario else "Anónimo",
            "ubicacion": i.meta_audio.localizacion if i.meta_audio else "No disponible",
            "url_imagen": obtener_imagen_ave(db, i.prediccion_especie),
            "latitud": i.meta_audio.latitud if i.meta_audio else None,
            "longitud": i.meta_audio.longitud if i.meta_audio else None,
            "top_5": i.top_5
        }
        for i in inferencias
    ]
#--------------------------------------------------
# FUNCION CONVERSION WEBM A WAV (FFMPEG IN-MEMORY)
#--------------------------------------------------
def convertir_webm_a_wav(audio_bytes: bytes) -> bytes:

#Convierte audio WEBM (Opus) a WAV PCM 16kHz mono usando FFmpeg (in-memory)

    try:
        proceso = subprocess.Popen(
            [
                FFMPEG_PATH,
                "-loglevel", "error",
                "-i", "pipe:0",
                "-ar", "16000",
                "-ac", "1",
                "-f", "wav",
                "pipe:1"
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        wav_bytes, stderr = proceso.communicate(audio_bytes)

        if proceso.returncode != 0:
            raise RuntimeError(stderr.decode())

        return wav_bytes

    except Exception as e:
        raise RuntimeError(f"Error convirtiendo WEBM a WAV: {str(e)}")


#--------------------------------------------------
# LISTAR AVES REGISTRADAS EN SISTEMA
#--------------------------------------------------
@router.get("/listar_aves")
def listar_aves(
    db: Session = Depends(get_db),
    usuario = Depends(get_current_user)
):

    aves = obtener_aves(db)

    return [
        {
            "id_ave": u.id_ave,
            "nombre_cientifico": u.nombre_cientifico,
            "nombre": u.nombre,
            "imagen_url": u.url_imagen,
            "audio_url": u.url_audio
        }
        for u in aves
    ]

#--------------------------------------------------
# LISTAR PREDICCIONES MAS FRECUENTES
#--------------------------------------------------
@router.get("/predicciones_mas_frecuentes_general")
def predicciones_mas_frecuentes(
    db: Session = Depends(get_db),
    usuario = Depends(get_current_user)
):
  
    resultados = obtener_predicciones_mas_frecuentes(db)

    return [
        {
            "prediccion_especie": r.prediccion_especie,
            "cantidad": r.cantidad_prediccion
        }
        for r in resultados
    ]

#--------------------------------------------------
# LISTAR PREDICCIONES MAS FRECUENTES POR USUARIO
#--------------------------------------------------
@router.get("/predicciones_mas_frecuentes_usuario")
def predicciones_mas_frecuentes_usuario(
    db: Session = Depends(get_db),
    usuario = Depends(get_current_user)
):

    resultados = obtener_predicciones_mas_frecuentes_usuario(db, usuario)

    return {
        "usuario": usuario.nombre_completo,
        "predicciones": [
            {
                "prediccion_especie": r.prediccion_especie,
                "cantidad": r.cantidad_prediccion
            }
            for r in resultados
        ]

    }
