"""
QR Code Attendance endpoints for SiSD.
- GET  /api/qrcode/<siswa_id>/image  — generate QR code PNG
- POST /api/absen/qr                 — validate QR and record attendance
- GET  /siswa/<id>/kartu-qr           — PDF card with QR code
"""
import io
import json
import hashlib
import hmac
from datetime import date, datetime, timedelta, timezone

import qrcode
from flask import Blueprint, Response, request, jsonify, send_file
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

from app import db, csrf
from app.routes import routes_bp
from app.models import Siswa, Absensi, SekolahConfig, get_sekolah_config
from app.timezone import now_wib, WIB

QR_SECRET = b'sisd-qr-secret-2026'


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _sign(data_str: str) -> str:
    """Return HMAC-SHA256 hex digest of *data_str*."""
    return hmac.new(QR_SECRET, data_str.encode(), hashlib.sha256).hexdigest()


def _make_qr_payload(siswa_id: int) -> str:
    """Build a JSON payload with HMAC for a given student and today's date."""
    today_str = date.today().isoformat()
    message = f"{siswa_id}:{today_str}"
    sig = _sign(message)
    payload = {"sid": siswa_id, "date": today_str, "sig": sig}
    return json.dumps(payload, separators=(",", ":"))


def _verify_qr_payload(payload: dict) -> tuple:
    """
    Verify a QR JSON payload.
    Returns (ok: bool, error_message: str|None).
    """
    for key in ("sid", "date", "sig"):
        if key not in payload:
            return False, f"Field '{key}' missing from QR data"

    sid = payload["sid"]
    date_str = payload["date"]
    sig = payload["sig"]

    message = f"{sid}:{date_str}"
    expected_sig = _sign(message)
    if not hmac.compare_digest(sig, expected_sig):
        return False, "Invalid QR signature"

    # Date must be today
    try:
        qr_date = date.fromisoformat(date_str)
    except ValueError:
        return False, "Invalid date format in QR"

    today = date.today()
    # Allow today only (±1 day tolerance for timezone edge cases)
    if abs((qr_date - today).days) > 1:
        return False, "QR code is expired or not yet valid"

    return True, None


# ---------------------------------------------------------------------------
# Endpoint A: QR Code image
# ---------------------------------------------------------------------------

@routes_bp.route('/api/qrcode/<int:siswa_id>/image')
def qr_code_image(siswa_id: int):
    """Return a PNG QR code image for the given student (today's date)."""
    siswa = Siswa.query.get(siswa_id)
    if not siswa:
        return jsonify({"success": False, "message": "Siswa not found"}), 404

    payload_str = _make_qr_payload(siswa_id)

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(payload_str)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    return send_file(buf, mimetype="image/png",
                     download_name=f"qr_siswa_{siswa_id}.png")


# ---------------------------------------------------------------------------
# Endpoint B: QR check-in (POST)
# ---------------------------------------------------------------------------

@routes_bp.route('/api/absen/qr', methods=['POST'])
@csrf.exempt
def absen_qr():
    """
    Accept JSON {qr_data: "<JSON string>"}, validate, and record attendance.
    """
    body = request.get_json(silent=True)
    if not body or "qr_data" not in body:
        return jsonify({
            "success": False,
            "message": "Field 'qr_data' is required in request body",
        }), 400

    # Parse QR JSON
    raw = body["qr_data"]
    if isinstance(raw, str):
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return jsonify({"success": False, "message": "Invalid JSON in qr_data"}), 400
    elif isinstance(raw, dict):
        payload = raw
    else:
        return jsonify({"success": False, "message": "qr_data must be a JSON string or object"}), 400

    # Verify HMAC & date
    ok, err = _verify_qr_payload(payload)
    if not ok:
        return jsonify({"success": False, "message": err}), 400

    siswa_id = payload["sid"]

    siswa = Siswa.query.get(siswa_id)
    if not siswa:
        return jsonify({"success": False, "message": "Student not found"}), 404

    today = date.today()

    # Check duplicate
    existing = Absensi.query.filter_by(siswa_id=siswa_id, tanggal=today).first()
    if existing:
        return jsonify({
            "success": False,
            "message": f"Already checked in today ({existing.status})",
            "siswa_name": siswa.nama_panggilan or siswa.nama_lengkap,
            "status": existing.status,
        }), 200

    # Insert attendance record
    new_absen = Absensi(
        siswa_id=siswa_id,
        kelas_id=siswa.kelas_id,
        tanggal=today,
        status='hadir',
        check_in_time=now_wib(),
        check_in_method='qrcode',
        guru_id=None,
    )
    db.session.add(new_absen)
    db.session.commit()

    # Re-use badge check from existing absensi module
    try:
        from app.routes.absensi import check_badges
        check_badges(siswa_id)
        db.session.commit()
    except Exception:
        pass  # Non-critical; attendance already recorded

    return jsonify({
        "success": True,
        "message": "Absensi berhasil dicatat!",
        "siswa_name": siswa.nama_panggilan or siswa.nama_lengkap,
        "nama_lengkap": siswa.nama_lengkap,
        "check_in_time": new_absen.check_in_time.strftime('%H:%M:%S') if new_absen.check_in_time else '',
        "status": "hadir",
    }), 201


