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

# 1. AMPLIAMOS TIPOS PERMITIDOS PARA IPHONE (MP4) Y OTROS MÓVILES
ALLOWED_TYPES = [
    "audio/wav", "audio/mpeg", "audio/mp3", 
    "audio/webm", "video/webm", 
    "audio/mp4", "video/mp4", "audio/aac", "audio/x-m4a"
]

MAX_SIZE_MB = 100
MIN_DURACION = 1.0
MAX_DURACION = 60.0
FFMPEG_PATH = "ffmpeg"

from starlette.concurrency import run_in_threadpool

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
        raise HTTPException(status_code=400, detail=f"Formato {file.content_type} no soportado. Use MP3, WAV, WEBM o MP4.")

    # 3. Validar tamaño
    if len(audio_bytes) > MAX_SIZE_MB * 1024 * 1024:
        registrar_error_sistema(db, f"Tamaño excedido", "valida_tamano_archivo", usuario.id_usuario)
        raise HTTPException(status_code=413, detail="Archivo demasiado grande.")

    # 4. CARGA Y CONVERSIÓN DINÁMICA
    try:
        # Si NO es WAV puro, lo pasamos por FFmpeg para estandarizar (WebM, MP4, MP3 -> WAV)
        if file.content_type != "audio/wav":
            # Ejecutar conversión en threadpool porque es CPU-bound
            audio_bytes = await run_in_threadpool(convertir_audio_a_wav, audio_bytes)

        # Cargar con Librosa (desde memoria)
        # Nota: TARGET_SR debe estar configurado en servicios.prediccion (idealmente 44100 o 48000)
        # Ejecutar carga en threadpool
        y, sr = await run_in_threadpool(
            librosa.load,
            io.BytesIO(audio_bytes),
            sr=TARGET_SR, 
            mono=True
        )
    except Exception as e:
        registrar_error_sistema(db, str(e), "carga_audio", usuario.id_usuario)
        print(f"Error procesando audio: {e}")
        raise HTTPException(status_code=400, detail="Error al procesar el audio. Verifique que el archivo no esté corrupto.")

    # 5. Validar duración
    duracion = len(y) / sr
    if duracion < MIN_DURACION or duracion > MAX_DURACION:
        raise HTTPException(status_code=400, detail="El audio debe durar entre 1 y 60 segundos.")

    # 6. Inferencia
    inicio = perf_counter()
    try:
        # Ejecutar inferencia en threadpool (Heavy CPU usage)
        resultados = await run_in_threadpool(predecir_audio, y, sr, db=db, top_n=5)
    except Exception as e:
        registrar_error_sistema(db, str(e), "proceso_inferencia_modelo", usuario.id_usuario)
        raise HTTPException(status_code=500, detail="Error interno en el modelo de IA.")

    tiempo = perf_counter() - inicio
    prediccion_principal = resultados[0]["nombre_cientifico"]
    confianza = resultados[0]["probabilidad"]
    imagen_url = obtener_imagen_ave(db, prediccion_principal)

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
    
    log_actual = db.query(EjecucionInferencia).order_by(EjecucionInferencia.log_id.desc()).first()
    log_id_actual = log_actual.log_id if log_actual else 0

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
# FUNCION CONVERSION UNIVERSAL (FFMPEG IN-MEMORY)
#--------------------------------------------------
def convertir_audio_a_wav(audio_bytes: bytes) -> bytes:
    """
    Convierte cualquier formato (MP4, WEBM, MP3) a WAV PCM 
    usando FFmpeg en memoria con alta calidad (44.1kHz).
    """
    try:
        proceso = subprocess.Popen(
            [
                FFMPEG_PATH,
                "-loglevel", "error",
                "-i", "pipe:0",  # Entrada stdin
                "-ar", "44100",  # IMPORTANTE: Subimos a 44.1kHz para captar agudos de aves
                "-ac", "1",      # Mono
                "-f", "wav",     # Salida WAV
                "pipe:1"         # Salida stdout
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        wav_bytes, stderr = proceso.communicate(audio_bytes)

        if proceso.returncode != 0:
            error_msg = stderr.decode()
            print(f"Error FFMPEG: {error_msg}")
            raise RuntimeError(f"FFmpeg falló: {error_msg}")

        return wav_bytes

    except Exception as e:
        raise RuntimeError(f"Error convirtiendo audio a WAV: {str(e)}")


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
            "especie_usuario": i.especie_usuario,
            "top_5": i.top_5
        }
        for i in inferencias
    ]

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

#-----------------------------------------------------------
# AÑADIR ESPECIE INDICADA POR USUARIO A LA INFERENCIA
#-----------------------------------------------------------
@router.post("/especie_usuario")
def agregar_especie_usuario(
    log_id: int = Form(...),
    especie_usuario: str = Form(...),
    db: Session = Depends(get_db),
    usuario = Depends(get_current_user)
):

    inferencia = db.query(EjecucionInferencia).filter(EjecucionInferencia.log_id == log_id).first()

    if not inferencia:
        raise HTTPException(status_code=404, detail="Inferencia no encontrada.")

    if inferencia.id_usuario != usuario.id_usuario:
        raise HTTPException(status_code=403, detail="No tienes permiso para modificar esta inferencia.")

    inferencia.especie_usuario = especie_usuario
    db.commit()

    return {"mensaje": "Especie de usuario añadida a la inferencia."}
    
#---------------------------------------------------------------
# GUARDAR GRABACION EN S3 Y REGISTRAR URL EN LOG DE INFERENCIA
#---------------------------------------------------------------
def guardar_grabacion_s3(
    audio_bytes: bytes,
    meta: UploadFile = File(...),
    log_id: int = Form(...),
    db: Session = Depends(get_db)
    ):

    # Configuración de AWS S3
    aws_access_key_id = "dummy"
    aws_secret_access_key = "summy"
    s3 = boto3.client('s3', aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key, region_name='us-east-1')
    bucket_name = 'aves-cerro-blanco-img'
    object_key = f"grabaciones/{int(log_id)}_{meta.filename}"

    try:
        # Subir archivo a S3
        s3.put_object(Body=audio_bytes, Bucket=bucket_name, Key=object_key)

        # Obtener URL pública del archivo subido
        url_grabacion = f"https://{bucket_name}.s3.us-east-1.amazonaws.com/{object_key}"

        # Actualizar registro de inferencia con URL de grabación
        inferencia = db.query(EjecucionInferencia).filter(EjecucionInferencia.log_id == log_id).first()

        if not inferencia:
            raise HTTPException(status_code=404, detail="Inferencia no encontrada.")

        inferencia.url_grabacion = url_grabacion
        db.commit()

        return {"mensaje": "Grabación guardada en S3 y URL registrada en la inferencia."}

    except Exception as e:
        registrar_error_sistema(
            db,
            mensaje_error=str(e),
            fuente="guardar_grabacion_s3",
            id_usuario=db.query(EjecucionInferencia).filter(EjecucionInferencia.log_id == log_id).first().id_usuario if db.query(EjecucionInferencia).filter(EjecucionInferencia.log_id == log_id).first() else None
        )
        raise HTTPException(status_code=500, detail="Error al guardar la grabación, intente de nuevo más tarde.")

