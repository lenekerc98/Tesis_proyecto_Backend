from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from servicios.sesiones import actualizar_usuario, obtener_aves, obtener_predicciones_mas_frecuentes, obtener_predicciones_mas_frecuentes_usuario, obtener_sesiones, obtener_usuario_nombre, obtener_usuarios, registrar_sesion_usuario_exito, registrar_sesion_usuario_fallido
from db.database import get_db
from servicios import esquema
from db import modelos
from servicios.seguridad import get_current_user, hash_password
from servicios.seguridad import verify_password, create_access_token

#--------------------------------------------------
# RUTAS GESTION USUARIOS 
#--------------------------------------------------

router = APIRouter(prefix="/v1/usuarios", tags=["Gestion_Usuarios"])

#--------------------------------------------------
# Registro de usuario en sistema.
#--------------------------------------------------

@router.post("/registro")
def register(user: esquema.UserCreate, db: Session = Depends(get_db)):
    role = db.query(modelos.Role).filter_by(name=user.role).first()
    if not role:
        raise HTTPException(400, "Rol inválido.")

    new_user = modelos.Usuario(
        email=user.email,
        nombre_completo=user.nombre_completo,
        contraseña_hash=hash_password(user.password),
        role_id=role.id_rol
    )
    db.add(new_user)
    db.commit()
    return {"mensaje": "Usuario creado correctamente, por favor inicie sesión."}

#--------------------------------------------------
# LOGIN DEL SISTEMA.
#--------------------------------------------------
@router.post("/login")
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    usuario = db.query(modelos.Usuario).filter(
        modelos.Usuario.email == form_data.username
    ).first()

    if not usuario:
        raise HTTPException(
            status_code=401,
            detail="Credenciales inválidas, intente de nuevo."
        )
    if not usuario.usuario_activo:
        registrar_sesion_usuario_fallido(
            db=db,
            id_usuario=usuario.id_usuario,
            estado="FALLIDO",
            ip=request.client.host,
            agente=request.headers.get("user-agent"),
            observacion="Usuario inactivo"
        )
        raise HTTPException(
            status_code=403,
            detail="Usuario inactivo. Contacte al administrador."
        )

    if not verify_password(form_data.password, usuario.contraseña_hash):
        #registrar intento fallido
        registrar_sesion_usuario_fallido(
            db=db,
            id_usuario=usuario.id_usuario,
            estado="FALLIDO",
            ip=request.client.host,
            agente=request.headers.get("user-agent"),
            observacion="Contraseña incorrecta"
        )


    # SOLO SI TODO FUE CORRECTO
    registrar_sesion_usuario_exito(
        db=db,
        id_usuario=usuario.id_usuario,
        estado="EXITOSO",
        ip=request.client.host,
        agente=request.headers.get("user-agent"),
        observacion="Inicio de sesión exitoso."
    )

    access_token = create_access_token(
        data={"sub": usuario.email}
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "usuario": {
            "email": usuario.email,
            "nombre_completo": usuario.nombre_completo,
            "role_id": usuario.role_id
        }
    }

#--------------------------------------------------
# RUTAS PROTEGIDAS - USUARIOS LOGEADOS
#--------------------------------------------------
@router.get("/Listar_sesiones")
def listar_sesiones(
    db: Session = Depends(get_db),
    usuario = Depends(get_current_user)
):
    sesiones = obtener_sesiones(db, usuario)

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


#--------------------------------------------------
# CONSULTA USUARIOS SISTEMA POR NOMBRE
#--------------------------------------------------
@router.get("/buscar_usuarios")
def buscar_usuarios(
    nombre: str,
    db: Session = Depends(get_db),
    usuario = Depends(get_current_user)
):
    usuarios = obtener_usuario_nombre(db, nombre)

    return [
        {
            "id_usuario": u.id_usuario,
            "email": u.email,
            "nombre_completo": u.nombre_completo,
            "role": "admin" if u.role_id == 0 else "usuario",
            "usuario_activo": u.usuario_activo
        }
        for u in usuarios
    ]

#--------------------------------------------------
# ACTUALIZAR PERFIL USUARIO
#--------------------------------------------------

@router.put("/actualiza_usuario")
def actualizar_perfil(
    data: esquema.UsuarioUpdateRequest,
    db: Session = Depends(get_db),
    usuario = Depends(get_current_user)
):
    if not data.dict(exclude_unset=True):
        raise HTTPException(
            status_code=400,
            detail="Debe enviar al menos un campo para actualizar"
        )

    usuario_actualizado = actualizar_usuario(
        db=db,
        usuario_id=usuario.id_usuario,
        datos=data.dict(exclude_unset=True)
    )

    return {
        "mensaje": "Perfil actualizado correctamente",
        "nombre_completo": usuario_actualizado.nombre_completo,
        "usuario_activo": usuario_actualizado.usuario_activo
    }

@router.get("/me")
def read_users_me(usuario = Depends(get_current_user)):
    """
    Devuelve los datos del usuario logueado basándose en el token.
    No requiere parámetros.
    """
    return {
        "id_usuario": usuario.id_usuario,
        "email": usuario.email,
        "nombre_completo": usuario.nombre_completo,
        "role_id": usuario.role_id,
        "role": "admin" if usuario.role_id == 0 else "usuario",
        "usuario_activo": usuario.usuario_activo
    }
#--------------------------------------------------