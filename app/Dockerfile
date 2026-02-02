# 1. Usamos una imagen base de Python ligera (Linux)
FROM python:3.10-slim

# 2. ESTO ES VITAL PARA TU APP DE AUDIO:
# Instalamos ffmpeg y dependencias del sistema necesarias para procesar audio
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsm6 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

# 3. Establecemos el directorio de trabajo dentro del contenedor
WORKDIR /app

# 4. Copiamos el archivo de requerimientos primero (para aprovechar la caché de Docker)
COPY requirements.txt .

# 5. Instalamos las librerías de Python
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 6. Copiamos el resto de tu código al contenedor
COPY . .

# 7. Exponemos el puerto 8000 (El estándar de FastAPI)
EXPOSE 8000

# 8. Comando para iniciar la app cuando arranque el servidor
# Ajusta "main:app" si tu archivo no se llama main.py
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]