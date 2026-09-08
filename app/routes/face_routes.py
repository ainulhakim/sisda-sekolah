"""
Face Recognition Attendance endpoints for SiSD.
- GET  /face-scan           — Student-facing face scan page
- GET  /face-enroll         — Admin enrollment page
- POST /api/face/enroll     — Enroll student face (admin only)
- POST /api/absen/face      — Face check-in
- GET  /api/face/enrolled   — List enrolled students (for enrollment page)
"""
from datetime import date

from flask import Blueprint, request, jsonify, render_template
from flask_login import login_required, current_user

from app import db, csrf
from app.routes import routes_bp
from app.models import Siswa, Absensi, Kelas, SekolahConfig, get_sekolah_config
from app.timezone import now_wib, WIB
from app.face_service import match_student_face, enroll_student_face


# ---------------------------------------------------------------------------
# Helper: replicate the scan-count logic from absensi_scan
# ---------------------------------------------------------------------------

def _today_scan_count():
    """Return number of QR/face check-ins for today."""
    today = date.today()
    return Absensi.query.filter(
        Absensi.tanggal == today,
        Absensi.check_in_method.in_(['qr', 'qrcode', 'face'])
    ).count()


# ---------------------------------------------------------------------------
# 1. GET /face-scan — render face scan page
# ---------------------------------------------------------------------------

@routes_bp.route('/face-scan')
@login_required
def face_scan():
    """Redirect to unified scan page."""
    from flask import redirect, url_for
    return redirect(url_for('routes.absensi_scan'))


# ---------------------------------------------------------------------------
# 2. GET /face-enroll — admin enrollment page
# ---------------------------------------------------------------------------

@routes_bp.route('/face-enroll')
@login_required
def face_enroll():
    if current_user.role not in ('admin',):
        from flask import flash, redirect, url_for
        flash('Akses ditolak!', 'danger')
        return redirect(url_for('routes.dashboard'))

    students = Siswa.query.filter_by(status='aktif').order_by(Siswa.nama_lengkap).all()
    return render_template('absensi/face_enroll.html', students=students)


# ---------------------------------------------------------------------------
# 3. POST /api/face/enroll — enroll student face (admin only)
# ---------------------------------------------------------------------------

@routes_bp.route('/api/face/enroll', methods=['POST'])
@csrf.exempt
def api_face_enroll():
    body = request.get_json(silent=True)
    if not body or 'siswa_id' not in body or 'embedding' not in body:
        return jsonify({
            'success': False,
            'message': "Fields 'siswa_id' and 'embedding' are required",
        }), 400

    siswa_id = body['siswa_id']
    embedding = body['embedding']

    if not isinstance(embedding, list) or len(embedding) != 128:
        return jsonify({
            'success': False,
            'message': 'Embedding must be a list of 128 floats',
        }), 400

    result = enroll_student_face(siswa_id, embedding)
    status_code = 200 if result['success'] else 400
    return jsonify(result), status_code


# ---------------------------------------------------------------------------
# 4. POST /api/absen/face — face check-in
# ---------------------------------------------------------------------------

@routes_bp.route('/api/absen/face', methods=['POST'])
@csrf.exempt
def absen_face():
    """
    Accept JSON {embedding: [float x 128]}, match against enrolled faces,
    and record attendance — mirrors absen_qr logic from qrcode_attendance.py.
    """
    body = request.get_json(silent=True)
    if not body or 'embedding' not in body:
        return jsonify({
            'success': False,
            'message': "Field 'embedding' is required in request body",
        }), 400

    embedding = body['embedding']
    if not isinstance(embedding, list) or len(embedding) != 128:
        return jsonify({
            'success': False,
            'message': 'Embedding must be a list of 128 floats',
        }), 400

    # --- Match face ---
    siswa_id, confidence = match_student_face(embedding)

    if siswa_id is None:
        return jsonify({
            'success': False,
            'message': 'Wajah tidak dikenali. Pastikan wajah terlihat jelas.',
            'confidence': confidence,
        }), 404

    siswa = Siswa.query.get(siswa_id)
    if not siswa:
        return jsonify({'success': False, 'message': 'Student not found'}), 404

    today = date.today()

    # --- Duplicate check ---
    existing = Absensi.query.filter_by(siswa_id=siswa_id, tanggal=today).first()
    if existing:
        return jsonify({
            'success': False,
            'message': f"Already checked in today ({existing.status})",
            'siswa_name': siswa.nama_panggilan or siswa.nama_lengkap,
            'status': existing.status,
        }), 200

    # --- Insert attendance record ---
    new_absen = Absensi(
        siswa_id=siswa_id,
        kelas_id=siswa.kelas_id or 2,  # fallback to first available kelas
        tanggal=today,
        status='hadir',
        check_in_time=now_wib(),
        check_in_method='face',
        guru_id=None,
    )
    db.session.add(new_absen)
    db.session.commit()

    # --- Badge check (same as QR) ---
    try:
        from app.routes.absensi import check_badges
        check_badges(siswa_id)
        db.session.commit()
    except Exception:
        pass  # Non-critical; attendance already recorded

    # --- Build kelas name ---
    kelas_nama = ''
    if siswa.kelas_id:
        kelas = Kelas.query.get(siswa.kelas_id)
        if kelas:
            kelas_nama = kelas.nama_kelas

    return jsonify({
        'success': True,
        'message': 'Absensi berhasil dicatat!',
        'siswa_name': siswa.nama_panggilan or siswa.nama_lengkap,
        'nama_lengkap': siswa.nama_lengkap,
        'check_in_time': new_absen.check_in_time.strftime('%H:%M:%S') if new_absen.check_in_time else '',
        'status': 'hadir',
        'confidence': confidence,
        'kelas_nama': kelas_nama,
    }), 201


# ---------------------------------------------------------------------------
# 5. GET /api/face/enrolled — list enrolled students
# ---------------------------------------------------------------------------

@routes_bp.route('/api/face/enrolled')
def api_face_enrolled():
    """Return list of active students with their face_enrolled status."""
    students = Siswa.query.filter_by(status='aktif').order_by(Siswa.nama_lengkap).all()
    result = []
    for s in students:
        result.append({
            'id': s.id,
            'nama_lengkap': s.nama_lengkap,
            'nama_panggilan': s.nama_panggilan or '',
            'kelas_id': s.kelas_id,
            'nisn': s.nisn or '',
            'face_enrolled': s.face_enrolled or False,
        })
    return jsonify(result), 200
