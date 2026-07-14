from app.timezone import now_wib
import csv, io, json, os
from flask import render_template, request, redirect, url_for, flash, send_file, current_app
from flask_login import login_required, current_user
from app.routes import routes_bp
from app.models import Siswa, Kelas, TahunAjaran, ImportLog
from app import db
from datetime import datetime
from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_foto(siswa):
    """Handle photo upload for a siswa"""
    foto = request.files.get('foto')
    if foto and foto.filename and allowed_file(foto.filename):
        ext = foto.filename.rsplit('.', 1)[1].lower()
        filename = secure_filename(f'siswa_{siswa.id}_{now_wib().strftime("%Y%m%d%H%M%S")}.{ext}')
        upload_dir = os.path.join(current_app.static_folder, 'uploads', 'avatars')
        os.makedirs(upload_dir, exist_ok=True)
        upload_path = os.path.join(upload_dir, filename)
        foto.save(upload_path)
        siswa.foto_profil = f'avatars/{filename}'
        return True
    return False

@routes_bp.route('/siswa')
@login_required
def siswa_list():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    kelas_id = request.args.get('kelas_id', type=int)
    status = request.args.get('status', 'aktif')
    query = Siswa.query.filter_by(status=status)
    if search:
        query = query.filter(Siswa.nama_lengkap.ilike(f'%{search}%'))
    if kelas_id:
        query = query.filter_by(kelas_id=kelas_id)
    siswa = query.order_by(Siswa.nama_lengkap).paginate(page=page, per_page=15, error_out=False)
    kelas_list = Kelas.query.all()
    return render_template('siswa/list.html', siswa=siswa, kelas_list=kelas_list, search=search, kelas_id=kelas_id, status=status)

@routes_bp.route('/siswa/tambah', methods=['GET', 'POST'])
@login_required
def siswa_tambah():
    if current_user.role not in ('admin', 'guru'):
        flash('Akses ditolak!', 'danger')
        return redirect(url_for('routes.siswa_list'))
    if request.method == 'POST':
        ta = TahunAjaran.query.filter_by(is_active=True).first()
        s = Siswa(
            nisn=request.form.get('nisn') or None,
            nama_lengkap=request.form.get('nama_lengkap'),
            nama_panggilan=request.form.get('nama_panggilan'),
            jenis_kelamin=request.form.get('jenis_kelamin'),
            tanggal_lahir=datetime.strptime(request.form['tanggal_lahir'], '%Y-%m-%d').date() if request.form.get('tanggal_lahir') else None,
            tempat_lahir=request.form.get('tempat_lahir'),
            alamat=request.form.get('alamat'),
            no_hp_ortu=request.form.get('no_hp_ortu'),
            nama_ortu=request.form.get('nama_ortu'),
            kelas_id=request.form.get('kelas_id', type=int),
            tahun_ajaran_id=ta.id if ta else None,
            status='aktif'
        )
        db.session.add(s)
        db.session.flush()  # Get s.id before saving photo
        save_foto(s)
        db.session.commit()
        flash(f'Siswa {s.nama_lengkap} berhasil ditambahkan!', 'success')
        return redirect(url_for('routes.siswa_list'))
    kelas_list = Kelas.query.all()
    return render_template('siswa/form.html', siswa=None, kelas_list=kelas_list)

