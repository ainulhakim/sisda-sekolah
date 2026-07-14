from flask import render_template, redirect, url_for
from flask_login import login_required, current_user
from app.routes import routes_bp
from app.models import Siswa, Guru, Kelas, Absensi, Badge, SiswaBadge, TahunAjaran
from datetime import date, timedelta
from sqlalchemy import func

@routes_bp.route('/')
@login_required
def index():
    return redirect(url_for('routes.dashboard'))

@routes_bp.route('/admin/dashboard')
@routes_bp.route('/guru/dashboard')
@routes_bp.route('/siswa/dashboard')
@routes_bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'admin':
        return admin_dashboard()
    elif current_user.role == 'guru':
        return guru_dashboard()
    else:
        return siswa_dashboard()

def admin_dashboard():
    total_siswa = Siswa.query.filter_by(status='aktif').count()
    total_guru = Guru.query.filter_by(is_active=True).count()
    total_kelas = Kelas.query.count()
    today = date.today()
    week_ago = today - timedelta(days=7)
    
    absensi_mingguan = db.session.query(
        Absensi.tanggal, Absensi.status, func.count(Absensi.id)
    ).filter(Absensi.tanggal >= week_ago).group_by(Absensi.tanggal, Absensi.status).all()
    
    chart_data = {}
    for t, s, c in absensi_mingguan:
        d = t.isoformat()
        if d not in chart_data:
            chart_data[d] = {'hadir': 0, 'izin': 0, 'sakit': 0, 'alpa': 0, 'telat': 0}
        chart_data[d][s] = c

    # Prestasi summary
    from app.models import PrestasiLomba
    ta = TahunAjaran.query.filter_by(is_active=True).first()
    total_prestasi = PrestasiLomba.query.count()
    prestasi_tahun = 0
    top_performers = []
    if ta:
        prestasi_tahun = db.session.query(PrestasiLomba).join(Lomba)\
            .filter(Lomba.tahun_ajaran_id == ta.id).count()
        # Top performers: students with most Juara 1/2/3
        from sqlalchemy import func as sqlfunc
        top_performers = db.session.query(
            Siswa.nama_lengkap,
            sqlfunc.count(PrestasiLomba.id).label('total')
        ).join(PrestasiLomba, Siswa.id == PrestasiLomba.siswa_id)\
        .filter(PrestasiLomba.juara.in_(['Juara 1', 'Juara 2', 'Juara 3']))\
        .group_by(Siswa.nama_lengkap)\
        .order_by(sqlfunc.count(PrestasiLomba.id).desc())\
        .limit(5).all()
    
    return render_template('dashboard/admin.html',
        total_siswa=total_siswa, total_guru=total_guru, total_kelas=total_kelas,
        chart_data=chart_data, today=today,
        total_prestasi=total_prestasi, prestasi_tahun=prestasi_tahun,
        top_performers=top_performers)

def guru_dashboard():
    guru = current_user.guru
    kelas_list = Kelas.query.filter_by(wali_kelas_id=guru.id).all() if guru else []
    today = date.today()
    absensi_hari_ini = []
    for k in kelas_list:
        a = Absensi.query.filter_by(kelas_id=k.id, tanggal=today).count()
        absensi_hari_ini.append({'kelas': k, 'count': a, 'total': k.jumlah_siswa})
    
    sad_students = []
    for k in kelas_list:
        sad = db.session.query(Siswa).join(Absensi).filter(
            Absensi.kelas_id == k.id, Absensi.tanggal == today,
            Absensi.mood == 'sedih'
        ).all()
        sad_students.extend(sad)
    
    return render_template('dashboard/guru.html',
        kelas_list=kelas_list, absensi_hari_ini=absensi_hari_ini,
        sad_students=sad_students, today=today)

def siswa_dashboard():
    from app.models import NilaiPelajaran, MataPelajaran, PrestasiLomba
    siswa = current_user.siswa
    badges = SiswaBadge.query.filter_by(siswa_id=siswa.id).all() if siswa else []
    streak = siswa.streak_hadir if siswa else 0
    recent_absensi = Absensi.query.filter_by(siswa_id=siswa.id).order_by(Absensi.tanggal.desc()).limit(7).all() if siswa else []
    mood_data = {}
    for a in recent_absensi:
        mood_data[a.tanggal.isoformat()] = a.mood

    # Nilai pelajaran utama
    ta = TahunAjaran.query.filter_by(is_active=True).first()
    nilai_list = []
    if siswa and ta:
        nilai_list = NilaiPelajaran.query.filter_by(
            siswa_id=siswa.id, tahun_ajaran_id=ta.id
        ).all()

    # Prestasi lomba
    prestasi_list = []
    if siswa:
        prestasi_list = PrestasiLomba.query.filter_by(siswa_id=siswa.id)\
            .order_by(PrestasiLomba.tanggal_dapat.desc().nullslast()).all()

    return render_template('dashboard/siswa.html',
        siswa=siswa, badges=badges, streak=streak,
        recent_absensi=recent_absensi, mood_data=mood_data,
        nilai_list=nilai_list, prestasi_list=prestasi_list)

# Need db import for admin_dashboard
from app.models import *
from app import db
