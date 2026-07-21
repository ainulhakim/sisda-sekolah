"""Add missing assessment items to the SiSD database.

- Section C: Add C.7, C.8
- Section D: Create English Assessment (13 items)
- Section E: Create Quran & Diniyah (10 items)
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app, db
from app.models import AssessmentSection, AssessmentItem

app = create_app()

with app.app_context():
    # ── 1. Add missing items to Section C (KOMUNIKASI) ──────────────────────
    section_c = AssessmentSection.query.filter_by(kode='C').first()
    if section_c:
        existing_kodes = {item.kode for item in section_c.items}
        new_c_items = [
            ('C.7', 'Kejelasan berbicara',
             'Dengarkan pengucapan anak saat menjawab. Amati artikulasi, volume, dan ritme bicara.',
             'Tanpa alat (observasi verbal)'),
            ('C.8', 'Mengikuti instruksi',
             'Berikan instruksi 2 langkah: Ambil pensil, lalu taruh di atas buku. Amati kemampuan mengikuti.',
             'Pensil + buku (objek instruksi)'),
        ]
        added_c = 0
        for kode, nama, panduan, alat in new_c_items:
            if kode not in existing_kodes:
                item = AssessmentItem(
                    section_id=section_c.id,
                    kode=kode, nama=nama, panduan=panduan, alat_bantu=alat
                )
                db.session.add(item)
                added_c += 1
        db.session.commit()
        print(f"✅ Section C: added {added_c} items ({', '.join(i[0] for i in new_c_items if i[0] not in existing_kodes)})")
    else:
        print("❌ Section C not found!")

    # ── 2. Create Section D: ENGLISH ASSESSMENT ─────────────────────────────
    section_d = AssessmentSection.query.filter_by(kode='D').first()
    if section_d:
        print("⚠️  Section D already exists, skipping creation.")
    else:
        section_d = AssessmentSection(kode='D', nama='ENGLISH ASSESSMENT')
        db.session.add(section_d)
        db.session.flush()

        d_items = [
            ('D.1', 'Greeting',
             'Sapa anak: Good morning!. Amati respons: apakah bisa menjawab dengan benar?',
             'Flashcard sapaan (Good morning/afternoon/evening)'),
            ('D.2', 'Self Introduction',
             'Minta: Tell me your name. Amati kemampuan memperkenalkan diri dalam bahasa Inggris.',
             'Kartu perkenalan / name tag'),
            ('D.3', 'Colors',
             'Tunjukkan warna, tanyakan: What color is this?. Amati pengenalan minimal 3 warna.',
             'Flashcard warna / kertas warna / crayon'),
            ('D.4', 'Shapes',
             'Tunjukkan bentuk: What shape is this?. Amati pengenalan bentuk dasar.',
             'Flashcard bentuk / puzzle bentuk / balok'),
            ('D.5', 'Numbers',
             'Tanyakan: Can you count to 10?. Amati kemampuan berhitung 1-10 dalam bahasa Inggris.',
             'Flashcard angka / kartu angka 1-10'),
            ('D.6', 'Alphabet',
             'Tunjukkan huruf: Show me letter A. Amati pengenalan huruf alfabet.',
             'Flashcard alfabet / poster alfabet'),
            ('D.7', 'Body Parts',
             'Tunjuk bagian tubuh: Where is your nose?. Amati pemahaman kosakata tubuh.',
             'Poster tubuh / boneka / lagu Head Shoulders'),
            ('D.8', 'Listening',
             'Putar lagu/perintah sederhana bahasa Inggris. Amati kemampuan memahami instruksi.',
             'Audio player + lagu anak Inggris'),
            ('D.9', 'Speaking',
             'Minta anak menirukan kata/kalimat sederhana. Amati kemampuan menirukan.',
             'Flashcard kosakata / gambar'),
            ('D.10', 'Pronunciation',
             'Amati pengucapan anak saat berbicara bahasa Inggris.',
             'Tanpa alat (observasi verbal)'),
            ('D.11', 'Confidence',
             'Amati keyakinan diri anak saat berbicara Inggris. Berani atau ragu-ragu?',
             'Tanpa alat (observasi perilaku)'),
            ('D.12', 'Participation',
             'Amati keterlibatan anak saat aktivitas bahasa Inggris. Aktif atau pasif?',
             'Tanpa alat (observasi perilaku)'),
            ('D.13', 'Attitude',
             'Amati sikap anak selama assessment English: antusias, malas, atau tidak mau melibatkan diri.',
             'Tanpa alat (observasi perilaku)'),
        ]
        for kode, nama, panduan, alat in d_items:
            item = AssessmentItem(
                section_id=section_d.id,
                kode=kode, nama=nama, panduan=panduan, alat_bantu=alat
            )
            db.session.add(item)
        db.session.commit()
        print(f"✅ Section D (ENGLISH ASSESSMENT): created with {len(d_items)} items")

    # ── 3. Create Section E: QURAN & DINIYAH ───────────────────────────────
    section_e = AssessmentSection.query.filter_by(kode='E').first()
    if section_e:
        print("⚠️  Section E already exists, skipping creation.")
    else:
        section_e = AssessmentSection(kode='E', nama='QURAN & DINIYAH')
        db.session.add(section_e)
        db.session.flush()

        e_items = [
            ('E.1', 'Huruf Hijaiyah',
             'Tunjukkan huruf hijaiyah satu per satu. Amati kemampuan mengenal minimal Alif-Ba-Ta-Sa.',
             'Flashcard hijaiyah / Iqro Jilid 1'),
            ('E.2', 'Makharij',
             'Minta anak membaca huruf. Amati tempat keluar huruf yang benar.',
             'Iqro / poster makharijul huruf'),
            ('E.3', 'Harakat',
             'Tunjukkan huruf dengan fathah, kasrah, dhommah. Amati pengenalan.',
             'Iqro / kartu huruf harakat'),
            ('E.4', 'Tanwin',
             'Tunjukkan huruf dengan tanwin. Amati pemahaman.',
             'Iqro / kartu tanwin'),
            ('E.5', 'Membaca',
             'Minta anak membaca surat pendek (Al-Fatihah / An-Nas). Amati kelancaran.',
             'Iqro / Al Quran kecil'),
            ('E.6', 'Surat Pendek',
             'Tanyakan: Sudah hafal surat apa?. Minta membaca surat yang dikuasai.',
             'Juz Amma / Al Quran kecil'),
            ('E.7', 'Doa',
             'Tanyakan doa sehari-hari. Amati hafalan doa.',
             'Buku doa anak / kartu doa harian'),
            ('E.8', 'Adab',
             'Amati perilaku anak: mengucap salam, tata cara duduk, sopan santun.',
             'Tanpa alat (observasi langsung)'),
            ('E.9', 'Wudhu',
             'Minta anak mendemonstrasikan urutan wudhu. Amati ketepatan urutan.',
             'Tempat wudhu / air + baskom kecil'),
            ('E.10', 'Shalat',
             'Minta anak menunjukkan gerakan shalat. Amati urutan dan ketepatan.',
             'Sajadah / mukena kecil'),
        ]
        for kode, nama, panduan, alat in e_items:
            item = AssessmentItem(
                section_id=section_e.id,
                kode=kode, nama=nama, panduan=panduan, alat_bantu=alat
            )
            db.session.add(item)
        db.session.commit()
        print(f"✅ Section E (QURAN & DINIYAH): created with {len(e_items)} items")

    # ── 4. Verify final counts ─────────────────────────────────────────────
    print("\n📊 Assessment Sections Summary:")
    print("-" * 50)
    total_items = 0
    for section in AssessmentSection.query.order_by(AssessmentSection.kode).all():
        count = len(section.items)
        total_items += count
        print(f"  {section.kode}: {section.nama:30s} — {count} items")
    print("-" * 50)
    print(f"  TOTAL: {total_items} items across {AssessmentSection.query.count()} sections")
