from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.routes import routes_bp
from app.models import Lomba, PrestasiLomba, Siswa, TahunAjaran
from app import db
from datetime import datetime


# ─── LOMBA CRUD (admin only) ───

@routes_bp.route('/lomba')
@login_required
def lomba_list():
    if current_user.role != 'admin':
        flash('Akses ditolak!', 'danger')
        return redirect(url_for('routes.dashboard'))
    search = request.args.get('search', '')
    query = Lomba.query
    if search:
        query = query.filter(Lomba.nama_lomba.ilike(f'%{search}%'))
    lomba_list = query.order_by(Lomba.tanggal.desc().nullslast()).all()
    return render_template('lomba/list.html', lomba_list=lomba_list, search=search)


@routes_bp.route('/lomba/tambah', methods=['GET', 'POST'])
@login_required
def lomba_tambah():
    if current_user.role != 'admin':
        flash('Akses ditolak!', 'danger')
        return redirect(url_for('routes.dashboard'))
    if request.method == 'POST':
        ta_id = request.form.get('tahun_ajaran_id', type=int)
        lomba = Lomba(
            nama_lomba=request.form.get('nama_lomba'),
            bidang=request.form.get('bidang'),
            penyelenggara=request.form.get('penyelenggara'),
            tingkat=request.form.get('tingkat'),
            tanggal=datetime.strptime(request.form['tanggal'], '%Y-%m-%d').date() if request.form.get('tanggal') else None,
            tahun_ajaran_id=ta_id if ta_id else None,
        )
        db.session.add(lomba)
        db.session.commit()
        flash(f'Lomba "{lomba.nama_lomba}" berhasil ditambahkan!', 'success')
        return redirect(url_for('routes.lomba_list'))
    ta_list = TahunAjaran.query.order_by(TahunAjaran.nama.desc()).all()
    return render_template('lomba/form.html', lomba=None, ta_list=ta_list)


@routes_bp.route('/lomba/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def lomba_edit(id):
    if current_user.role != 'admin':
        flash('Akses ditolak!', 'danger')
        return redirect(url_for('routes.dashboard'))
    lomba = Lomba.query.get_or_404(id)
    if request.method == 'POST':
        lomba.nama_lomba = request.form.get('nama_lomba')
        lomba.bidang = request.form.get('bidang')
        lomba.penyelenggara = request.form.get('penyelenggara')
        lomba.tingkat = request.form.get('tingkat')
        lomba.tanggal = datetime.strptime(request.form['tanggal'], '%Y-%m-%d').date() if request.form.get('tanggal') else None
        ta_id = request.form.get('tahun_ajaran_id', type=int)
        lomba.tahun_ajaran_id = ta_id if ta_id else None
        db.session.commit()
        flash(f'Lomba "{lomba.nama_lomba}" berhasil diupdate!', 'success')
        return redirect(url_for('routes.lomba_list'))
    ta_list = TahunAjaran.query.order_by(TahunAjaran.nama.desc()).all()
    return render_template('lomba/form.html', lomba=lomba, ta_list=ta_list)


@routes_bp.route('/lomba/<int:id>/hapus', methods=['POST'])
@login_required
def lomba_hapus(id):
    if current_user.role != 'admin':
        flash('Akses ditolak!', 'danger')
        return redirect(url_for('routes.dashboard'))
    lomba = Lomba.query.get_or_404(id)
    if lomba.jumlah_prestasi > 0:
        flash(f'Tidak bisa menghapus lomba "{lomba.nama_lomba}" karena masih ada prestasi terkait ({lomba.jumlah_prestasi} data).', 'danger')
        return redirect(url_for('routes.lomba_list'))
    nama = lomba.nama_lomba
    db.session.delete(lomba)
    db.session.commit()
    flash(f'Lomba "{nama}" berhasil dihapus.', 'success')
    return redirect(url_for('routes.lomba_list'))


# ─── PRESTASI CRUD (admin only) ───

@routes_bp.route('/lomba/prestasi/tambah', methods=['GET', 'POST'])
@login_required
def prestasi_tambah():
    if current_user.role != 'admin':
        flash('Akses ditolak!', 'danger')
        return redirect(url_for('routes.dashboard'))
    if request.method == 'POST':
        prestasi = PrestasiLomba(
            siswa_id=request.form.get('siswa_id', type=int),
            lomba_id=request.form.get('lomba_id', type=int),
            juara=request.form.get('juara'),
            kategori=request.form.get('kategori'),
            catatan=request.form.get('catatan'),
            tanggal_dapat=datetime.strptime(request.form['tanggal_dapat'], '%Y-%m-%d').date() if request.form.get('tanggal_dapat') else None,
        )
        db.session.add(prestasi)
        db.session.commit()
        flash('Prestasi berhasil ditambahkan!', 'success')
        return redirect(url_for('routes.lomba_list'))
    siswa_list = Siswa.query.filter_by(status='aktif').order_by(Siswa.nama_lengkap).all()
    lomba_list = Lomba.query.filter_by(is_active=True).order_by(Lomba.nama_lomba).all()
    return render_template('lomba/prestasi_form.html', prestasi=None, siswa_list=siswa_list, lomba_list=lomba_list)


@routes_bp.route('/lomba/prestasi/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def prestasi_edit(id):
    if current_user.role != 'admin':
        flash('Akses ditolak!', 'danger')
        return redirect(url_for('routes.dashboard'))
    prestasi = PrestasiLomba.query.get_or_404(id)
    if request.method == 'POST':
        prestasi.siswa_id = request.form.get('siswa_id', type=int)
        prestasi.lomba_id = request.form.get('lomba_id', type=int)
        prestasi.juara = request.form.get('juara')
        prestasi.kategori = request.form.get('kategori')
        prestasi.catatan = request.form.get('catatan')
        prestasi.tanggal_dapat = datetime.strptime(request.form['tanggal_dapat'], '%Y-%m-%d').date() if request.form.get('tanggal_dapat') else None
        db.session.commit()
        flash('Prestasi berhasil diupdate!', 'success')
        return redirect(url_for('routes.lomba_list'))
    siswa_list = Siswa.query.filter_by(status='aktif').order_by(Siswa.nama_lengkap).all()
    lomba_list = Lomba.query.filter_by(is_active=True).order_by(Lomba.nama_lomba).all()
    return render_template('lomba/prestasi_form.html', prestasi=prestasi, siswa_list=siswa_list, lomba_list=lomba_list)


@routes_bp.route('/lomba/prestasi/<int:id>/hapus', methods=['POST'])
@login_required
def prestasi_hapus(id):
    if current_user.role != 'admin':
        flash('Akses ditolak!', 'danger')
        return redirect(url_for('routes.dashboard'))
    prestasi = PrestasiLomba.query.get_or_404(id)
    db.session.delete(prestasi)
    db.session.commit()
    flash('Prestasi berhasil dihapus.', 'success')
    return redirect(url_for('routes.lomba_list'))


@routes_bp.route('/lomba/siswa/<int:id>/prestasi')
@login_required
def prestasi_siswa(id):
    siswa = Siswa.query.get_or_404(id)
    prestasi = PrestasiLomba.query.filter_by(siswa_id=id).order_by(PrestasiLomba.tanggal_dapat.desc().nullslast()).all()
    return render_template('lomba/prestasi_siswa.html', siswa=siswa, prestasi_list=prestasi)
