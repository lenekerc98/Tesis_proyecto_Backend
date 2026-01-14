# servicios/logs_error.py
from sqlalchemy.orm import Session
from db.modelos import LogErrorSistema

def registrar_error_sistema(
    db: Session,
    mensaje_error: str,
    fuente: str,
    id_usuario: int
):
    log = LogErrorSistema(
        mensaje_error=mensaje_error,
        fuente=fuente,
        id_usuario=id_usuario
    )
    db.add(log)
    db.commit()


def obtener_logs_error(db: Session, limite: int):
    if limite == 0:
        limite = 100  # Valor por defecto si no se especifica límite

    return (
        db.query(LogErrorSistema)
        .order_by(LogErrorSistema.fecha_general_log.desc())
        .limit(limite)
        .all()
    )