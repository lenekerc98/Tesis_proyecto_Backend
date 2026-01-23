from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload
from servicios.seguridad import hash_password
from db.modelos import Ave, EjecucionInferencia, SesionUsuario, Usuario

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
# CONSULTAS SESIONES PARA USUARIO LOGEADO
# ------------------------------------------------------------------
def obtener_sesiones(db: Session, usuario):
    query = db.query(SesionUsuario).options(
        joinedload(SesionUsuario.usuario)
    )

    # USUARIO NORMAL SOLO SUS SESIONES
    return (
        query
        .filter(SesionUsuario.id_usuario == usuario.id_usuario)
        .order_by(SesionUsuario.fecha_ingreso.desc())
        .all()
    )


# ------------------------------------------------------------------
# CONSULTAS SESIONES PARA USUARIO ADMIN
# ------------------------------------------------------------------
def obtener_sesiones_admin(db: Session, usuario):
    query = db.query(SesionUsuario).options(
        joinedload(SesionUsuario.usuario)
    )

    # SOLO ADMIN VE TODAS LAS SESIONES
    if usuario.role_id == ADMIN_ROLE_ID:
        return query.order_by(
            SesionUsuario.fecha_ingreso.desc()
        ).all()

# ------------------------------------------------------------------
# CONSULTAS USUARIOS
# ------------------------------------------------------------------
def obtener_usuarios(db: Session):
    return db.query(Usuario).order_by(Usuario.fecha_creacion.desc()).all()

# ------------------------------------------------------------------
# CONSULTAS ESPECIES DE AVE
# ------------------------------------------------------------------
def obtener_aves(db: Session):
    return db.query(Ave).all()

# ------------------------------------------------------------------
# CONSULTAS ESPECIES DE AVE CON MAS PREDICCIONES
# ------------------------------------------------------------------
def obtener_predicciones_mas_frecuentes(db: Session):
    return (
        db.query(
            EjecucionInferencia.prediccion_especie,
            func.count(EjecucionInferencia.prediccion_especie).label("cantidad_prediccion")
        )
        .group_by(EjecucionInferencia.prediccion_especie)
        .order_by(func.count(EjecucionInferencia.prediccion_especie).desc())
        .all()
    )

# ------------------------------------------------------------------
# CONSULTAS ESPECIES DE AVE CON MAS PREDICCIONES POR USUARIO
# ------------------------------------------------------------------
def obtener_predicciones_mas_frecuentes_usuario(db: Session, usuario):
    return (
        db.query(
            EjecucionInferencia.prediccion_especie,
            func.count(EjecucionInferencia.prediccion_especie).label("cantidad_prediccion")
        )
        .filter(EjecucionInferencia.id_usuario == usuario.id_usuario)
        .group_by(EjecucionInferencia.prediccion_especie)
        .order_by(func.count(EjecucionInferencia.prediccion_especie).desc())
        .all()
    )

# ------------------------------------------------------------------
# ACTUALIZAR USUARIO
# ------------------------------------------------------------------
def actualizar_usuario(
    db: Session,
    usuario_id: int,
    datos: dict
):
    usuario = db.query(Usuario).filter(
        Usuario.id_usuario == usuario_id
    ).first()

    if not usuario:
        raise HTTPException(404, "Usuario no encontrado")

    if "nombre_completo" in datos:
        usuario.nombre_completo = datos["nombre_completo"]

    if "password" in datos:
        usuario.password = hash_password(datos["password"])

    if "usuario_activo" in datos:
        usuario.usuario_activo = datos["usuario_activo"]

    db.commit()
    db.refresh(usuario)

    return usuario
