from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from config import Config

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Silakan login terlebih dahulu.'

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    
    from app.routes import register_blueprints
    register_blueprints(app)
    
    @app.context_processor
    def inject_sekolah():
        try:
            from app.models import get_sekolah_config
            return dict(sekolah=get_sekolah_config())
        except Exception:
            return dict(sekolah=None)

    with app.app_context():
        from app import models
        db.create_all()

    return app
