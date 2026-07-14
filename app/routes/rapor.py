from app.timezone import now_wib
"""
Rapor PDF generator for SISDA Sekolah.
Generates a downloadable PDF report card for each student.
"""
import io
import math
from datetime import datetime

from flask import send_file
from flask_login import login_required
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
    HRFlowable, KeepTogether
)
from reportlab.graphics.shapes import Drawing, String, Line, Polygon, Group
from reportlab.graphics.charts.legends import Legend

from app.routes import routes_bp
from app.models import (
    Siswa, Absensi, NilaiPelajaran, MataPelajaran,
    TahunAjaran, SiswaBadge, AssessmentSection, AssessmentItem, AssessmentResult,
    get_sekolah_config
)
from app.routes.kemampuan_dasar import compute_domain_data, DOMAIN_MAP

# Colors
BLUE_PRIMARY = colors.HexColor('#3498db')
BLUE_DARK = colors.HexColor('#2c3e50')
BLUE_LIGHT = colors.HexColor('#eaf2f8')
GREEN = colors.HexColor('#27ae60')
GREEN_LIGHT = colors.HexColor('#eafaf1')
RED = colors.HexColor('#e74c3c')
RED_LIGHT = colors.HexColor('#fdedec')
ORANGE = colors.HexColor('#f39c12')
GRAY = colors.HexColor('#95a5a6')
GRAY_LIGHT = colors.HexColor('#ecf0f1')
GRAY_DARK = colors.HexColor('#7f8c8d')
WHITE = colors.white


def _fmt(val):
    """Format a numeric value or return dash."""
    if val is None:
        return '-'
    return str(val)


def _safe_str(val, default='-'):
    """Return default if val is None or the string 'None'."""
    if val is None:
        return default
    s = str(val).strip()
    if not s or s.lower() == 'none':
        return default
    return s


def _grade_color(val):
    """Return color based on grade value."""
    if val is None:
        return GRAY_DARK
    if val >= 80:
        return GREEN
    if val >= 60:
        return ORANGE
    return RED


def _build_header(styles, sekolah=None):
    """Build the PDF header section."""
    elements = []
    
    # School name
    school_name = sekolah.nama_sekolah if sekolah and sekolah.nama_sekolah else 'SANTREN KODING'
    elements.append(Paragraph(school_name, styles['SchoolName']))
    # School address/contact if available
    if sekolah:
        addr_parts = []
        if sekolah.alamat:
            addr_parts.append(sekolah.alamat)
        if sekolah.no_telepon:
            addr_parts.append(f'Telp: {sekolah.no_telepon}')
        if sekolah.email:
            addr_parts.append(f'Email: {sekolah.email}')
        if sekolah.website:
            addr_parts.append(sekolah.website)
        if addr_parts:
            addr_style = ParagraphStyle('SchoolAddr', parent=styles['Normal'],
                                        fontSize=8, textColor=GRAY_DARK,
                                        alignment=TA_CENTER, spaceAfter=1*mm)
            elements.append(Paragraph(' | '.join(addr_parts), addr_style))
    elements.append(Spacer(1, 2 * mm))
    elements.append(Paragraph('RAPOR PENILAIAN', styles['ReportTitle']))
    elements.append(Spacer(1, 4 * mm))
    elements.append(HRFlowable(width='100%', thickness=2, color=BLUE_PRIMARY))
    elements.append(Spacer(1, 4 * mm))
    
    return elements


def _build_student_info(siswa, styles):
    """Build the student information section."""
    elements = []
    elements.append(Paragraph('DATA SISWA', styles['SectionTitle']))
    elements.append(Spacer(1, 2 * mm))
    
    kelas_name = siswa.kelas.nama_kelas if siswa.kelas else '-'
    ortu_name = _safe_str(siswa.nama_ortu)
    nisn = _safe_str(siswa.nisn)
    ttl = '-'
    if siswa.tanggal_lahir:
        ttl = f"{_safe_str(siswa.tempat_lahir)}, {siswa.tanggal_lahir.strftime('%d %B %Y')}"
    
    data = [
        ['Nama Lengkap', ':', _safe_str(siswa.nama_lengkap)],
        ['NISN', ':', nisn],
        ['Kelas', ':', kelas_name],
        ['Jenis Kelamin', ':', 'Laki-laki' if siswa.jenis_kelamin == 'L' else 'Perempuan'],
        ['Tanggal Lahir', ':', ttl],
        ['Nama Orang Tua', ':', ortu_name],
    ]
    
    t = Table(data, colWidths=[35*mm, 5*mm, 120*mm])
    t.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (0, 0), (0, -1), BLUE_DARK),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 6 * mm))
    
    return elements


