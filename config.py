import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'sisda-sekolah-secret-key-2026')
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(BASE_DIR, 'sisda.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
