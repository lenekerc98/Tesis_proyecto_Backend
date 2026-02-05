from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from db import modelos
from servicios.hist_inferencias import obtener_inferencias_admin
# IMPORTANTE: Agregamos 'actualizar_usuario' a los imports
from servicios.prediccion import obtener_imagen_ave
from servicios.sesiones import actualizar_usuario, obtener_sesiones_admin, obtener_usuario_nombre, obtener_usuarios, obtener_usuarios_inactivos_nombre
from db.database import get_db
from servicios.seguridad import get_current_user, require_admin
from servicios.log_errores import obtener_logs_error

router = APIRouter(
    prefix="/v1/admin/logs",
    tags=["Administración"]
)

# ---------------------------------------------------------
# 1. ESQUEMA DE DATOS PARA EDICIÓN
# ---------------------------------------------------------
class EdicionUsuarioAdmin(BaseModel):
    nombre_completo: str
    email: str
    usuario_activo: bool
    password: Optional[str] = None  # Opcional, si viene vacío no se toca

# ---------------------------------------------------------
# 2. ENDPOINTS EXISTENTES
# ---------------------------------------------------------

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
            "id_usuario": log.id_usuario,
            # Nota: log_errores no suele tener usuario_activo, revisa tu modelo si esto da error
            # "usuario_activo": log.usuario_activo 
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
            "email": u.email,
            "fecha_creacion": u.fecha_creacion.strftime("%d-%m-%Y %H:%M:%S"),
            "usuario_activo": u.usuario_activo
        }
        for u in usuarios
    ]


@router.get("/Listar_sesiones")
def listar_sesiones(
    db: Session = Depends(get_db),
    usuario = Depends(get_current_user)
):
     # Solo admins
    if usuario.role_id != 0:
        raise HTTPException(
            status_code=403,
            detail="Acceso denegado, solo administradores pueden acceder a esta información."
        )
    
    sesiones = obtener_sesiones_admin(db, usuario)

    return [
        {
            "usuario": {
                "id": s.usuario.id_usuario,
                "email": s.usuario.email,
                "rol": "admin" if s.usuario.role_id == 0 else "usuario",
            },
            "fecha_ingreso": s.fecha_ingreso,
            "ip_origen": s.ip_origen,
            "agente": s.agente,
            "estado": s.estado,
            "observacion": s.observacion
        }
        for s in sesiones
    ]

@router.get("/historial")
def listar_inferencias(
    db: Session = Depends(get_db),
    usuario = Depends(get_current_user)

):
    inferencias = obtener_inferencias_admin(db)

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

@router.get("/usuarios_inactivos/buscar")
def buscar_usuarios_inactivos(
    nombre: str,
    db: Session = Depends(get_db),
    admin = Depends(require_admin)
):
    usuarios = obtener_usuarios_inactivos_nombre(db, nombre)
    
    if not usuarios:
        raise HTTPException(404, "No se encontraron usuarios inactivos con ese nombre")

    return [
        {
            "id_usuario": u.id_usuario,
            "nombre_completo": u.nombre_completo,
            "email": u.email,
            "fecha_desactivacion": u.fecha_actualizacion
        }
        for u in usuarios
    ]

# ---------------------------------------------------------
# 3. NUEVO ENDPOINT DE EDICIÓN COMPLETA (Reutilizando Servicio)
# ---------------------------------------------------------
@router.put("/usuarios/{id_usuario}/editar")
def editar_usuario_admin(
    id_usuario: int,
    datos: EdicionUsuarioAdmin,
    db: Session = Depends(get_db),
    admin = Depends(require_admin)
):
    # Convertimos el modelo Pydantic a diccionario, eliminando los nulos (como password si viene vacio)
    datos_dict = datos.dict(exclude_unset=True)

    # Lógica específica de Admin: Manejo de fechas al activar/desactivar
    # Agregamos manualmente la fecha al diccionario si es necesario
    if "usuario_activo" in datos_dict:
        if not datos_dict["usuario_activo"]:
            datos_dict["fecha_desactivacion"] = datetime.now()
        else:
            datos_dict["fecha_desactivacion"] = None

    # Llamamos a TU servicio existente 'actualizar_usuario'.
    # Este servicio ya sabe que si recibe 'password', debe hashearla.
    try:
        usuario_actualizado = actualizar_usuario(
            db=db,
            usuario_id=id_usuario,
            datos=datos_dict
        )
    except Exception as e:
        # Manejo básico de errores si el usuario no existe o falla la BD
        raise HTTPException(status_code=400, detail=f"Error al actualizar: {str(e)}")

    return {
        "mensaje": "Usuario actualizado correctamente",
        "nombre_completo": usuario_actualizado.nombre_completo,
        "usuario_activo": usuario_actualizado.usuario_activo
    }

@router.put("/usuarios/{id_usuario}/reactivar")
def reactivar_usuario(
    id_usuario: int,
    db: Session = Depends(get_db),
    admin = Depends(require_admin)
):
    usuario = db.query(modelos.Usuario).filter(
        modelos.Usuario.id_usuario == id_usuario
    ).first()

    if not usuario:
        raise HTTPException(404, "Usuario no encontrado")

    if usuario.usuario_activo:
        raise HTTPException(400, "El usuario ya está activo")

    usuario.usuario_activo = True
    usuario.fecha_desactivacion = None

    db.commit()

    return {
        "mensaje": f"Usuario {usuario.nombre_completo} reactivado correctamente"

    }