def _build_attendance(siswa, ta, semester, styles):
    """Build attendance summary section."""
    elements = []
    elements.append(Paragraph('RINGKASAN ABSENSI', styles['SectionTitle']))
    elements.append(Spacer(1, 2 * mm))
    
    # Query attendance for this student in current TA/semester
    query = Absensi.query.filter_by(siswa_id=siswa.id)
    if ta:
        # Filter by dates within the academic year - approximate by TA name
        pass  # Absensi doesn't have tahun_ajaran_id, use all
    
    all_absensi = query.all()
    
    total = len(all_absensi)
    hadir = sum(1 for a in all_absensi if a.status == 'hadir')
    izin = sum(1 for a in all_absensi if a.status == 'izin')
    sakit = sum(1 for a in all_absensi if a.status == 'sakit')
    alpa = sum(1 for a in all_absensi if a.status == 'alpa')
    persen = round((hadir / total * 100), 1) if total > 0 else 0.0
    
    data = [
        ['Kategori', 'Jumlah Hari', 'Persentase'],
        ['Total Hari', str(total), '-'],
        ['Hadir', str(hadir), f'{persen}%'],
        ['Izin', str(izin), '-'],
        ['Sakit', str(sakit), '-'],
        ['Alpa', str(alpa), '-'],
    ]
    
    t = Table(data, colWidths=[50*mm, 50*mm, 50*mm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), BLUE_PRIMARY),
        ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('BACKGROUND', (0, 1), (-1, 1), BLUE_LIGHT),
        ('GRID', (0, 0), (-1, -1), 0.5, GRAY),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 6 * mm))
    
    return elements


def _build_grades(siswa, ta, semester, styles):
    """Build grades table section."""
    elements = []
    elements.append(Paragraph('NILAI PELAJARAN', styles['SectionTitle']))
    elements.append(Spacer(1, 2 * mm))
    
    # Query grades
    query = NilaiPelajaran.query.filter_by(siswa_id=siswa.id)
    if ta:
        query = query.filter_by(tahun_ajaran_id=ta.id)
    if semester:
        query = query.filter_by(semester=semester)
    
    grades = query.all()
    
    if not grades:
        elements.append(Paragraph('<i>Belum ada data nilai.</i>', styles['Italic']))
        elements.append(Spacer(1, 6 * mm))
        return elements
    
    # Header row
    header = ['No', 'Mata Pelajaran', 'UH1', 'UH2', 'UH3', 'UH4', 'Tgs1', 'Tgs2', 'Tgs3', 'UTS', 'UAS', 'Rata-rata']
    data = [header]
    
    for idx, g in enumerate(grades, 1):
        matpel = g.mata_pelajaran.nama if g.mata_pelajaran else '-'
        rr = g.rata_rata
        data.append([
            str(idx),
            matpel,
            _fmt(g.uh_1), _fmt(g.uh_2), _fmt(g.uh_3), _fmt(g.uh_4),
            _fmt(g.tugas_1), _fmt(g.tugas_2), _fmt(g.tugas_3),
            _fmt(g.uts), _fmt(g.uas),
            _fmt(rr)
        ])
    
    col_widths = [8*mm, 35*mm] + [11*mm]*9 + [14*mm]
    t = Table(data, colWidths=col_widths)
    
    style_commands = [
        ('BACKGROUND', (0, 0), (-1, 0), BLUE_PRIMARY),
        ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 6.5),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 6.5),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (1, 1), (1, -1), 'LEFT'),
        ('GRID', (0, 0), (-1, -1), 0.5, GRAY),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
    ]
    
    # Color-code rows
    for idx, g in enumerate(grades, 1):
        rr = g.rata_rata
        if rr is not None:
            if rr >= 80:
                style_commands.append(('BACKGROUND', (0, idx), (-1, idx), GREEN_LIGHT))
            elif rr >= 60:
                style_commands.append(('BACKGROUND', (0, idx), (-1, idx), colors.HexColor('#fef9e7')))
            else:
                style_commands.append(('BACKGROUND', (0, idx), (-1, idx), RED_LIGHT))
        else:
            if idx % 2 == 0:
                style_commands.append(('BACKGROUND', (0, idx), (-1, idx), GRAY_LIGHT))
    
    t.setStyle(TableStyle(style_commands))
    elements.append(t)
    elements.append(Spacer(1, 6 * mm))
    
    return elements


