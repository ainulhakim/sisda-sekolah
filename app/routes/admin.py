from app.timezone import utcnow_wib
from flask import render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from app.routes import routes_bp
from app.models import Guru, Kelas, TahunAjaran, Kurikulum, User, SekolahConfig, get_sekolah_config
from app import db
import os
import secrets
from werkzeug.utils import secure_filename
from datetime import datetime

@routes_bp.route('/admin/guru')
@login_required
def guru_list():
    if current_user.role != 'admin':
        flash('Akses ditolak!', 'danger')
        return redirect(url_for('routes.dashboard'))
    guru = Guru.query.filter_by(is_active=True).all()
    return render_template('admin/guru.html', guru_list=guru)

@routes_bp.route('/admin/guru/tambah', methods=['GET', 'POST'])
@login_required
def guru_tambah():
    if current_user.role != 'admin':
        flash('Akses ditolak!', 'danger')
        return redirect(url_for('routes.dashboard'))
    if request.method == 'POST':
        g = Guru(
            nip=request.form.get('nip'),
            nama_lengkap=request.form.get('nama_lengkap'),
            email=request.form.get('email'),
            no_hp=request.form.get('no_hp')
        )
        db.session.add(g)
        db.session.commit()
        flash(f'Guru {g.nama_lengkap} berhasil ditambahkan!', 'success')
        return redirect(url_for('routes.guru_list'))
    return render_template('admin/guru.html', guru_list=Guru.query.all(), adding=True)

