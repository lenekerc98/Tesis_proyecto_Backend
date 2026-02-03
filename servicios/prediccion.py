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
    top_n: int = 5
):

    # 1. Limpieza
    y = limpiar_audio(y)

    # 2. Log-mel
    S = audio_a_logmel(y, sr)

    # 3. Tensor (1, 128, 216, 1)
    X = S[np.newaxis, ..., np.newaxis]

    # 4. Inferencia
    probs = model.predict(X)[0]

    # 5 . Top-N
    top_indices = np.argsort(probs)[::-1][:top_n]

    resultados = []

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
            "probabilidad": float(probs[idx])
        })

    return resultados
#-----------------------------------------------------------
