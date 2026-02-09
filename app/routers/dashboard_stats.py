from fastapi import APIRouter, Depends
from requests import Session
from sqlalchemy import func, desc
from datetime import datetime, timedelta

from db import modelos
from db.database import get_db
from servicios.prediccion import obtener_imagen_ave
from servicios.seguridad import require_admin
# Asegúrate de importar tus modelos y dependencias correctamente
# from ... import modelos, get_db, require_admin, obtener_imagen_ave 

router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"]
)


@router.get("/dashboard_stats")
def obtener_estadisticas_dashboard(
    db: Session = Depends(get_db),
    usuario = Depends(require_admin) # Solo admin puede ver esto
):
    hoy = datetime.now().date()
    inicio_semana = hoy - timedelta(days=hoy.weekday()) # Lunes de esta semana

    # 1. USUARIOS CON SESIÓN HOY (Logins exitosos hoy)
    # CORRECCIÓN: Usamos modelos.SesionUsuario (no Sesion)
    logins_hoy = db.query(modelos.SesionUsuario).filter(
        func.date(modelos.SesionUsuario.fecha_ingreso) == hoy,
        modelos.SesionUsuario.estado == "EXITOSO"
    ).count()

    # 2. TOTAL USUARIOS ACTIVOS
    usuarios_activos = db.query(modelos.Usuario).filter(modelos.Usuario.usuario_activo == True).count()

    # 3. FUNCIÓN AUXILIAR PARA OBTENER EL TOP 1 AVE
    def obtener_top_ave(filtro_fecha=None):
        query = db.query(
            modelos.EjecucionInferencia.prediccion_especie,
            func.count(modelos.EjecucionInferencia.prediccion_especie).label('total')
        )
        
        # Filtro de fecha opcional
        if filtro_fecha:
            query = query.filter(modelos.EjecucionInferencia.fecha_ejecuta >= filtro_fecha)
            
        # Agrupamos y ordenamos
        top = query.group_by(modelos.EjecucionInferencia.prediccion_especie)\
                   .order_by(desc('total'))\
                   .first()
        
        if top:
            # Buscamos la URL de la imagen usando tu servicio existente
            # Si no hay imagen, mandamos None para que el frontend ponga una por defecto
            try:
                url_imagen = obtener_imagen_ave(db, top.prediccion_especie)
            except:
                url_imagen = None

            return {
                "especie": top.prediccion_especie, 
                "total": top.total, 
                "imagen": url_imagen
            }
        return None

    # 4. EJECUTAMOS LAS CONSULTAS
    top_general = obtener_top_ave() # Histórico completo
    top_semana = obtener_top_ave(inicio_semana) # Desde el lunes
    top_dia = obtener_top_ave(datetime.now().replace(hour=0, minute=0, second=0)) # Desde hoy a las 00:00

    # 5. RETORNAMOS JSON ESTRUCTURADO
    return {
        "metricas": {
            "logins_hoy": logins_hoy,
            "usuarios_totales": usuarios_activos
        },
        "tops": {
            "general": top_general,
            "semana": top_semana,
            "dia": top_dia
        }
    }