@routes_bp.route('/admin/guru/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def guru_edit(id):
    if current_user.role != 'admin':
        flash('Akses ditolak!', 'danger')
        return redirect(url_for('routes.dashboard'))
    g = Guru.query.get_or_404(id)
    if request.method == 'POST':
        g.nip = request.form.get('nip')
        g.nama_lengkap = request.form.get('nama_lengkap')
        g.email = request.form.get('email')
        g.no_hp = request.form.get('no_hp')
        db.session.commit()
        flash(f'Guru {g.nama_lengkap} berhasil diupdate!', 'success')
        return redirect(url_for('routes.guru_list'))
    return render_template('admin/guru.html', guru_list=Guru.query.all(), editing=g)

@routes_bp.route('/admin/guru/<int:id>/hapus', methods=['POST'])
@login_required
def guru_hapus(id):
    if current_user.role != 'admin':
        flash('Akses ditolak!', 'danger')
        return redirect(url_for('routes.dashboard'))
    g = Guru.query.get_or_404(id)
    # Delete associated user account if exists
    if g.user:
        db.session.delete(g.user)
    g.is_active = False
    db.session.commit()
    flash(f'Guru {g.nama_lengkap} telah dihapus.', 'info')
    return redirect(url_for('routes.guru_list'))

@routes_bp.route('/admin/guru/<int:id>/akun', methods=['POST'])
@login_required
def guru_akun(id):
    if current_user.role != 'admin':
        flash('Akses ditolak!', 'danger')
        return redirect(url_for('routes.dashboard'))
    g = Guru.query.get_or_404(id)
    if g.user:
        flash(f'Guru {g.nama_lengkap} sudah memiliki akun login.', 'warning')
        return redirect(url_for('routes.guru_list'))
    username = g.nip or g.email or g.nama_lengkap.lower().replace(' ', '.')
    password = secrets.token_urlsafe(8)
    user = User(username=username, role='guru', guru_id=g.id)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    flash(f'Akun dibuat! Username: {username}, Password: {password}', 'success')
    return redirect(url_for('routes.guru_list'))

@routes_bp.route('/admin/guru/<int:id>/reset-password', methods=['POST'])
@login_required
def guru_reset_password(id):
    if current_user.role != 'admin':
        flash('Akses ditolak!', 'danger')
        return redirect(url_for('routes.dashboard'))
    g = Guru.query.get_or_404(id)
    # g.user is a list (backref from User), get the first one
    user = g.user[0] if g.user else None
    if not user:
        flash(f'Guru {g.nama_lengkap} belum memiliki akun login.', 'warning')
        return redirect(url_for('routes.guru_list'))
    new_password = secrets.token_urlsafe(8)
    user.set_password(new_password)
    db.session.commit()
    flash(f'Password {g.nama_lengkap} direset! Username: {user.username}, Password Baru: {new_password}', 'success')
    return redirect(url_for('routes.guru_list'))

@routes_bp.route('/admin/kelas')
@login_required
def kelas_list():
    if current_user.role != 'admin':
        flash('Akses ditolak!', 'danger')
        return redirect(url_for('routes.dashboard'))
    kelas = Kelas.query.all()
    guru_list = Guru.query.filter_by(is_active=True).all()
    ta_list = TahunAjaran.query.all()
    return render_template('admin/kelas.html', kelas_list=kelas, guru_list=guru_list, ta_list=ta_list)

@routes_bp.route('/admin/kelas/tambah', methods=['POST'])
@login_required
def kelas_tambah():
    if current_user.role != 'admin':
        flash('Akses ditolak!', 'danger')
        return redirect(url_for('routes.dashboard'))
    k = Kelas(
        nama_kelas=request.form.get('nama_kelas'),
        tingkat=request.form.get('tingkat', type=int),
        tahun_ajaran_id=request.form.get('tahun_ajaran_id', type=int),
        wali_kelas_id=request.form.get('wali_kelas_id', type=int),
        kuota=request.form.get('kuota', 30, type=int)
    )
    db.session.add(k)
    db.session.commit()
    flash(f'Kelas {k.nama_kelas} berhasil ditambahkan!', 'success')
    return redirect(url_for('routes.kelas_list'))

@routes_bp.route('/admin/kelas/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def kelas_edit(id):
    if current_user.role != 'admin':
        flash('Akses ditolak!', 'danger')
        return redirect(url_for('routes.dashboard'))
    k = Kelas.query.get_or_404(id)
    if request.method == 'POST':
        k.nama_kelas = request.form.get('nama_kelas')
        k.tingkat = request.form.get('tingkat', type=int)
        k.tahun_ajaran_id = request.form.get('tahun_ajaran_id', type=int)
        k.wali_kelas_id = request.form.get('wali_kelas_id', type=int) or None
        k.kuota = request.form.get('kuota', 30, type=int)
        db.session.commit()
        flash(f'Kelas {k.nama_kelas} berhasil diupdate!', 'success')
        return redirect(url_for('routes.kelas_list'))
    guru_list = Guru.query.filter_by(is_active=True).all()
    ta_list = TahunAjaran.query.all()
    return render_template('admin/kelas.html', kelas_list=Kelas.query.all(),
                           guru_list=guru_list, ta_list=ta_list, editing=k)

@routes_bp.route('/admin/kelas/<int:id>/hapus', methods=['POST'])
@login_required
def kelas_hapus(id):
    if current_user.role != 'admin':
        flash('Akses ditolak!', 'danger')
        return redirect(url_for('routes.dashboard'))
    k = Kelas.query.get_or_404(id)
    if k.jumlah_siswa > 0:
        flash(f'Kelas {k.nama_kelas} masih memiliki {k.jumlah_siswa} siswa aktif. Pindahkan siswa terlebih dahulu.', 'danger')
        return redirect(url_for('routes.kelas_list'))
    db.session.delete(k)
    db.session.commit()
    flash(f'Kelas {k.nama_kelas} berhasil dihapus.', 'info')
    return redirect(url_for('routes.kelas_list'))

# ── Guru: Lihat Kelas Saya (Read-Only) ──────────────────────────
@routes_bp.route('/guru/kelas')
@login_required
def guru_kelas_view():
    """Guru can view their assigned class and students (read-only)."""
    if current_user.role not in ('admin', 'guru'):
        flash('Akses ditolak!', 'danger')
        return redirect(url_for('routes.dashboard'))
    
    # Get guru record
    guru = Guru.query.filter_by(id=current_user.guru_id).first() if current_user.guru_id else None
    
    if current_user.role == 'admin':
        # Admin sees all classes
        kelas_list = Kelas.query.all()
    elif guru:
        # Guru sees only their assigned class (wali kelas)
        kelas_list = Kelas.query.filter_by(wali_kelas_id=guru.id).all()
    else:
        kelas_list = []
    
    # Get students for each class
    kelas_siswa = {}
    for k in kelas_list:
        siswa = Siswa.query.filter_by(kelas_id=k.id, status='aktif').order_by(Siswa.nama_lengkap).all()
        kelas_siswa[k.id] = siswa
    
    return render_template('admin/kelas_guru.html', 
                         kelas_list=kelas_list, 
                         kelas_siswa=kelas_siswa,
                         guru=guru)

@routes_bp.route('/admin/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if current_user.role != 'admin':
        flash('Akses ditolak!', 'danger')
        return redirect(url_for('routes.dashboard'))

    sekolah = get_sekolah_config()

    if request.method == 'POST':
        # Toggle tahun ajaran
        ta_id = request.form.get('active_ta', type=int)
        if ta_id:
            TahunAjaran.query.update({TahunAjaran.is_active: False})
            ta = TahunAjaran.query.get(ta_id)
            if ta:
                ta.is_active = True
        # Toggle kurikulum
        kur_id = request.form.get('active_kurikulum', type=int)
        if kur_id:
            Kurikulum.query.update({Kurikulum.is_active: False})
            kur = Kurikulum.query.get(kur_id)
            if kur:
                kur.is_active = True

        # Save sekolah config
        sekolah.nama_sekolah = request.form.get('nama_sekolah', '').strip()
        sekolah.singkatan = request.form.get('singkatan', '').strip()
        sekolah.alamat = request.form.get('alamat', '').strip()
        sekolah.no_telepon = request.form.get('no_telepon', '').strip()
        sekolah.email = request.form.get('email', '').strip()
        sekolah.website = request.form.get('website', '').strip()
        sekolah.kepala_sekolah = request.form.get('kepala_sekolah', '').strip()
        sekolah.nip_kepala = request.form.get('nip_kepala', '').strip()
        sekolah.visi = request.form.get('visi', '').strip()
        sekolah.misi = request.form.get('misi', '').strip()
        sekolah.updated_at = utcnow_wib()

        # Handle logo upload
        logo = request.files.get('logo')
        if logo and logo.filename and '.' in logo.filename:
            ext = logo.filename.rsplit('.', 1)[1].lower()
            if ext in ('png', 'jpg', 'jpeg', 'gif', 'webp'):
                filename = secure_filename(f'sekolah_logo.{ext}')
                upload_dir = os.path.join(current_app.static_folder, 'uploads', 'logo')
                os.makedirs(upload_dir, exist_ok=True)
                upload_path = os.path.join(upload_dir, filename)
                logo.save(upload_path)
                sekolah.logo_path = f'logo/{filename}'

        db.session.commit()
        flash('Pengaturan berhasil disimpan!', 'success')
        return redirect(url_for('routes.settings'))

    ta_list = TahunAjaran.query.all()
    kur_list = Kurikulum.query.all()
    return render_template('admin/settings.html', ta_list=ta_list, kur_list=kur_list, sekolah=sekolah)
