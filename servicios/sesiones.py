from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload
from servicios.seguridad import hash_password
from db.modelos import SesionUsuario, Usuario

ADMIN_ROLE_ID = 0

def registrar_sesion_usuario_exito(
    db: Session,
    id_usuario: int,
    estado: str = None,
    ip: str = None,
    agente: str = None,
    observacion: str = "Inicio de sesión exitoso"
):
    sesion = SesionUsuario(
        id_usuario=id_usuario,
        ip_origen=ip,
        agente=agente,
        observacion=observacion,
        estado=estado
    )

    db.add(sesion)
    db.commit()
    db.refresh(sesion)
    return sesion

def registrar_sesion_usuario_fallido(
    db: Session,
    id_usuario: int | None,
    estado: str,
    ip: str,
    agente: str,
    observacion: str = "Intento de inicio de sesión fallido"
):
    if id_usuario is None:
        return  # No se registra si no existe el usuario

    sesion = SesionUsuario(
        id_usuario=id_usuario,
        ip_origen=ip,
        agente=agente,
        observacion=observacion,
        estado=estado
    )

    db.add(sesion)
    db.commit()

# ------------------------------------------------------------------
# CONSULTAS SESIONES
# ------------------------------------------------------------------
def obtener_sesiones(db: Session, usuario):
    query = db.query(SesionUsuario).options(
        joinedload(SesionUsuario.usuario)
    )

    # SOLO ADMIN VE TODAS LAS SESIONES
    if usuario.role_id == ADMIN_ROLE_ID:
        return query.order_by(
            SesionUsuario.fecha_ingreso.desc()
        ).all()

    # USUARIO NORMAL SOLO SUS SESIONES
    return (
        query
        .filter(SesionUsuario.id_usuario == usuario.id_usuario)
        .order_by(SesionUsuario.fecha_ingreso.desc())
        .all()
    )

# ------------------------------------------------------------------
# CONSULTAS USUARIOS
# ------------------------------------------------------------------
def obtener_usuarios(db: Session):
    return db.query(Usuario).order_by(Usuario.fecha_creacion.desc()).all()

# ------------------------------------------------------------------
# ACTUALIZAR USUARIO
# ------------------------------------------------------------------
def actualizar_usuario(
    db: Session,
    usuario_id: int,
    datos: dict
):
    usuario = db.query(Usuario).filter(Usuario.id_usuario == usuario_id).first()

    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    if datos.get("nombre_completo"):
        usuario.nombre_completo = datos["nombre_completo"]

    if datos.get("password"):
        usuario.contraseña_hash = hash_password(datos["password"])

    usuario.fecha_actualizacion = func.now()

    db.commit()
    db.refresh(usuario)

    return usuario