def _draw_radar_chart(domain_data, width=200, height=200):
    """Draw a radar chart for the 6 domains."""
    domains = list(domain_data.keys())
    n = len(domains)
    if n == 0:
        return None
    
    # Center and radius
    cx, cy = width / 2, height / 2
    radius = min(width, height) / 2 - 20
    
    d = Drawing(width, height)
    
    # Draw concentric pentagons (grid)
    for level in [0.2, 0.4, 0.6, 0.8, 1.0]:
        points = []
        for i in range(n):
            angle = math.radians(90 + i * (360 / n))
            x = cx + radius * level * math.cos(angle)
            y = cy + radius * level * math.sin(angle)
            points.extend([x, y])
        points.extend(points[:2])  # close the shape
        d.add(Polygon(points, fillColor=None, strokeColor=GRAY, strokeWidth=0.5))
    
    # Draw axis lines
    for i in range(n):
        angle = math.radians(90 + i * (360 / n))
        x = cx + radius * math.cos(angle)
        y = cy + radius * math.sin(angle)
        d.add(Line(cx, cy, x, y, strokeColor=GRAY, strokeWidth=0.5))
    
    # Draw labels
    for i, domain in enumerate(domains):
        angle = math.radians(90 + i * (360 / n))
        lx = cx + (radius + 15) * math.cos(angle)
        ly = cy + (radius + 15) * math.sin(angle)
        anchor = 'middle'
        if lx < cx - 5:
            anchor = 'end'
        elif lx > cx + 5:
            anchor = 'start'
        d.add(String(lx, ly, domain, fontSize=7, textAnchor=anchor, fillColor=BLUE_DARK))
    
    # Draw data polygon
    data_points = []
    for i, domain in enumerate(domains):
        pct = domain_data[domain]['pct'] / 100.0
        angle = math.radians(90 + i * (360 / n))
        x = cx + radius * pct * math.cos(angle)
        y = cy + radius * pct * math.sin(angle)
        data_points.extend([x, y])
    data_points.extend(data_points[:2])  # close
    
    d.add(Polygon(data_points, fillColor=colors.HexColor('#3498db44'), strokeColor=BLUE_PRIMARY, strokeWidth=2))
    
    # Draw data points
    for i, domain in enumerate(domains):
        pct = domain_data[domain]['pct'] / 100.0
        angle = math.radians(90 + i * (360 / n))
        x = cx + radius * pct * math.cos(angle)
        y = cy + radius * pct * math.sin(angle)
        d.add(Polygon([x-3, y-3, x+3, y+3, x, y+5], fillColor=BLUE_PRIMARY, strokeColor=WHITE, strokeWidth=1))
    
    return d


