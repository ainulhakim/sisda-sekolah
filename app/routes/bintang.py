"""
Bintang Harian routes for SiSD.
- POST /bintang/beri              — give stars/thumbs to students
- GET  /bintang/riwayat           — view history
- GET  /bintang/leaderboard       — class leaderboard
"""
from datetime import date, datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func

from app import db
from app.routes import routes_bp
from app.models import BintangHarian, Siswa, Guru, Kelas


# ── Beri Bintang / Jempol ──────────────────────────────────────
@routes_bp.route('/bintang/beri', methods=['POST'])
@login_required
def bintang_beri():
    """Give stars or thumbs down to selected students."""
    if current_user.role not in ('admin', 'guru'):
        flash('Akses ditolak!', 'danger')
        return redirect(url_for('routes.dashboard'))
    
    guru = Guru.query.filter_by(id=current_user.guru_id).first()
    if not guru:
        flash('Data guru tidak ditemukan!', 'danger')
        return redirect(url_for('routes.dashboard'))
    
    # Get form data
    kelas_id = request.form.get('kelas_id', type=int)
    siswa_ids = request.form.getlist('siswa_ids')  # list of siswa IDs
    jenis = request.form.get('jenis')  # 'bintang' or 'jempol'
    deskripsi = request.form.get('deskripsi', '').strip()
    tanggal = request.form.get('tanggal') or date.today().isoformat()
    
    # Validation
    if not kelas_id or not siswa_ids or not jenis or not deskripsi:
        flash('Semua field harus diisi! Minimal pilih 1 siswa.', 'danger')
        return redirect(url_for('routes.bintang_riwayat', kelas_id=kelas_id))
    
    if jenis not in ('bintang', 'jempol'):
        flash('Jenis harus bintang atau jempol!', 'danger')
        return redirect(url_for('routes.bintang_riwayat', kelas_id=kelas_id))
    
    # Parse date
    try:
        tgl = date.fromisoformat(tanggal)
    except ValueError:
        tgl = date.today()
    
    # Insert records
    count = 0
    for sid in siswa_ids:
        sid = int(sid) if sid.isdigit() else None
        if not sid:
            continue
        b = BintangHarian(
            siswa_id=sid,
            guru_id=guru.id,
            kelas_id=kelas_id,
            tanggal=tgl,
            jenis=jenis,
            deskripsi=deskripsi,
        )
        db.session.add(b)
        count += 1
    
    db.session.commit()
    
    icon = '⭐' if jenis == 'bintang' else '👎'
    flash(f'{icon} Berhasil memberikan {jenis} kepada {count} siswa!', 'success')
    return redirect(url_for('routes.bintang_riwayat', kelas_id=kelas_id))


# ── Riwayat Bintang ────────────────────────────────────────────
@routes_bp.route('/bintang/riwayat')
@login_required
def bintang_riwayat():
    """View bintang history for a class."""
    if current_user.role not in ('admin', 'guru'):
        flash('Akses ditolak!', 'danger')
        return redirect(url_for('routes.dashboard'))
    
    guru = Guru.query.filter_by(id=current_user.guru_id).first()
    kelas_id = request.args.get('kelas_id', type=int)
    
    # Get classes (wali + mengajar)
    if current_user.role == 'admin':
        kelas_list = Kelas.query.all()
    elif guru:
        wali = Kelas.query.filter_by(wali_kelas_id=guru.id).all()
        mengajar_ids = db.session.query(BintangHarian.kelas_id).filter_by(guru_id=guru.id).distinct().all()
        # Also get classes from GuruMengajar
        from app.models import GuruMengajar
        gm_ids = db.session.query(GuruMengajar.kelas_id).filter_by(guru_id=guru.id).distinct().all()
        all_ids = set([r[0] for r in mengajar_ids] + [r[0] for r in gm_ids])
        mengajar = Kelas.query.filter(Kelas.id.in_(list(all_ids))).all() if all_ids else []
        
        seen = set()
        kelas_list = []
        for k in wali + mengajar:
            if k.id not in seen:
                seen.add(k.id)
                kelas_list.append(k)
    else:
        kelas_list = []
    
    # Default to first class if none selected
    if not kelas_id and kelas_list:
        kelas_id = kelas_list[0].id
    
    # Get records for selected class
    records = []
    siswa_list = []
    if kelas_id:
        siswa_list = Siswa.query.filter_by(kelas_id=kelas_id, status='aktif').order_by(Siswa.nama_lengkap).all()
        
        query = BintangHarian.query.filter_by(kelas_id=kelas_id)
        
        # Filter by date
        tanggal = request.args.get('tanggal')
        if tanggal:
            try:
                tgl = date.fromisoformat(tanggal)
                query = query.filter_by(tanggal=tgl)
            except ValueError:
                pass
        
        records = query.order_by(BintangHarian.created_at.desc()).all()
    
    return render_template('bintang/riwayat.html',
                         kelas_list=kelas_list,
                         selected_kelas_id=kelas_id,
                         siswa_list=siswa_list,
                         records=records,
                         today=date.today().isoformat())


