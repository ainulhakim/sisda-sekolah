"""Migration script: add MataPelajaran + NilaiPelajaran tables and seed 6 default subjects."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app, db
from app.models import MataPelajaran

app = create_app()

with app.app_context():
    # Create new tables
    db.create_all()
    
    # Seed 6 default subjects if not exist
    default_subjects = [
        ('Bahasa Indonesia', 'BIndo', 'Mata pelajaran bahasa dan sastra Indonesia', 'utama'),
        ('Matematika', 'MTK', 'Mata pelajaran ilmu hitung dan logika', 'utama'),
        ('IPA', 'IPA', 'Ilmu Pengetahuan Alam', 'utama'),
        ('IPS', 'IPS', 'Ilmu Pengetahuan Sosial', 'utama'),
        ('Pendidikan Agama', 'AGAMA', 'Pendidikan Agama dan Budi Pekerti', 'utama'),
        ('Bahasa Inggris', 'INGGRIS', 'Bahasa Inggris sebagai bahasa asing', 'utama'),
    ]
    
    added = 0
    for nama, kode, deskripsi, tipe in default_subjects:
        if not MataPelajaran.query.filter_by(kode=kode).first():
            db.session.add(MataPelajaran(
                nama=nama, kode=kode, deskripsi=deskripsi, tipe=tipe, is_active=True
            ))
            added += 1
    
    if added:
        db.session.commit()
        print(f'✅ {added} mata pelajaran berhasil ditambahkan!')
    else:
        print('ℹ️  Semua mata pelajaran sudah ada.')
    
    # List all subjects
    all_mp = MataPelajaran.query.order_by(MataPelajaran.nama).all()
    print(f'\n📚 Total mata pelajaran: {len(all_mp)}')
    for mp in all_mp:
        print(f'   {mp.kode:10s} - {mp.nama}')