def _build_kemampuan_dasar(siswa, styles):
    """Build kemampuan dasar (radar chart + table) section."""
    elements = []
    elements.append(Paragraph('KEMAMPUAN DASAR', styles['SectionTitle']))
    elements.append(Spacer(1, 2 * mm))
    
    domain_data = compute_domain_data(siswa.id)
    
    # Check if any data exists
    has_data = any(d['tercapai'] > 0 for d in domain_data.values())
    
    if not has_data:
        elements.append(Paragraph('<i>Belum ada data assessment.</i>', styles['Italic']))
        elements.append(Spacer(1, 6 * mm))
        return elements
    
    # Radar chart
    radar = _draw_radar_chart(domain_data, width=220, height=220)
    if radar:
        elements.append(radar)
        elements.append(Spacer(1, 4 * mm))
    
    # Domain table
    header = ['Domain', 'Jumlah Item', 'Skor (Tercapai)', 'Persentase']
    data = [header]
    for domain_name, info in domain_data.items():
        data.append([
            domain_name,
            str(info['total']),
            f"{info['tercapai']} / {info['total']}",
            f"{info['pct']}%"
        ])
    
    # Add overall
    total_tercapai = sum(d['tercapai'] for d in domain_data.values())
    total_items = sum(d['total'] for d in domain_data.values())
    overall_pct = round((total_tercapai / total_items * 100), 1) if total_items > 0 else 0.0
    data.append(['TOTAL', str(total_items), f'{total_tercapai} / {total_items}', f'{overall_pct}%'])
    
    t = Table(data, colWidths=[35*mm, 30*mm, 35*mm, 30*mm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), BLUE_PRIMARY),
        ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('FONTNAME', (0, 1), (-1, -2), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -2), 9),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -1), (-1, -1), 9),
        ('BACKGROUND', (0, -1), (-1, -1), BLUE_LIGHT),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, GRAY),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 6 * mm))
    
    return elements


def _build_assessment_guru(siswa, styles):
    """Build assessment guru summary section."""
    elements = []
    elements.append(Paragraph('ASSESSMENT GURU', styles['SectionTitle']))
    elements.append(Spacer(1, 2 * mm))
    
    # Get all sections
    sections = AssessmentSection.query.all()
    
    if not sections:
        elements.append(Paragraph('<i>Belum ada data assessment.</i>', styles['Italic']))
        elements.append(Spacer(1, 6 * mm))
        return elements
    
    header = ['Bagian', 'Nama Bagian', 'Tercapai', 'Total', 'Persentase']
    data = [header]
    
    for section in sections:
        items = AssessmentItem.query.filter_by(section_id=section.id).all()
        total = len(items)
        
        tercapai = 0
        for item in items:
            result = AssessmentResult.query.filter_by(siswa_id=siswa.id, item_id=item.id).first()
            if result and result.nilai == '✔':
                tercapai += 1
        
        pct = round((tercapai / total * 100), 1) if total > 0 else 0.0
        data.append([section.kode, section.nama, str(tercapai), str(total), f'{pct}%'])
    
    t = Table(data, colWidths=[15*mm, 50*mm, 25*mm, 20*mm, 25*mm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), BLUE_PRIMARY),
        ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('ALIGN', (2, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, GRAY),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 6 * mm))
    
    return elements


def _build_badges(siswa, styles):
    """Build badges section."""
    elements = []
    elements.append(Paragraph('BADGE YANG DIRAIH', styles['SectionTitle']))
    elements.append(Spacer(1, 2 * mm))
    
    badges = SiswaBadge.query.filter_by(siswa_id=siswa.id).all()
    
    if not badges:
        elements.append(Paragraph('<i>Belum ada badge yang diraih.</i>', styles['Italic']))
        elements.append(Spacer(1, 6 * mm))
        return elements
    
    header = ['No', 'Nama Badge', 'Deskripsi', 'Tanggal Dapat']
    data = [header]
    
    for idx, sb in enumerate(badges, 1):
        badge = sb.badge
        emoji = badge.icon_emoji or ''
        data.append([
            str(idx),
            f'{emoji} {badge.nama}',
            badge.deskripsi or '-',
            sb.tanggal_dapat.strftime('%d/%m/%Y') if sb.tanggal_dapat else '-'
        ])
    
    t = Table(data, colWidths=[10*mm, 35*mm, 75*mm, 30*mm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), BLUE_PRIMARY),
        ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, GRAY),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 6 * mm))
    
    return elements