@routes_bp.route('/siswa/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def siswa_edit(id):
    if current_user.role not in ('admin', 'guru'):
        flash('Akses ditolak!', 'danger')
        return redirect(url_for('routes.siswa_list'))
    s = Siswa.query.get_or_404(id)
    if request.method == 'POST':
        s.nisn = request.form.get('nisn') or None
        s.nama_lengkap = request.form.get('nama_lengkap')
        s.nama_panggilan = request.form.get('nama_panggilan')
        s.jenis_kelamin = request.form.get('jenis_kelamin')
        s.tanggal_lahir = datetime.strptime(request.form['tanggal_lahir'], '%Y-%m-%d').date() if request.form.get('tanggal_lahir') else None
        s.tempat_lahir = request.form.get('tempat_lahir')
        s.alamat = request.form.get('alamat')
        s.no_hp_ortu = request.form.get('no_hp_ortu')
        s.nama_ortu = request.form.get('nama_ortu')
        s.kelas_id = request.form.get('kelas_id', type=int)
        s.status = request.form.get('status', 'aktif')
        save_foto(s)
        db.session.commit()
        flash(f'Data {s.nama_lengkap} berhasil diupdate!', 'success')
        return redirect(url_for('routes.siswa_detail', id=id))
    kelas_list = Kelas.query.all()
    return render_template('siswa/form.html', siswa=s, kelas_list=kelas_list)

@routes_bp.route('/siswa/<int:id>')
@login_required
def siswa_detail(id):
    s = Siswa.query.get_or_404(id)
    from app.models import SiswaBadge, Absensi
    badges = SiswaBadge.query.filter_by(siswa_id=id).all()
    absensi = Absensi.query.filter_by(siswa_id=id).order_by(Absensi.tanggal.desc()).limit(30).all()
    return render_template('siswa/detail.html', siswa=s, badges=badges, absensi=absensi)

@routes_bp.route('/siswa/<int:id>/hapus', methods=['POST'])
@login_required
def siswa_hapus(id):
    if current_user.role != 'admin':
        flash('Hanya admin yang bisa menghapus!', 'danger')
        return redirect(url_for('routes.siswa_list'))
    s = Siswa.query.get_or_404(id)
    s.status = 'keluar'
    db.session.commit()
    flash(f'{s.nama_lengkap} telah ditandai keluar.', 'info')
    return redirect(url_for('routes.siswa_list'))

@routes_bp.route('/siswa/import', methods=['GET', 'POST'])
@login_required
def siswa_import():
    if current_user.role not in ('admin', 'guru'):
        flash('Akses ditolak!', 'danger')
        return redirect(url_for('routes.siswa_list'))
    if request.method == 'POST':
        file = request.files.get('file')
        if not file or not file.filename.endswith('.csv'):
            flash('File harus berformat CSV!', 'danger')
            return redirect(url_for('routes.siswa_import'))
        content = file.read().decode('utf-8')
        reader = csv.DictReader(io.StringIO(content))
        ta = TahunAjaran.query.filter_by(is_active=True).first()
        errors = []
        success = 0
        total = 0
        for row in reader:
            total += 1
            try:
                if not row.get('nisn') or not row.get('nama_lengkap'):
                    errors.append(f'Baris {total}: NISN atau nama kosong')
                    continue
                kelas = Kelas.query.filter_by(nama_kelas=row.get('kelas_nama', '')).first()
                s = Siswa(
                    nisn=row['nisn'], nama_lengkap=row['nama_lengkap'],
                    nama_panggilan=row.get('nama_panggilan'),
                    jenis_kelamin=row.get('jenis_kelamin', 'L'),
                    tanggal_lahir=datetime.strptime(row['tanggal_lahir'], '%Y-%m-%d').date() if row.get('tanggal_lahir') else None,
                    tempat_lahir=row.get('tempat_lahir'),
                    alamat=row.get('alamat'),
                    no_hp_ortu=row.get('no_hp_ortu'),
                    nama_ortu=row.get('nama_ortu'),
                    kelas_id=kelas.id if kelas else None,
                    tahun_ajaran_id=ta.id if ta else None,
                    status=row.get('status', 'aktif')
                )
                db.session.add(s)
                success += 1
            except Exception as e:
                errors.append(f'Baris {total}: {str(e)}')
        db.session.commit()
        log = ImportLog(filename=file.filename, total_rows=total, success_count=success,
                        error_count=len(errors), errors_json=json.dumps(errors),
                        imported_by=current_user.id)
        db.session.add(log)
        db.session.commit()
        flash(f'Import selesai: {success} berhasil, {len(errors)} error.', 'success' if not errors else 'warning')
        return render_template('siswa/import.html', log=log, errors=errors)
    return render_template('siswa/import.html', log=None, errors=[])

@routes_bp.route('/siswa/export')
@login_required
def siswa_export():
    if current_user.role not in ('admin', 'guru'):
        flash('Akses ditolak!', 'danger')
        return redirect(url_for('routes.siswa_list'))
    siswa = Siswa.query.filter_by(status='aktif').all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['nisn','nama_lengkap','nama_panggilan','jenis_kelamin','tanggal_lahir','tempat_lahir','alamat','no_hp_ortu','nama_ortu','kelas','status'])
    for s in siswa:
        writer.writerow([s.nisn, s.nama_lengkap, s.nama_panggilan, s.jenis_kelamin,
                        s.tanggal_lahir, s.tempat_lahir, s.alamat, s.no_hp_ortu,
                        s.nama_ortu, s.kelas.nama_kelas if s.kelas else '', s.status])
    output.seek(0)
    return send_file(io.BytesIO(output.getvalue().encode('utf-8')), mimetype='text/csv',
                    as_attachment=True, download_name='data_siswa.csv')
