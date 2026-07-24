from flask import Blueprint
from app.auth import auth_bp

routes_bp = Blueprint('routes', __name__)

# Import all route modules BEFORE registering
from app.routes import dashboard, siswa, absensi, admin, assessment, assessment_ortu, pelajaran, kemampuan_dasar, rapor
from app.routes import gap_analysis, lomba, qrcode_attendance, bintang

def register_blueprints(app):
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(routes_bp)
