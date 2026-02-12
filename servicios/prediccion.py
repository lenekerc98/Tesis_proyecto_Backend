# app/servicios/prediccion.py
import os
import numpy as np
import librosa
import tensorflow as tf

from sqlalchemy.orm import Session
from db.modelos import Ave

# ---------------- CONFIGURACIÓN ----------------
MODEL_PATH = "modelo_cnn/best_model.keras"

TARGET_SR = 44100
N_MELS = 128
TARGET_FRAMES = 216
FMIN = 500
FMAX = 11025

# Cargar modelo UNA sola vez
model = tf.keras.models.load_model(MODEL_PATH)

#Limpieza de audio.

def limpiar_audio(y):
    if y.ndim > 1:
        y = librosa.to_mono(y)

    y = y / (np.max(np.abs(y)) + 1e-9)
    y = librosa.effects.preemphasis(y, coef=0.97)

    return y

# Generar espectrograma log-mel 128 x 216
def audio_a_logmel(y, sr):
    S = librosa.feature.melspectrogram(
        y=y,
        sr=sr,
        n_mels=N_MELS,
        fmin=FMIN,
        fmax=FMAX
    )

    S_db = librosa.power_to_db(S, ref=np.max)
    S_norm = (S_db - S_db.min()) / (S_db.max() - S_db.min() + 1e-9)

    frames = S_norm.shape[1]

    if frames < TARGET_FRAMES:
        S_norm = np.pad(
            S_norm,
            ((0, 0), (0, TARGET_FRAMES - frames)),
            mode="constant"
        )
    elif frames > TARGET_FRAMES:
        start = (frames - TARGET_FRAMES) // 2
        S_norm = S_norm[:, start:start + TARGET_FRAMES]

    return S_norm

# Obtener URL de imagen de ave por nombre científico.

def obtener_imagen_ave(db: Session, nombre_cientifico: str):
    ave = (
        db.query(Ave)
        .filter(Ave.nombre_cientifico == nombre_cientifico)
        .first()
    )

    return ave.url_imagen if ave else None

# Predicción de especie desde archivo de audio

def predecir_audio(
    y: np.ndarray,
    sr: int,
    db: Session,
    top_n: int = 5,
    threshold: float = 0.60  # Nuevo umbral de confianza
):
    # 1. Limpieza inicial
    y = limpiar_audio(y)

    # 2. Configuración de Ventana Deslizante (Sliding Window)
    # 216 frames * 512 hop_length / 44100 sr ~= 2.5 segundos
    # Usaremos ventanas de ~2.5s con 50% de superposición (overlap)
    samples_per_window = int(2.5 * sr)
    step = int(samples_per_window * 0.5)  # 50% overlap

    # Si el audio es muy corto, lo tratamos como una sola ventana
    if len(y) <= samples_per_window:
        windows = [y]
    else:
        # Generar ventanas
        windows = []
        for start in range(0, len(y) - samples_per_window + 1, step):
            end = start + samples_per_window
            windows.append(y[start:end])
        
        # Asegurar que el último fragmento se procese si es significativo
        if len(y) > samples_per_window and (len(y) - step) % samples_per_window != 0:
            windows.append(y[-samples_per_window:])

    # 3. Predicción por lotes (Batch Prediction)
    batch_X = []
    for window in windows:
        S = audio_a_logmel(window, sr)
        # Añadir eje de canal: (128, 216) -> (128, 216, 1)
        X = S[..., np.newaxis]
        batch_X.append(X)

    batch_X = np.array(batch_X) # Shape: (N_ventanas, 128, 216, 1)

    # Ejecutar inferencia en todo el lote
    # probs_batch shape: (N_ventanas, N_clases)
    probs_batch = model.predict(batch_X)

    # 4. Agregación de resultados (MAX pooling)
    # Tomamos la probabilidad máxima observada para cada especie a través de todas las ventanas.
    # Esto ayuda a detectar el ave incluso si solo canta en un pequeño fragmento.
    max_probs = np.max(probs_batch, axis=0)

    # 5. Top-N y Umbral de Confianza
    top_indices = np.argsort(max_probs)[::-1][:top_n]
    
    # Verificación del mejor resultado contra el umbral
    best_idx = top_indices[0]
    best_prob = float(max_probs[best_idx])

    resultados = []

    if best_prob < threshold:
        # Si no supera el umbral, devolvemos un resultado "vacío" o de "ruido"
        resultados.append({
            "id_ave": 0, # ID reservado o ficticio
            "nombre_cientifico": "Desconocido",
            "nombre": "No se detectó ave (Baja confianza)",
            "probabilidad": best_prob
        })
        # Rellenamos el resto con los que haya, aunque sean bajos, o simplemente cortamos aquí
        # Para mantener el formato top-5, podemos agregar los siguientes marcados como baja confianza
    else:
        # Procesamiento normal de los Top-N
        for idx in top_indices:
            ave = (
                db.query(Ave)
                .filter(Ave.id_ave == int(idx))
                .first()
            )

            resultados.append({
                "id_ave": int(idx),
                "nombre_cientifico": ave.nombre_cientifico if ave else "desconocido",
                "nombre": ave.nombre if ave else "desconocido",
                "probabilidad": float(max_probs[idx])
            })

    return resultados
#-----------------------------------------------------------