# ---------------------------------------------------------------------------
# Endpoint C: Student QR card PDF
# ---------------------------------------------------------------------------

@routes_bp.route('/siswa/<int:siswa_id>/kartu-qr')
def kartu_qr_pdf(siswa_id: int):
    """Generate a single-page A4 PDF with the student's QR code and info."""
    siswa = Siswa.query.get(siswa_id)
    if not siswa:
        return jsonify({"success": False, "message": "Siswa not found"}), 404

    config = get_sekolah_config()

    # Build QR image in-memory
    payload_str = _make_qr_payload(siswa_id)
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=2,
    )
    qr.add_data(payload_str)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    qr_buf = io.BytesIO()
    qr_img.save(qr_buf, format="PNG")
    qr_buf.seek(0)
    qr_reader = ImageReader(qr_buf)

    # Build PDF
    pdf_buf = io.BytesIO()
    c = canvas.Canvas(pdf_buf, pagesize=A4)
    width, height = A4  # ~595 x 842 points

    # --- School name ---
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(width / 2, height - 60, config.nama_sekolah or "SEKOLAH DASAR")

    # --- Title ---
    c.setFont("Helvetica", 11)
    c.drawCentredString(width / 2, height - 80, "Kartu QR Code Absensi")

    # --- QR code (200 x 200 points ≈ 70 mm) ---
    qr_size = 200
    qr_x = (width - qr_size) / 2
    qr_y = (height - qr_size) / 2 + 40
    c.drawImage(qr_reader, qr_x, qr_y, width=qr_size, height=qr_size)

    # --- Student info below QR ---
    info_y = qr_y - 20
    c.setFont("Helvetica-Bold", 13)
    display_name = siswa.nama_panggilan or siswa.nama_lengkap
    c.drawCentredString(width / 2, info_y, display_name)

    c.setFont("Helvetica", 11)
    info_y -= 18
    c.drawCentredString(width / 2, info_y, siswa.nama_lengkap)

    if siswa.nisn:
        info_y -= 16
        c.setFont("Helvetica", 9)
        c.drawCentredString(width / 2, info_y, f"NISN: {siswa.nisn}")

    # --- School footer ---
    c.setFont("Helvetica", 8)
    c.drawCentredString(width / 2, 40, config.nama_sekolah or "")
    if config.alamat:
        c.drawCentredString(width / 2, 28, config.alamat)

    c.save()
    pdf_buf.seek(0)

    return send_file(
        pdf_buf,
        mimetype="application/pdf",
        download_name=f"kartu_qr_{siswa_id}.pdf",
    )


# ---------------------------------------------------------------------------
# Endpoint D: Update mood for attendance record
# ---------------------------------------------------------------------------

@routes_bp.route('/api/absensi/<int:absensi_id>/mood', methods=['POST'])
@csrf.exempt
def update_mood(absensi_id: int):
    """Update mood for an attendance record. POST {mood: 'senang'|'sedih'|...}"""
    body = request.get_json(silent=True)
    if not body or 'mood' not in body:
        return jsonify({"success": False, "message": "Field 'mood' required"}), 400

    absensi = Absensi.query.get(absensi_id)
    if not absensi:
        return jsonify({"success": False, "message": "Record not found"}), 404

    valid_moods = ['senang', 'sedih', 'netral', 'mengantuk', 'sakit']
    mood = body['mood']
    if mood not in valid_moods:
        return jsonify({"success": False, "message": f"Mood harus salah satu: {', '.join(valid_moods)}"}), 400

    absensi.mood = mood
    db.session.commit()

    return jsonify({
        "success": True,
        "message": f"Mood diupdate ke {mood}",
        "mood": mood,
    }), 200


# ---------------------------------------------------------------------------
# Endpoint E: Get today's attendance list (for scanner page)
# ---------------------------------------------------------------------------

@routes_bp.route('/api/absensi/today')
def today_attendance():
    """Return today's attendance list with student details."""
    today = date.today()
    records = db.session.query(Absensi, Siswa).join(
        Siswa, Absensi.siswa_id == Siswa.id
    ).filter(
        Absensi.tanggal == today
    ).order_by(Absensi.check_in_time.desc()).all()

    result = []
    for absen, siswa in records:
        result.append({
            'id': absen.id,
            'siswa_id': siswa.id,
            'nama_lengkap': siswa.nama_lengkap,
            'nama_panggilan': siswa.nama_panggilan or '',
            'kelas_id': absen.kelas_id,
            'status': absen.status,
            'mood': absen.mood or '',
            'check_in_time': absen.check_in_time.strftime('%H:%M:%S') if absen.check_in_time else '',
            'check_in_method': absen.check_in_method or 'manual',
        })

    return jsonify(result), 200
