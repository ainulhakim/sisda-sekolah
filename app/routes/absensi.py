from app.timezone import now_wib
from datetime import date, datetime
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.routes import routes_bp
from app.models import Absensi, Siswa, Kelas, Badge, SiswaBadge, TahunAjaran
from app import db
from sqlalchemy import func

def check_badges(siswa_id):
    """Check and award badges for a siswa."""
    siswa = Siswa.query.get(siswa_id)
    if not siswa:
        return
    ta = TahunAjaran.query.filter_by(is_active=True).first()
    all_badges = Badge.query.filter_by(is_active=True).all()
    earned_ids = [sb.badge_id for sb in SiswaBadge.query.filter_by(siswa_id=siswa_id).all()]
    
    for badge in all_badges:
        if badge.id in earned_ids:
            continue
        earned = False
        if badge.syarat_tipe == 'streak_hadir':
            earned = siswa.streak_hadir >= badge.syarat_nilai
        elif badge.syarat_tipe == 'hadir_bulan_penuh':
            today = date.today()
            days_in_month = 30
            hadir_count = Absensi.query.filter_by(siswa_id=siswa_id, status='hadir').filter(
                func.strftime('%Y-%m', Absensi.tanggal) == today.strftime('%Y-%m')
            ).count()
            earned = hadir_count >= days_in_month
        elif badge.syarat_tipe == 'total_badge':
            earned = len(earned_ids) >= badge.syarat_nilai
        elif badge.syarat_tipe == 'mood_senang_streak':
            streak = 0
            for i in range(badge.syarat_nilai):
                check_date = date.today() - __import__('datetime').timedelta(days=i)
                a = Absensi.query.filter_by(siswa_id=siswa_id, tanggal=check_date, mood='senang').first()
                if a:
                    streak += 1
                else:
                    break
            earned = streak >= badge.syarat_nilai
        elif badge.syarat_tipe == 'checkin_pagi':
            early_count = Absensi.query.filter_by(siswa_id=siswa_id).filter(
                func.strftime('%H:%M', Absensi.check_in_time) < '07:00'
            ).count()
            earned = early_count >= badge.syarat_nilai
        elif badge.syarat_tipe == 'jumat_hadir':
            jumat_count = Absensi.query.filter_by(siswa_id=siswa_id, status='hadir').filter(
                func.strftime('%w', Absensi.tanggal) == '5'
            ).count()
            earned = jumat_count >= badge.syarat_nilai
        elif badge.syarat_tipe == 'kelas_penuh':
            if siswa.kelas_id:
                kelas = Kelas.query.get(siswa.kelas_id)
                if kelas:
                    total = kelas.jumlah_siswa
                    all_present = Absensi.query.filter_by(kelas_id=kelas.id, tanggal=date.today(), status='hadir').count()
                    earned = total > 0 and all_present >= total
        
        if earned:
            sb = SiswaBadge(siswa_id=siswa_id, badge_id=badge.id, tanggal_dapat=date.today(),
                           tahun_ajaran_id=ta.id if ta else None)
            db.session.add(sb)

@routes_bp.route('/absensi/checkin', methods=['GET', 'POST'])
@login_required
def absensi_checkin():
    if current_user.role not in ('admin', 'guru'):
        flash('Akses ditolak!', 'danger')
        return redirect(url_for('routes.dashboard'))
    
    if current_user.role == 'guru' and current_user.guru:
        kelas_list = Kelas.query.filter_by(wali_kelas_id=current_user.guru.id).all()
    else:
        kelas_list = Kelas.query.all()
    
    selected_kelas = request.args.get('kelas_id', type=int)
    siswa_list = []
    if selected_kelas:
        siswa_list = Siswa.query.filter_by(kelas_id=selected_kelas, status='aktif').all()
    
    today = date.today()
    checked = {}
    for s in siswa_list:
        a = Absensi.query.filter_by(siswa_id=s.id, tanggal=today).first()
        if a:
            checked[s.id] = a
    
    if request.method == 'POST':
        action = request.form.get('action')
        kelas_id = request.form.get('kelas_id', type=int)
        
        if action == 'single':
            siswa_id = request.form.get('siswa_id', type=int)
            status = request.form.get('status', 'hadir')
            mood = request.form.get('mood')
            existing = Absensi.query.filter_by(siswa_id=siswa_id, tanggal=today).first()
            if existing:
                existing.status = status
                existing.mood = mood
                existing.guru_id = current_user.guru_id if current_user.role == 'guru' else None
                existing.check_in_time = now_wib()
            else:
                siswa = Siswa.query.get(siswa_id)
                a = Absensi(
                    siswa_id=siswa_id, kelas_id=siswa.kelas_id, tanggal=today,
                    status=status, mood=mood, check_in_time=now_wib(),
                    check_in_method='manual',
                    guru_id=current_user.guru_id if current_user.role == 'guru' else None
                )
                db.session.add(a)
            db.session.commit()
            check_badges(siswa_id)
            db.session.commit()
        
        elif action == 'bulk':
            for s in Siswa.query.filter_by(kelas_id=kelas_id, status='aktif').all():
                existing = Absensi.query.filter_by(siswa_id=s.id, tanggal=today).first()
                if not existing:
                    a = Absensi(
                        siswa_id=s.id, kelas_id=kelas_id, tanggal=today,
                        status='hadir', mood='biasa', check_in_time=now_wib(),
                        check_in_method='manual',
                        guru_id=current_user.guru_id if current_user.role == 'guru' else None
                    )
                    db.session.add(a)
            db.session.commit()
        
        return redirect(url_for('routes.absensi_checkin', kelas_id=kelas_id))
    
    return render_template('absensi/checkin.html', kelas_list=kelas_list,
                          selected_kelas=selected_kelas, siswa_list=siswa_list, checked=checked, today=today)

