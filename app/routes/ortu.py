from flask import Blueprint, render_template, redirect, url_for, request
from flask_login import login_required, current_user
from datetime import date, timedelta
from app.models import User, Siswa, BintangHarian, PrestasiLomba, SiswaBadge, Absensi, NilaiPelajaran, MataPelajaran

ortu_bp = Blueprint('ortu', __name__)

@ortu_bp.route('/ortu/dashboard')
@login_required
def dashboard():
    """Parent dashboard — view child's progress."""
    if current_user.role != 'ortu':
        return redirect(url_for('routes.dashboard'))

    siswa = current_user.siswa
    if not siswa:
        return render_template('ortu/no_child.html')

    # ── Bintang stats ──
    periode = request.args.get('periode', 'harian')
    today = date.today()

    bq = BintangHarian.query.filter_by(siswa_id=siswa.id)
    if periode == 'harian':
        bq = bq.filter(BintangHarian.tanggal == today)
    elif periode == 'pekanan':
        start = today - timedelta(days=today.weekday())
        bq = bq.filter(BintangHarian.tanggal >= start)
    elif periode == 'bulanan':
        start = today.replace(day=1)
        bq = bq.filter(BintangHarian.tanggal >= start)
    elif periode == 'semester':
        start = today.replace(month=1, day=1) if today.month <= 6 else today.replace(month=7, day=1)
        bq = bq.filter(BintangHarian.tanggal >= start)
    elif periode == 'tahunan':
        start = today.replace(month=1, day=1)
        bq = bq.filter(BintangHarian.tanggal >= start)

    bintang_count = bq.filter_by(jenis='bintang').count()
    jempol_count = bq.filter_by(jenis='jempol').count()
    net_bintang = bintang_count - jempol_count

    # Recent bintang
    bintang_recent = BintangHarian.query.filter_by(siswa_id=siswa.id).order_by(BintangHarian.tanggal.desc(), BintangHarian.id.desc()).limit(10).all()

    # ── Absensi summary ──
    absensi_30 = Absensi.query.filter_by(siswa_id=siswa.id).order_by(Absensi.tanggal.desc()).limit(30).all()
    hadir_count = sum(1 for a in absensi_30 if a.status == 'hadir')
    total_absen = len(absensi_30)

    # ── Prestasi ──
    prestasi = PrestasiLomba.query.filter_by(siswa_id=siswa.id).order_by(PrestasiLomba.tanggal_dapat.desc()).all()

    # ── Badges ──
    badges = SiswaBadge.query.filter_by(siswa_id=siswa.id).all()

    # ── Nilai ──
    nilai_list = siswa.nilai_pelajaran_list if hasattr(siswa, 'nilai_pelajaran_list') else []

    return render_template('ortu/dashboard.html',
                         siswa=siswa,
                         periode=periode,
                         bintang_count=bintang_count,
                         jempol_count=jempol_count,
                         net_bintang=net_bintang,
                         bintang_recent=bintang_recent,
                         absensi_30=absensi_30,
                         hadir_count=hadir_count,
                         total_absen=total_absen,
                         prestasi=prestasi,
                         badges=badges,
                         nilai_list=nilai_list)
