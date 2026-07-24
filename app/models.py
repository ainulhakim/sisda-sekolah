from app.timezone import utcnow_wib
from datetime import datetime, date
from app import db, login_manager
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='siswa')  # admin/guru/ortu/siswa
    guru_id = db.Column(db.Integer, db.ForeignKey('guru.id'), nullable=True)
    siswa_id = db.Column(db.Integer, db.ForeignKey('siswa.id'), nullable=True)
    is_active_user = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    guru = db.relationship('Guru', backref='user', lazy=True)
    siswa = db.relationship('Siswa', backref='user', lazy=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class TahunAjaran(db.Model):
    __tablename__ = 'tahun_ajaran'
    id = db.Column(db.Integer, primary_key=True)
    nama = db.Column(db.String(20), nullable=False)
    semester = db.Column(db.Integer, nullable=False)
    is_active = db.Column(db.Boolean, default=False)
    
    kelas = db.relationship('Kelas', backref='tahun_ajaran', lazy=True)
    siswa = db.relationship('Siswa', backref='tahun_ajaran', lazy=True)
    siswa_badge = db.relationship('SiswaBadge', backref='tahun_ajaran', lazy=True)

class Guru(db.Model):
    __tablename__ = 'guru'
    id = db.Column(db.Integer, primary_key=True)
    nip = db.Column(db.String(30), unique=True)
    nama_lengkap = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120))
    no_hp = db.Column(db.String(20))
    foto_profil = db.Column(db.String(200))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    kelas_wali = db.relationship('Kelas', backref='wali_kelas', lazy=True)
    absensi = db.relationship('Absensi', backref='guru', lazy=True)
    mengajar = db.relationship('GuruMengajar', backref='guru', lazy=True)