@routes_bp.route('/absensi/rekap')
@login_required
def absensi_rekap():
    kelas_id = request.args.get('kelas_id', type=int)
    tanggal_mulai = request.args.get('tanggal_mulai')
    tanggal_akhir = request.args.get('tanggal_akhir')
    
    query = db.session.query(
        Siswa.id, Siswa.nama_lengkap, Kelas.nama_kelas,
        func.count(Absensi.id).filter(Absensi.status == 'hadir').label('hadir'),
        func.count(Absensi.id).filter(Absensi.status == 'izin').label('izin'),
        func.count(Absensi.id).filter(Absensi.status == 'sakit').label('sakit'),
        func.count(Absensi.id).filter(Absensi.status == 'alpa').label('alpa'),
        func.count(Absensi.id).filter(Absensi.status == 'telat').label('telat'),
        func.count(Absensi.id).label('total')
    ).join(Siswa, Siswa.id == Absensi.siswa_id).join(Kelas, Kelas.id == Absensi.kelas_id)
    
    if kelas_id:
        query = query.filter(Absensi.kelas_id == kelas_id)
    if tanggal_mulai:
        query = query.filter(Absensi.tanggal >= tanggal_mulai)
    if tanggal_akhir:
        query = query.filter(Absensi.tanggal <= tanggal_akhir)
    
    results = query.group_by(Siswa.id, Siswa.nama_lengkap, Kelas.nama_kelas).all()
    kelas_list = Kelas.query.all()
    
    return render_template('absensi/rekap.html', results=results, kelas_list=kelas_list,
                          kelas_id=kelas_id, tanggal_mulai=tanggal_mulai, tanggal_akhir=tanggal_akhir)

@routes_bp.route('/absensi/leaderboard')
@login_required
def absensi_leaderboard():
    kelas_id = request.args.get('kelas_id', type=int)
    ta = TahunAjaran.query.filter_by(is_active=True).first()
    
    query = db.session.query(
        Siswa.id, Siswa.nama_lengkap, Siswa.nama_panggilan, Kelas.nama_kelas,
        func.count(Absensi.id).filter(Absensi.status == 'hadir').label('total_hadir'),
        func.count(SiswaBadge.id).label('total_badge')
    ).outerjoin(Absensi, (Absensi.siswa_id == Siswa.id) & (Absensi.status == 'hadir')
    ).outerjoin(Kelas, Kelas.id == Siswa.kelas_id
    ).outerjoin(SiswaBadge, SiswaBadge.siswa_id == Siswa.id)
    
    if kelas_id:
        query = query.filter(Siswa.kelas_id == kelas_id)
    if ta:
        query = query.filter(Siswa.tahun_ajaran_id == ta.id)
    
    results = query.group_by(Siswa.id, Siswa.nama_lengkap, Siswa.nama_panggilan, Kelas.nama_kelas
    ).order_by(db.desc('total_hadir')).limit(10).all()
    
    kelas_list = Kelas.query.all()
    return render_template('absensi/leaderboard.html', results=results, kelas_list=kelas_list, kelas_id=kelas_id)

@routes_bp.route('/absensi/badges')
@login_required
def absensi_badges():
    all_badges = Badge.query.filter_by(is_active=True).all()
    if current_user.role == 'siswa' and current_user.siswa:
        siswa_badges = SiswaBadge.query.filter_by(siswa_id=current_user.siswa_id).all()
        earned_ids = [sb.badge_id for sb in siswa_badges]
        earned_map = {sb.badge_id: sb for sb in siswa_badges}
    else:
        earned_ids = []
        earned_map = {}

    return render_template('absensi/badges.html', all_badges=all_badges,
                          earned_ids=earned_ids, earned_map=earned_map)

@routes_bp.route('/absensi/scan')
@login_required
def absensi_scan():
    if current_user.role not in ('admin', 'guru'):
        flash('Akses ditolak!', 'danger')
        return redirect(url_for('routes.dashboard'))
    today_date = date.today()
    scan_count = Absensi.query.filter(
        Absensi.tanggal == today_date,
        Absensi.check_in_method.in_(['qr', 'qrcode'])
    ).count()
    return render_template('absensi/scan.html', today=today_date, scan_count=scan_count)


@routes_bp.route('/absensi/hari-ini')
@login_required
def absensi_hari_ini():
    """Today's attendance list with mood editing."""
    if current_user.role not in ('admin', 'guru'):
        flash('Akses ditolak!', 'danger')
        return redirect(url_for('routes.dashboard'))
    
    today_date = date.today()
    records = db.session.query(Absensi, Siswa).join(
        Siswa, Absensi.siswa_id == Siswa.id
    ).filter(
        Absensi.tanggal == today_date
    ).order_by(Absensi.check_in_time.asc()).all()
    
    # Flatten for template
    attendance_records = []
    for absen, siswa in records:
        absen.siswa = siswa
        absen.kelas = siswa.kelas if siswa.kelas_id else None
        attendance_records.append(absen)
    
    return render_template('absensi/hari_ini.html', records=attendance_records)
