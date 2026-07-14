from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.routes import routes_bp
from app.models import MataPelajaran, NilaiPelajaran, Siswa, Kelas, TahunAjaran, Guru
from app import db


def _get_active_ta():
    return TahunAjaran.query.filter_by(is_active=True).first()


# ── List Mata Pelajaran ──────────────────────────────────────────
@routes_bp.route('/pelajaran')
@login_required
def pelajaran_list():
    if current_user.role not in ('admin', 'guru'):
        flash('Akses ditolak!', 'danger')
        return redirect(url_for('routes.dashboard'))
    pelajaran = MataPelajaran.query.order_by(MataPelajaran.nama).all()
    return render_template('pelajaran/list.html', pelajaran_list=pelajaran)


# ── Tambah Mata Pelajaran (admin only) ──────────────────────────
@routes_bp.route('/pelajaran/tambah', methods=['GET', 'POST'])
@login_required
def pelajaran_tambah():
    if current_user.role != 'admin':
        flash('Hanya admin yang bisa menambah mata pelajaran!', 'danger')
        return redirect(url_for('routes.pelajaran_list'))
    if request.method == 'POST':
        kode = request.form.get('kode', '').strip().upper()
        if MataPelajaran.query.filter_by(kode=kode).first():
            flash(f'Kode "{kode}" sudah digunakan!', 'danger')
            return redirect(url_for('routes.pelajaran_tambah'))
        mp = MataPelajaran(
            nama=request.form.get('nama', '').strip(),
            kode=kode,
            deskripsi=request.form.get('deskripsi', '').strip(),
            tipe=request.form.get('tipe', 'utama'),
            is_active=True
        )
        db.session.add(mp)
        db.session.commit()
        flash(f'Mata pelajaran "{mp.nama}" berhasil ditambahkan!', 'success')
        return redirect(url_for('routes.pelajaran_list'))
    return render_template('pelajaran/form.html', mp=None)


