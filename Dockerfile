# Usamos una imagen ligera de Python
FROM python:3.10-slim

# Directorio de trabajo dentro del contenedor
WORKDIR /app

# Copiamos primero los requerimientos para aprovechar la caché de Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiamos el resto del código
COPY . .

# Comando para ejecutar FastAPI
# IMPORTANTE: Según tu estructura, el objeto 'app' está en 'app/main.py'
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}