class GuruMengajar(db.Model):
    """Guru yang mengampu mata pelajaran di kelas tertentu."""
    __tablename__ = 'guru_mengajar'
    id = db.Column(db.Integer, primary_key=True)
    guru_id = db.Column(db.Integer, db.ForeignKey('guru.id'), nullable=False)
    kelas_id = db.Column(db.Integer, db.ForeignKey('kelas.id'), nullable=False)
    mata_pelajaran_id = db.Column(db.Integer, db.ForeignKey('mata_pelajaran.id'), nullable=False)
    tahun_ajaran_id = db.Column(db.Integer, db.ForeignKey('tahun_ajaran.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    mata_pelajaran = db.relationship('MataPelajaran', backref='guru_mengajar', lazy=True)
    tahun_ajaran = db.relationship('TahunAjaran', backref='guru_mengajar', lazy=True)
    
    # Unique constraint: one teacher per subject per class per year
    __table_args__ = (
        db.UniqueConstraint('guru_id', 'kelas_id', 'mata_pelajaran_id', 'tahun_ajaran_id', 
                           name='uq_guru_kelas_mp_ta'),
    )

class Kelas(db.Model):
    __tablename__ = 'kelas'
    id = db.Column(db.Integer, primary_key=True)
    nama_kelas = db.Column(db.String(10), nullable=False)
    tingkat = db.Column(db.Integer, nullable=False)
    tahun_ajaran_id = db.Column(db.Integer, db.ForeignKey('tahun_ajaran.id'))
    wali_kelas_id = db.Column(db.Integer, db.ForeignKey('guru.id'), nullable=True)
    kuota = db.Column(db.Integer, default=30)
    
    siswa = db.relationship('Siswa', backref='kelas', lazy=True)
    absensi = db.relationship('Absensi', backref='kelas', lazy=True)
    guru_mengajar = db.relationship('GuruMengajar', backref='kelas', lazy=True)
    
    @property
    def jumlah_siswa(self):
        return Siswa.query.filter_by(kelas_id=self.id, status='aktif').count()

class Siswa(db.Model):
    __tablename__ = 'siswa'
    id = db.Column(db.Integer, primary_key=True)
    nisn = db.Column(db.String(20), unique=True)
    nama_lengkap = db.Column(db.String(100), nullable=False)
    nama_panggilan = db.Column(db.String(50))
    jenis_kelamin = db.Column(db.String(1), nullable=False)
    tanggal_lahir = db.Column(db.Date)
    tempat_lahir = db.Column(db.String(50))
    alamat = db.Column(db.Text)
    no_hp_ortu = db.Column(db.String(20))
    nama_ortu = db.Column(db.String(100))
    foto_profil = db.Column(db.String(200))
    kelas_id = db.Column(db.Integer, db.ForeignKey('kelas.id'))
    tahun_ajaran_id = db.Column(db.Integer, db.ForeignKey('tahun_ajaran.id'))
    status = db.Column(db.String(20), default='aktif')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    absensi = db.relationship('Absensi', backref='siswa', lazy=True)
    badges = db.relationship('SiswaBadge', backref='siswa', lazy=True)
    
    @property
    def streak_hadir(self):
        from datetime import timedelta
        streak = 0
        today = date.today()
        for i in range(365):
            check_date = today - timedelta(days=i)
            a = Absensi.query.filter_by(siswa_id=self.id, tanggal=check_date, status='hadir').first()
            if a:
                streak += 1
            else:
                break
        return streak
    
    @property
    def persentase_kehadiran(self):
        total = Absensi.query.filter_by(siswa_id=self.id).count()
        if total == 0:
            return 0
        hadir = Absensi.query.filter_by(siswa_id=self.id, status='hadir').count()
        return round((hadir / total) * 100, 1)

class Absensi(db.Model):
    __tablename__ = 'absensi'
    id = db.Column(db.Integer, primary_key=True)
    siswa_id = db.Column(db.Integer, db.ForeignKey('siswa.id'), nullable=False)
    kelas_id = db.Column(db.Integer, db.ForeignKey('kelas.id'), nullable=False)
    tanggal = db.Column(db.Date, nullable=False, default=date.today)
    status = db.Column(db.String(20), nullable=False, default='hadir')
    mood = db.Column(db.String(20))
    check_in_time = db.Column(db.DateTime)
    check_out_time = db.Column(db.DateTime)
    check_in_method = db.Column(db.String(20), default='manual')
    guru_id = db.Column(db.Integer, db.ForeignKey('guru.id'), nullable=True)
    catatan = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('siswa_id', 'tanggal', name='unique_siswa_tanggal'),)

class Badge(db.Model):
    __tablename__ = 'badge'
    id = db.Column(db.Integer, primary_key=True)
    nama = db.Column(db.String(50), nullable=False)
    deskripsi = db.Column(db.Text)
    icon_emoji = db.Column(db.String(10))
    warna = db.Column(db.String(10))
    syarat_tipe = db.Column(db.String(30), nullable=False)
    syarat_nilai = db.Column(db.Integer, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    
    siswa_badges = db.relationship('SiswaBadge', backref='badge', lazy=True)

class SiswaBadge(db.Model):
    __tablename__ = 'siswa_badge'
    id = db.Column(db.Integer, primary_key=True)
    siswa_id = db.Column(db.Integer, db.ForeignKey('siswa.id'), nullable=False)
    badge_id = db.Column(db.Integer, db.ForeignKey('badge.id'), nullable=False)
    tanggal_dapat = db.Column(db.Date, default=date.today)
    tahun_ajaran_id = db.Column(db.Integer, db.ForeignKey('tahun_ajaran.id'))

class Kurikulum(db.Model):
    __tablename__ = 'kurikulum'
    id = db.Column(db.Integer, primary_key=True)
    nama = db.Column(db.String(50), nullable=False)
    deskripsi = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=False)

class SekolahConfig(db.Model):
    __tablename__ = 'sekolah_config'
    id = db.Column(db.Integer, primary_key=True)
    nama_sekolah = db.Column(db.String(200), default='SANTREN KODING')
    singkatan = db.Column(db.String(50), default='SK')
    alamat = db.Column(db.Text, default='')
    no_telepon = db.Column(db.String(30), default='')
    email = db.Column(db.String(120), default='')
    website = db.Column(db.String(200), default='')
    kepala_sekolah = db.Column(db.String(100), default='')
    nip_kepala = db.Column(db.String(30), default='')
    logo_path = db.Column(db.String(200), default='')
    visi = db.Column(db.Text, default='')
    misi = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


def get_sekolah_config():
    """Get or create default school config."""
    config = SekolahConfig.query.first()
    if not config:
        config = SekolahConfig()
        db.session.add(config)
        db.session.commit()
    return config


class Lomba(db.Model):
    __tablename__ = 'lomba'
    id = db.Column(db.Integer, primary_key=True)
    nama_lomba = db.Column(db.String(200), nullable=False)
    bidang = db.Column(db.String(100))  # Akademik, Olahraga, Seni, Keagamaan, Teknologi
    penyelenggara = db.Column(db.String(200))
    tingkat = db.Column(db.String(50))  # Sekolah, Kecamatan, Kabupaten, Provinsi, Nasional
    tanggal = db.Column(db.Date)
    tahun_ajaran_id = db.Column(db.Integer, db.ForeignKey('tahun_ajaran.id'), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    tahun_ajaran = db.relationship('TahunAjaran', backref='lomba_list')

    @property
    def jumlah_prestasi(self):
        return PrestasiLomba.query.filter_by(lomba_id=self.id).count()


class PrestasiLomba(db.Model):
    __tablename__ = 'prestasi_lomba'
    id = db.Column(db.Integer, primary_key=True)
    siswa_id = db.Column(db.Integer, db.ForeignKey('siswa.id'), nullable=False)
    lomba_id = db.Column(db.Integer, db.ForeignKey('lomba.id'), nullable=False)
    juara = db.Column(db.String(50))  # Juara 1, Juara 2, Harapan 1, Peserta
    kategori = db.Column(db.String(100))  # Tunggal, Regu, Perorangan
    catatan = db.Column(db.Text)
    tanggal_dapat = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    siswa = db.relationship('Siswa', backref='prestasi_list')
    lomba = db.relationship('Lomba', backref='prestasi_list')

    @property
    def juara_angka(self):
        import re
        if not self.juara:
            return 999
        match = re.search(r'(\d+)', self.juara)
        return int(match.group(1)) if match else 999

    @property
    def juara_color(self):
        if not self.juara:
            return 'secondary'
        j = self.juara.lower()
        if 'juara 1' in j or '1' == j.strip():
            return 'warning'
        elif 'juara 2' in j:
            return 'secondary'
        elif 'juara 3' in j:
            return 'info'
        elif 'harapan' in j:
            return 'primary'
        else:
            return 'light'


class ImportLog(db.Model):
    __tablename__ = 'import_log'
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(200))
    total_rows = db.Column(db.Integer)
    success_count = db.Column(db.Integer)
    error_count = db.Column(db.Integer)
    errors_json = db.Column(db.Text)
    imported_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class AssessmentSection(db.Model):
    __tablename__ = 'assessment_sections'
    id = db.Column(db.Integer, primary_key=True)
    kode = db.Column(db.String(5), nullable=False)  # B, C, F, G, H, I
    nama = db.Column(db.String(100), nullable=False)  # AKTIVITAS FISIK, KOMUNIKASI, etc
    items = db.relationship('AssessmentItem', backref='section', lazy=True, order_by='AssessmentItem.kode')

class AssessmentItem(db.Model):
    __tablename__ = 'assessment_items'
    id = db.Column(db.Integer, primary_key=True)
    section_id = db.Column(db.Integer, db.ForeignKey('assessment_sections.id'), nullable=False)
    kode = db.Column(db.String(10), nullable=False)  # B.1, B.2, etc
    nama = db.Column(db.String(100), nullable=False)  # Duduk tegap, Jalan lurus, etc
    panduan = db.Column(db.Text)  # Panduan observasi guru
    alat_bantu = db.Column(db.String(200))  # Alat yang dibutuhkan

class AssessmentResult(db.Model):
    __tablename__ = 'assessment_results'
    id = db.Column(db.Integer, primary_key=True)
    siswa_id = db.Column(db.Integer, db.ForeignKey('siswa.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('assessment_items.id'), nullable=False)
    tahun_ajaran_id = db.Column(db.Integer, db.ForeignKey('tahun_ajaran.id'), nullable=True)
    nilai = db.Column(db.String(5))  # ✔ or ✘
    catatan = db.Column(db.Text)
    assessor_id = db.Column(db.Integer, db.ForeignKey('guru.id'), nullable=True)
    tanggal = db.Column(db.Date, default=date.today)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    siswa = db.relationship('Siswa', backref='assessments')
    item = db.relationship('AssessmentItem', backref='results')
    assessor = db.relationship('Guru', backref='assessments')
    
    __table_args__ = (
        db.UniqueConstraint('siswa_id', 'item_id', 'tahun_ajaran_id', name='unique_assessment'),
    )

class AssessmentOrtu(db.Model):
    __tablename__ = 'assessment_ortu'
    id = db.Column(db.Integer, primary_key=True)
    siswa_id = db.Column(db.Integer, db.ForeignKey('siswa.id'), nullable=False)
    tahun_ajaran_id = db.Column(db.Integer, db.ForeignKey('tahun_ajaran.id'), nullable=True)
    data_json = db.Column(db.Text)  # JSON blob storing all form data
    assessor_id = db.Column(db.Integer, db.ForeignKey('guru.id'), nullable=True)
    tanggal = db.Column(db.Date, default=date.today)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    siswa = db.relationship('Siswa', backref='assessment_ortu_list')
    
    __table_args__ = (
        db.UniqueConstraint('siswa_id', 'tahun_ajaran_id', name='unique_assessment_ortu'),
    )
class MataPelajaran(db.Model):
    __tablename__ = 'mata_pelajaran'
    id = db.Column(db.Integer, primary_key=True)
    nama = db.Column(db.String(100), nullable=False)
    kode = db.Column(db.String(10), nullable=False, unique=True)
    deskripsi = db.Column(db.Text)
    tipe = db.Column(db.String(20), default='utama')  # 'utama' or 'pendamping'
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def rata_rata_rapor(self, siswa_id=None, tahun_ajaran_id=None, semester=None):
        """Calculate average grade for a student in this subject."""
        query = NilaiPelajaran.query.filter_by(mata_pelajaran_id=self.id, siswa_id=siswa_id)
        if tahun_ajaran_id:
            query = query.filter_by(tahun_ajaran_id=tahun_ajaran_id)
        if semester:
            query = query.filter_by(semester=semester)
        n = query.first()
        if not n:
            return None
        return n.rata_rata


class NilaiPelajaran(db.Model):
    __tablename__ = 'nilai_pelajaran'
    id = db.Column(db.Integer, primary_key=True)
    siswa_id = db.Column(db.Integer, db.ForeignKey('siswa.id'), nullable=False)
    mata_pelajaran_id = db.Column(db.Integer, db.ForeignKey('mata_pelajaran.id'), nullable=False)
    tahun_ajaran_id = db.Column(db.Integer, db.ForeignKey('tahun_ajaran.id'), nullable=True)
    semester = db.Column(db.Integer, default=1)
    uh_1 = db.Column(db.Float)
    uh_2 = db.Column(db.Float)
    uh_3 = db.Column(db.Float)
    uh_4 = db.Column(db.Float)
    uts = db.Column(db.Float)
    uas = db.Column(db.Float)
    tugas_1 = db.Column(db.Float)
    tugas_2 = db.Column(db.Float)
    tugas_3 = db.Column(db.Float)
    catatan = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    siswa = db.relationship('Siswa', backref='nilai_pelajaran_list')
    mata_pelajaran = db.relationship('MataPelajaran', backref='nilai_list')
    tahun_ajaran = db.relationship('TahunAjaran', backref='nilai_pelajaran')

    __table_args__ = (
        db.UniqueConstraint('siswa_id', 'mata_pelajaran_id', 'tahun_ajaran_id', 'semester', name='unique_nilai'),
    )

    @property
    def rata_rata(self):
        """Calculate average of all valid grades."""
        nilai_list = [self.uh_1, self.uh_2, self.uh_3, self.uh_4,
                      self.uts, self.uas, self.tugas_1, self.tugas_2, self.tugas_3]
        valid = [n for n in nilai_list if n is not None and n >= 0]
        if not valid:
            return None
        return round(sum(valid) / len(valid), 1)

    @property
    def nilai_harian(self):
        """Average of UH and Tugas."""
        nilai_list = [self.uh_1, self.uh_2, self.uh_3, self.uh_4,
                      self.tugas_1, self.tugas_2, self.tugas_3]
        valid = [n for n in nilai_list if n is not None and n >= 0]
        if not valid:
            return None
        return round(sum(valid) / len(valid), 1)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