# ── Edit Mata Pelajaran (admin only) ────────────────────────────
@routes_bp.route('/pelajaran/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def pelajaran_edit(id):
    if current_user.role != 'admin':
        flash('Hanya admin yang bisa mengedit!', 'danger')
        return redirect(url_for('routes.pelajaran_list'))
    mp = MataPelajaran.query.get_or_404(id)
    if request.method == 'POST':
        kode = request.form.get('kode', '').strip().upper()
        existing = MataPelajaran.query.filter_by(kode=kode).first()
        if existing and existing.id != id:
            flash(f'Kode "{kode}" sudah digunakan!', 'danger')
            return redirect(url_for('routes.pelajaran_edit', id=id))
        mp.nama = request.form.get('nama', '').strip()
        mp.kode = kode
        mp.deskripsi = request.form.get('deskripsi', '').strip()
        mp.tipe = request.form.get('tipe', 'utama')
        mp.is_active = 'is_active' in request.form
        db.session.commit()
        flash(f'Mata pelajaran "{mp.nama}" berhasil diupdate!', 'success')
        return redirect(url_for('routes.pelajaran_list'))
    return render_template('pelajaran/form.html', mp=mp)


# ── Hapus Mata Pelajaran (admin only) ───────────────────────────
@routes_bp.route('/pelajaran/<int:id>/hapus', methods=['POST'])
@login_required
def pelajaran_hapus(id):
    if current_user.role != 'admin':
        flash('Hanya admin yang bisa menghapus!', 'danger')
        return redirect(url_for('routes.pelajaran_list'))
    mp = MataPelajaran.query.get_or_404(id)
    if mp.nilai_list:
        flash(f'Mata pelajaran "{mp.nama}" masih memiliki data nilai. Hapus data nilai terlebih dahulu.', 'danger')
        return redirect(url_for('routes.pelajaran_list'))
    nama = mp.nama
    db.session.delete(mp)
    db.session.commit()
    flash(f'Mata pelajaran "{nama}" berhasil dihapus.', 'info')
    return redirect(url_for('routes.pelajaran_list'))


# ── Input Nilai per Mata Pelajaran ──────────────────────────────
@routes_bp.route('/pelajaran/<int:id>/input-nilai', methods=['GET', 'POST'])
@login_required
def pelajaran_input_nilai(id):
    if current_user.role not in ('admin', 'guru'):
        flash('Akses ditolak!', 'danger')
        return redirect(url_for('routes.pelajaran_list'))
    mp = MataPelajaran.query.get_or_404(id)
    ta = _get_active_ta()
    semester = request.args.get('semester', 1, type=int)

    # For guru, only show their wali kelas students
    if current_user.role == 'guru':
        guru = Guru.query.filter_by(id=current_user.guru_id).first()
        if guru:
            kelas = Kelas.query.filter_by(wali_kelas_id=guru.id, tahun_ajaran_id=ta.id).first() if ta else None
            if kelas:
                siswa_list = Siswa.query.filter_by(kelas_id=kelas.id, status='aktif').order_by(Siswa.nama_lengkap).all()
            else:
                siswa_list = []
        else:
            siswa_list = []
    else:
        # Admin: show all active students, optionally filtered by kelas
        kelas_id = request.args.get('kelas_id', type=int)
        query = Siswa.query.filter_by(status='aktif')
        if kelas_id:
            query = query.filter_by(kelas_id=kelas_id)
        siswa_list = query.order_by(Siswa.nama_lengkap).all()

    kelas_list = Kelas.query.order_by(Kelas.nama_kelas).all()

    if request.method == 'POST':
        saved = 0
        for s in siswa_list:
            prefix = f'siswa_{s.id}_'
            uh_1 = request.form.get(f'{prefix}uh_1', '').strip()
            uh_2 = request.form.get(f'{prefix}uh_2', '').strip()
            uh_3 = request.form.get(f'{prefix}uh_3', '').strip()
            uh_4 = request.form.get(f'{prefix}uh_4', '').strip()
            uts = request.form.get(f'{prefix}uts', '').strip()
            uas = request.form.get(f'{prefix}uas', '').strip()
            tugas_1 = request.form.get(f'{prefix}tugas_1', '').strip()
            tugas_2 = request.form.get(f'{prefix}tugas_2', '').strip()
            tugas_3 = request.form.get(f'{prefix}tugas_3', '').strip()
            catatan = request.form.get(f'{prefix}catatan', '').strip()

            # Skip if all empty (no data entered for this student)
            all_empty = not any([uh_1, uh_2, uh_3, uh_4, uts, uas, tugas_1, tugas_2, tugas_3])
            if all_empty:
                continue

            def to_float(v):
                try:
                    f = float(v)
                    return max(0, min(100, f)) if v else None
                except (ValueError, TypeError):
                    return None

            # Get existing or create new
            nilai = NilaiPelajaran.query.filter_by(
                siswa_id=s.id, mata_pelajaran_id=mp.id,
                tahun_ajaran_id=ta.id if ta else None, semester=semester
            ).first()

            if not nilai:
                nilai = NilaiPelajaran(
                    siswa_id=s.id, mata_pelajaran_id=mp.id,
                    tahun_ajaran_id=ta.id if ta else None, semester=semester
                )
                db.session.add(nilai)

            nilai.uh_1 = to_float(uh_1)
            nilai.uh_2 = to_float(uh_2)
            nilai.uh_3 = to_float(uh_3)
            nilai.uh_4 = to_float(uh_4)
            nilai.uts = to_float(uts)
            nilai.uas = to_float(uas)
            nilai.tugas_1 = to_float(tugas_1)
            nilai.tugas_2 = to_float(tugas_2)
            nilai.tugas_3 = to_float(tugas_3)
            nilai.catatan = catatan if catatan else None
            saved += 1

        db.session.commit()
        flash(f'Berhasil menyimpan nilai untuk {saved} siswa di mata pelajaran "{mp.nama}"!', 'success')
        return redirect(url_for('routes.pelajaran_input_nilai', id=id, semester=semester))

    # Pre-load existing grades
    existing_grades = {}
    for s in siswa_list:
        n = NilaiPelajaran.query.filter_by(
            siswa_id=s.id, mata_pelajaran_id=mp.id,
            tahun_ajaran_id=ta.id if ta else None, semester=semester
        ).first()
        if n:
            existing_grades[s.id] = n

    return render_template('pelajaran/input_nilai.html',
                           mp=mp, siswa_list=siswa_list, kelas_list=kelas_list,
                           existing_grades=existing_grades, ta=ta, semester=semester)


# ── Lihat Nilai Siswa ──────────────────────────────────────────
@routes_bp.route('/siswa/<int:id>/nilai')
@login_required
def siswa_nilai(id):
    siswa = Siswa.query.get_or_404(id)
    ta_id = request.args.get('ta_id', type=int)
    semester = request.args.get('semester', 1, type=int)

    query = NilaiPelajaran.query.filter_by(siswa_id=id)
    if ta_id:
        query = query.filter_by(tahun_ajaran_id=ta_id)
    query = query.filter_by(semester=semester)

    nilai_list = query.order_by(NilaiPelajaran.mata_pelajaran_id).all()

    # Group by subject
    nilai_by_mp = {}
    for n in nilai_list:
        mp_id = n.mata_pelajaran_id
        if mp_id not in nilai_by_mp:
            nilai_by_mp[mp_id] = {
                'mata_pelajaran': n.mata_pelajaran,
                'nilai': n
            }
    ta_list = TahunAjaran.query.order_by(TahunAjaran.nama.desc()).all()
    return render_template('siswa/nilai.html', siswa=siswa, nilai_by_mp=nilai_by_mp,
                           ta_list=ta_list, selected_ta=ta_id, semester=semester)
