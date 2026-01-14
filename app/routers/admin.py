from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from servicios.sesiones import obtener_usuarios
from db.database import get_db
from servicios.seguridad import get_current_user, require_admin
from servicios.log_errores import obtener_logs_error

router = APIRouter(
    prefix="/v1/admin/logs",
    tags=["Administración"]
)

@router.get("/errores")
def listar_logs_error(
    limite: int = 0,
    db: Session = Depends(get_db),
    admin = Depends(require_admin)
):
    logs = obtener_logs_error(db, limite)

    return [
        {
            "id_log": log.id_log_sis,
            "mensaje_error": log.mensaje_error,
            "fuente": log.fuente,
            "fecha": log.fecha_general_log,
            "id_usuario": log.id_usuario
        }
        for log in logs
    ]

@router.get("/listar_usuarios")
def listar_usuarios(
    db: Session = Depends(get_db),
    usuario = Depends(get_current_user)
):

    # Solo admins
    if usuario.role_id != 0:
        raise HTTPException(
            status_code=403,
            detail="Acceso denegado, solo administradores pueden acceder a esta información."
        )

    usuarios = obtener_usuarios(db)

    return [
        {
            "rol": "admin" if u.role_id == 0 else "usuario",
            "id_usuario": u.id_usuario,
            "Nombre completo": u.nombre_completo,
            "usuario": u.usuario,
            "email": u.email,
            "telefono": u.telefono,
            "fecha_creacion": u.fecha_creacion.strftime("%d-%m-%Y %H:%M:%S")
        }
        for u in usuarios
    ]