from sqlalchemy.orm import Session
from db.modelos import EjecucionInferencia, MetadatoAudio

ADMIN_ROLE_ID = 0

def registrar_inferencia(
    db: Session,
    id_usuario: int | None,
    prediccion_especie: str,
    confianza: float,
    top_5: dict,
    tiempo_ejecucion: float
):
    log = EjecucionInferencia(
        id_usuario=id_usuario,
        prediccion_especie=prediccion_especie,
        confianza=confianza,
        top_5=top_5,
        tiempo_ejecucion=tiempo_ejecucion
    )

    db.add(log)
    db.commit()


def obtener_inferencias(db: Session, usuario, skip: int = 0, limit: int = None):
    # Contamos el total sin hacer JOIN para que sea muy rápido
    total = (
        db.query(EjecucionInferencia)
        .filter(EjecucionInferencia.id_usuario == usuario.id_usuario)
        .filter(EjecucionInferencia.prediccion_especie.not_ilike("%desconocido%"))
        .count()
    )

    query = (
        db.query(EjecucionInferencia)
        .filter(EjecucionInferencia.id_usuario == usuario.id_usuario)
        .filter(EjecucionInferencia.prediccion_especie.not_ilike("%desconocido%"))
        .outerjoin(MetadatoAudio, EjecucionInferencia.log_id == MetadatoAudio.id_inferencia)
    )
    
    if limit is not None:
        query = query.order_by(EjecucionInferencia.fecha_ejecuta.desc()).offset(skip).limit(limit)
    else:
        query = query.order_by(EjecucionInferencia.fecha_ejecuta.desc())
    return total, query.all()


def obtener_inferencias_admin(db: Session, skip: int = 0, limit: int = None):
    # Contamos el total sin hacer JOIN para que sea muy rápido
    total = (
        db.query(EjecucionInferencia)
        .filter(EjecucionInferencia.prediccion_especie.not_ilike("%desconocido%"))
        .count()
    )

    query = (
        db.query(EjecucionInferencia)
        .filter(EjecucionInferencia.prediccion_especie.not_ilike("%desconocido%"))
        .outerjoin(MetadatoAudio, EjecucionInferencia.log_id == MetadatoAudio.id_inferencia)
    )
    
    if limit is not None:
        query = query.order_by(EjecucionInferencia.fecha_ejecuta.desc()).offset(skip).limit(limit)
    else:
        query = query.order_by(EjecucionInferencia.fecha_ejecuta.desc())
    return total, query.all()


def registrar_metadata_audio(
    db: Session,
    *,
    origen: str,
    formato: str,
    id_usuario: int,
    id_inferencia: int,
    localizacion: str = None,
    latitud: float = None,
    longitud: float = None
):
    metadata = MetadatoAudio(
        origen=origen,
        formato=formato,
        id_usuario=id_usuario,
        id_inferencia=id_inferencia,
        localizacion=localizacion,
        latitud=latitud,
        longitud=longitud
    )

    db.add(metadata)
    db.commit()
    db.refresh(metadata)

    return metadata
