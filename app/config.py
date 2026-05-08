import os
from datetime import timedelta
from pathlib import Path
from dotenv import load_dotenv

# Ruta base del proyecto (funciona en local y en PythonAnywhere)
BASE_DIR = Path(__file__).resolve().parent.parent

# Carga .env desde la raíz del proyecto
load_dotenv(BASE_DIR / '.env')


class Config:
    # ── Seguridad ────────────────────────────────────────────────────────────
    SECRET_KEY     = os.getenv('SECRET_KEY',     'dev-secret-CAMBIA-EN-PRODUCCION')
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'dev-jwt-CAMBIA-EN-PRODUCCION')

    # ── Base de datos ─────────────────────────────────────────────────────────
    # En local usa SQLite relativo al proyecto.
    # En PythonAnywhere también usa SQLite (funciona perfecto).
    _db_default = f"sqlite:///{(BASE_DIR / 'instance' / 'hidrogestion.sqlite').as_posix()}"
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', _db_default)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,   # Detecta conexiones caídas
        'pool_recycle':  280,    # Evita errores por timeout del servidor
    }

    # ── JWT ───────────────────────────────────────────────────────────────────
    JWT_ACCESS_TOKEN_EXPIRES  = timedelta(hours=8)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    JWT_ERROR_MESSAGE_KEY     = 'mensaje'

    # ── Uploads ───────────────────────────────────────────────────────────────
    # En PythonAnywhere puedes definir UPLOAD_FOLDER=/home/usuario/hidrogestion/uploads
    # Si no se define, usa la carpeta uploads/ dentro del proyecto (funciona en ambos)
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', str(BASE_DIR / 'uploads'))
    # Garantiza que sea ruta absoluta
    if not Path(UPLOAD_FOLDER).is_absolute():
        UPLOAD_FOLDER = str((BASE_DIR / UPLOAD_FOLDER).resolve())
    MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', str(16 * 1024 * 1024)))  # 16 MB

    # ── CORS ──────────────────────────────────────────────────────────────────
    # '*' permite todos los orígenes — necesario para app móvil React Native
    # En local puedes poner: http://localhost:3000,http://localhost:5000
    _cors_raw = os.getenv('CORS_ORIGINS', '*')
    CORS_ORIGINS = '*' if _cors_raw.strip() == '*' else [
        o.strip() for o in _cors_raw.split(',') if o.strip()
    ]
