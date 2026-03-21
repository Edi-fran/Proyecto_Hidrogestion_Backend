import os
from datetime import timedelta
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')


def _sqlite_default_uri() -> str:
    db_path = BASE_DIR / 'instance' / 'hidrogestion.sqlite'
    return f"sqlite:///{db_path.as_posix()}"


class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'dev-jwt-secret-key')
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', _sqlite_default_uri())
    if SQLALCHEMY_DATABASE_URI.startswith('sqlite:///instance/'):
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{(BASE_DIR / SQLALCHEMY_DATABASE_URI.replace('sqlite:///', '')).as_posix()}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=8)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    JWT_ERROR_MESSAGE_KEY = 'mensaje'
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', str(BASE_DIR / 'uploads'))
    if not Path(UPLOAD_FOLDER).is_absolute():
        UPLOAD_FOLDER = str((BASE_DIR / UPLOAD_FOLDER).resolve())
    MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))
    CORS_ORIGINS = [origin.strip() for origin in os.getenv('CORS_ORIGINS', '*').split(',') if origin.strip()]