# ── Leaderboard Kelas ──────────────────────────────────────────
@routes_bp.route('/bintang/leaderboard')
@login_required
def bintang_leaderboard():
    """Class leaderboard: bintang - jempol = net score."""
    if current_user.role not in ('admin', 'guru'):
        flash('Akses ditolak!', 'danger')
        return redirect(url_for('routes.dashboard'))
    
    guru = Guru.query.filter_by(id=current_user.guru_id).first()
    kelas_id = request.args.get('kelas_id', type=int)
    periode = request.args.get('periode', 'all')  # 'all', 'bulan', 'minggu'
    
    # Get classes
    if current_user.role == 'admin':
        kelas_list = Kelas.query.all()
    elif guru:
        wali = Kelas.query.filter_by(wali_kelas_id=guru.id).all()
        from app.models import GuruMengajar
        gm_ids = db.session.query(GuruMengajar.kelas_id).filter_by(guru_id=guru.id).distinct().all()
        all_ids = set([r[0] for r in gm_ids])
        mengajar = Kelas.query.filter(Kelas.id.in_(list(all_ids))).all() if all_ids else []
        
        seen = set()
        kelas_list = []
        for k in wali + mengajar:
            if k.id not in seen:
                seen.add(k.id)
                kelas_list.append(k)
    else:
        kelas_list = []
    
    if not kelas_id and kelas_list:
        kelas_id = kelas_list[0].id
    
    # Calculate leaderboard
    leaderboard = []
    if kelas_id:
        siswa_list = Siswa.query.filter_by(kelas_id=kelas_id, status='aktif').all()
        
        for s in siswa_list:
            query = BintangHarian.query.filter_by(siswa_id=s.id, kelas_id=kelas_id)
            
            # Apply date filter
            today = date.today()
            if periode == 'minggu':
                from datetime import timedelta
                start = today - timedelta(days=today.weekday())  # Monday
                query = query.filter(BintangHarian.tanggal >= start)
            elif periode == 'bulan':
                from datetime import timedelta
                start = today.replace(day=1)
                query = query.filter(BintangHarian.tanggal >= start)
            
            bintang = query.filter_by(jenis='bintang').count()
            jempol = query.filter_by(jenis='jempol').count()
            net = bintang - jempol
            
            leaderboard.append({
                'siswa': s,
                'bintang': bintang,
                'jempol': jempol,
                'net': net,
            })
        
        # Sort by net score descending
        leaderboard.sort(key=lambda x: x['net'], reverse=True)
    
    return render_template('bintang/leaderboard.html',
                         kelas_list=kelas_list,
                         selected_kelas_id=kelas_id,
                         leaderboard=leaderboard,
                         periode=periode)


# ── API: Hapus Bintang ─────────────────────────────────────────
@routes_bp.route('/bintang/<int:id>/hapus', methods=['POST'])
@login_required
def bintang_hapus(id):
    """Delete a bintang record."""
    if current_user.role not in ('admin', 'guru'):
        return jsonify({'success': False, 'message': 'Akses ditolak'}), 403
    
    b = BintangHarian.query.get_or_404(id)
    kelas_id = b.kelas_id
    db.session.delete(b)
    db.session.commit()
    
    flash('Pencatatan bintang berhasil dihapus.', 'info')
    return redirect(url_for('routes.bintang_riwayat', kelas_id=kelas_id))
