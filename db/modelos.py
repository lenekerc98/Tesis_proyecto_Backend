from sqlalchemy import Date, Float, Column, DateTime, Integer, String, Boolean, ForeignKey, Time, func
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from .database import Base

class Role(Base):
    __tablename__ = "roles"
    id_rol = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    descripcion = Column(String)

class Usuario(Base):
    __tablename__ = "usuarios"
    id_usuario = Column(Integer, primary_key=True)
    email = Column(String, unique=True)
    fecha_creacion = Column(DateTime(timezone=True), server_default=func.now())
    fecha_actualizacion = Column(DateTime(timezone=True), onupdate=func.now())
    nombre_completo = Column(String)
    contraseña_hash = Column(String)
    usuario_activo = Column(Boolean, default=True)
    role_id = Column(Integer, ForeignKey("roles.id_rol"))
    role = relationship("Role")
    sesiones = relationship("SesionUsuario", back_populates="usuario")

class Ave(Base):
    __tablename__ = "aves"
    id_ave = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, nullable=True)
    nombre_cientifico = Column(String, nullable=False)
    localizaciones = Column(JSONB, nullable=True)
    descripcion = Column(String, nullable=True)

class SesionUsuario(Base):
    __tablename__ = "sesiones_usuarios"
    id_sesion = Column(Integer, primary_key=True, index=True)
    id_usuario = Column(Integer, ForeignKey("usuarios.id_usuario"), nullable=False)
    fecha_ingreso = Column(DateTime(timezone=True), server_default=func.now())
    ip_origen = Column(String(45), nullable=True)
    agente = Column(String, nullable=True)
    observacion = Column(String, nullable=True)
    estado = Column(String, nullable=False)
    usuario = relationship("Usuario", back_populates="sesiones")

class EjecucionInferencia(Base):
    __tablename__ = "ejecuciones_inferencias"
    log_id = Column(Integer, primary_key=True, index=True)
    id_usuario = Column(Integer,ForeignKey("usuarios.id_usuario"),nullable=True)
    prediccion_especie = Column(String)
    confianza = Column(Float)
    top_5 = Column(JSONB)
    tiempo_ejecucion = Column(Float)
    fecha_ejecuta = Column(DateTime(timezone=True), server_default=func.now())

class LogErrorSistema(Base):
    __tablename__ = "logs_error_sistema"
    id_log_sis = Column(Integer, primary_key=True, index=True)
    mensaje_error = Column(String, nullable=False)
    fuente = Column(String, nullable=True)
    fecha_general_log = Column(DateTime(timezone=True), server_default=func.now())
    id_usuario = Column(Integer, ForeignKey("usuarios.id_usuario"), nullable=False)

class MetadatoAudio(Base):
    __tablename__ = "metadata_audio"
    id_audio = Column(Integer, primary_key=True, index=True)
    origen = Column(String, nullable=False)
    formato = Column(String, nullable=False)
    fecha_registro = Column(Date, server_default=func.now())
    hora_registro = Column(Time, server_default=func.current_time())
    localizacion = Column(String, nullable=True)
    longitud = Column(Float, nullable=True)
    latitud = Column(Float, nullable=True)
    id_usuario = Column(Integer, ForeignKey("usuarios.id_usuario"), nullable=False)
    id_inferencia = Column(Integer, ForeignKey("ejecuciones_inferencias.log_id"), nullable=True)