"""
QR Code Attendance endpoints for SiSD.
- GET  /api/qrcode/<siswa_id>/image  — generate QR code PNG
- POST /api/absen/qr                 — validate QR and record attendance
- GET  /siswa/<id>/kartu-qr           — CR80 card PDF with school logo + QR
"""
import io
import os
import json
import hashlib
import hmac
from datetime import date, datetime, timedelta, timezone

import qrcode
from flask import Blueprint, Response, request, jsonify, send_file, current_app
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, black, white
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
        kelas_id=siswa.kelas_id or 2,  # fallback to first available kelas
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
# Endpoint C: Student QR card PDF  (CR80 — 85.6mm × 53.98mm)
# ---------------------------------------------------------------------------

@routes_bp.route('/siswa/<int:siswa_id>/kartu-qr')
def kartu_qr_pdf(siswa_id: int):
    """
    Generate a CR80-sized ID card PDF (85.6mm × 53.98mm, same as credit card)
    with school logo, student info, and scannable QR code.

    Layout (landscape):
    ┌────────────────────────────────────────────────────┐
    │ [LOGO]  SD BILINGUAL SANTREN KODING               │
    │         "Global Sejak Dini"                       │
    │────────────────────────────────────────────────────│
    │  ╔══════════╗                                     │
    │   ║ QR CODE ║  Ahmad Fauzi                       │
    │   ║  22mm   ║  Nama: Ahmad Fauzi                 │
    │   ╚══════════╝  NISN: 008xxxxxxx                 │
    │                                                    │
    └────────────────────────────────────────────────────┘
    """
    siswa = Siswa.query.get(siswa_id)
    if not siswa:
        return jsonify({"success": False, "message": "Siswa not found"}), 404

    config = get_sekolah_config()

    # --- Build QR image in-memory ---
    payload_str = _make_qr_payload(siswa_id)
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,  # High EC for small print
        box_size=8,
        border=1,
    )
    qr.add_data(payload_str)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    qr_buf = io.BytesIO()
    qr_img.save(qr_buf, format="PNG")
    qr_buf.seek(0)
    qr_reader = ImageReader(qr_buf)

    # --- CR80 card dimensions ---
    card_w = 85.6 * mm    # 242.65 pts
    card_h = 53.98 * mm   # 153.01 pts

    pdf_buf = io.BytesIO()
    c = canvas.Canvas(pdf_buf, pagesize=(card_w, card_h))

    # ── Background: white with thin border ──
    c.setFillColor(white)
    c.rect(0, 0, card_w, card_h, fill=1, stroke=0)
    c.setStrokeColor(HexColor('#cccccc'))
    c.setLineWidth(0.5)
    c.rect(1.5, 1.5, card_w - 3, card_h - 3, fill=0, stroke=1)

    # ── Top section: Logo + School Name ──
    logo_path = None
    if config.logo_path:
        logo_path = os.path.join(
            current_app.static_folder, 'uploads', config.logo_path
        )
        if not os.path.exists(logo_path):
            logo_path = None

    top_section_h = 14 * mm
    top_y = card_h - 3 * mm

    if logo_path:
        # Logo: 11mm × 11mm, left-aligned
        logo_size = 11 * mm
        logo_x = 4 * mm
        logo_y = top_y - logo_size - 1 * mm
        c.drawImage(
            logo_path, logo_x, logo_y,
            width=logo_size, height=logo_size,
            preserveAspectRatio=True, mask='auto',
        )
        # School name: right of logo
        text_x = logo_x + logo_size + 2.5 * mm
        text_top = top_y - 3.5 * mm

        c.setFillColor(black)
        c.setFont("Helvetica-Bold", 7)
        c.drawString(text_x, text_top, config.nama_sekolah or "SEKOLAH")

        # Tagline
        if config.visi:
            c.setFont("Helvetica-Oblique", 5)
            c.setFillColor(HexColor('#555555'))
            c.drawString(text_x, text_top - 4 * mm, f'"{config.visi}"')
    else:
        # No logo — centered
        c.setFont("Helvetica-Bold", 8)
        c.drawCentredString(card_w / 2, top_y - 5 * mm, config.nama_sekolah or "SEKOLAH")
        if config.visi:
            c.setFont("Helvetica-Oblique", 5)
            c.setFillColor(HexColor('#555555'))
            c.drawCentredString(card_w / 2, top_y - 9 * mm, f'"{config.visi}"')

    # ── Divider line ──
    divider_y = card_h - top_section_h - 2 * mm
    c.setStrokeColor(HexColor('#dddddd'))
    c.setLineWidth(0.4)
    c.line(4 * mm, divider_y, card_w - 4 * mm, divider_y)

    # ── Bottom section: QR code (left) + Student info (right) ──
    qr_size = 22 * mm
    qr_x = 5 * mm
    qr_y = 5 * mm
    c.drawImage(qr_reader, qr_x, qr_y, width=qr_size, height=qr_size)

    # Student info — to the right of QR
    info_x = qr_x + qr_size + 4 * mm
    info_top_y = qr_y + qr_size - 2 * mm

    # Student name (bold)
    display_name = siswa.nama_panggilan or siswa.nama_lengkap
    c.setFillColor(black)
    c.setFont("Helvetica-Bold", 7.5)
    c.drawString(info_x, info_top_y, display_name)

    # Full name (if different from panggilan)
    if siswa.nama_panggilan and siswa.nama_lengkap != siswa.nama_panggilan:
        c.setFont("Helvetica", 5.5)
        c.setFillColor(HexColor('#444444'))
        c.drawString(info_x, info_top_y - 5 * mm, siswa.nama_lengkap)

    # NISN
    nisn_y = info_top_y - (10 * mm if siswa.nama_panggilan and siswa.nama_lengkap != siswa.nama_panggilan else 5 * mm)
    if siswa.nisn:
        c.setFont("Helvetica", 5)
        c.setFillColor(HexColor('#666666'))
        c.drawString(info_x, nisn_y, f"NISN: {siswa.nisn}")

    # School name footer (very small)
    c.setFont("Helvetica", 3.5)
    c.setFillColor(HexColor('#aaaaaa'))
    c.drawCentredString(card_w / 2, 2 * mm, config.nama_sekolah or "")

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