def _build_footer(styles, sekolah=None):
    """Build the footer with signature and print date."""
    elements = []
    elements.append(Spacer(1, 10 * mm))
    elements.append(HRFlowable(width='100%', thickness=1, color=BLUE_PRIMARY))
    elements.append(Spacer(1, 4 * mm))
    
    now = now_wib()
    date_str = now.strftime('%d %B %Y')
    
    kepala = sekolah.kepala_sekolah if sekolah and sekolah.kepala_sekolah else ''
    nip = sekolah.nip_kepala if sekolah and sekolah.nip_kepala else ''
    
    footer_data = [
        ['Catatan Guru:', '', 'Mengetahui,', '', f'Dicetak: {date_str}'],
        ['', '', '', '', ''],
        ['________________________', '', '________________________', '', ''],
        ['Wali Kelas', '', 'Kepala Sekolah', '', ''],
    ]
    if kepala:
        footer_data.insert(3, ['', '', kepala, '', ''])
    if nip:
        footer_data.insert(4, ['', '', f'NIP. {nip}', '', ''])
    
    t = Table(footer_data, colWidths=[45*mm, 15*mm, 45*mm, 15*mm, 35*mm])
    t.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, 0), 'Helvetica-Bold'),
        ('FONTNAME', (4, 0), (4, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (4, 0), (4, 0), 7),
        ('TEXTCOLOR', (4, 0), (4, 0), GRAY_DARK),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    elements.append(t)
    
    return elements


@routes_bp.route('/siswa/<int:id>/rapor')
@login_required
def cetak_rapor(id):
    """Generate and download PDF rapor for a student."""
    siswa = Siswa.query.get_or_404(id)
    sekolah = get_sekolah_config()
    
    # Get active tahun ajaran
    ta = TahunAjaran.query.filter_by(is_active=True).first()
    semester = ta.semester if ta else 1
    ta_name = ta.nama if ta else '-'
    sem_label = f"Semester {semester}"
    
    # Build styles
    styles = getSampleStyleSheet()
    
    custom_styles = {
        'SchoolName': ParagraphStyle(
            'SchoolName', parent=styles['Title'],
            fontSize=20, textColor=BLUE_PRIMARY,
            alignment=TA_CENTER, spaceAfter=1*mm,
            fontName='Helvetica-Bold'
        ),
        'ReportTitle': ParagraphStyle(
            'ReportTitle', parent=styles['Title'],
            fontSize=14, textColor=BLUE_DARK,
            alignment=TA_CENTER, spaceAfter=1*mm,
            fontName='Helvetica-Bold'
        ),
        'SectionTitle': ParagraphStyle(
            'SectionTitle', parent=styles['Heading2'],
            fontSize=11, textColor=BLUE_PRIMARY,
            fontName='Helvetica-Bold',
            spaceBefore=2*mm, spaceAfter=1*mm,
            borderWidth=0, borderColor=BLUE_PRIMARY,
            borderPadding=0,
        ),
        'Italic': ParagraphStyle(
            'ItalicNote', parent=styles['Normal'],
            fontSize=9, textColor=GRAY_DARK,
            fontName='Helvetica-Oblique',
        ),
    }
    
    # Create PDF
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=15*mm,
        bottomMargin=15*mm,
        leftMargin=15*mm,
        rightMargin=15*mm,
    )
    
    elements = []
    
    # Header
    elements.extend(_build_header(custom_styles, sekolah))
    
    # Semester & TA info
    ta_info = Paragraph(
        f'{sem_label} | Tahun Ajaran {ta_name}',
        ParagraphStyle('TAInfo', parent=styles['Normal'], fontSize=10,
                       alignment=TA_CENTER, textColor=BLUE_DARK, fontName='Helvetica-Bold')
    )
    elements.append(ta_info)
    elements.append(Spacer(1, 6 * mm))
    
    # Student Info
    elements.extend(_build_student_info(siswa, custom_styles))
    
    # Attendance
    elements.extend(_build_attendance(siswa, ta, semester, custom_styles))
    
    # Grades
    elements.extend(_build_grades(siswa, ta, semester, custom_styles))
    
    # Kemampuan Dasar (radar chart + domain table)
    elements.extend(_build_kemampuan_dasar(siswa, custom_styles))
    
    # Assessment Guru
    elements.extend(_build_assessment_guru(siswa, custom_styles))
    
    # Badges
    elements.extend(_build_badges(siswa, custom_styles))
    
    # Footer
    elements.extend(_build_footer(custom_styles, sekolah))
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    
    filename = f'rapor_{siswa.nama_lengkap.replace(" ", "_")}_{ta_name}_s{semester}.pdf'
    
    return send_file(
        buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename
    )
