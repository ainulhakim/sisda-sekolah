import json
from flask import render_template
from flask_login import login_required
from app.routes import routes_bp
from app.models import (
    Siswa, AssessmentSection, AssessmentItem,
    AssessmentResult, AssessmentOrtu, TahunAjaran
)


# ── Domain mapping: teacher sections → domain ──────────────────────────
TEACHER_DOMAIN_MAP = {
    'Fisik':    ['B'],
    'Bahasa':   ['C', 'D'],
    'Agama':    ['E'],
    'Kognitif': ['F'],
    'STEAM':    ['G'],
    'Sosial':   ['H'],
    'Karakter': ['I'],
}

# ── Ortu JSON field → domain mapping ───────────────────────────────────
ORTU_FIELD_MAP = {
    'Fisik':    ['persepsi_motorhalus', 'persepsi_motorkasar'],
    'Kognitif': ['persepsi_konsentrasi', 'persepsi_ingat', 'persepsi_problem',
                 'akademik_huruf', 'akademik_baca', 'akademik_hitung'],
    'Bahasa':   ['persepsi_keberanian', 'persepsi_instruksi',
                 'akademik_cerita', 'akademik_english'],
    'Sosial':   ['persepsi_kerjasama', 'persepsi_empati', 'persepsi_leader'],
    'Agama':    ['akademik_mengaji', 'akademik_quran'],
    'Karakter': ['persepsi_disiplin', 'persepsi_mandiri'],
    'STEAM':    ['persepsi_kreatif', 'persepsi_tahu'],
}

DOMAIN_EMOJI = {
    'Fisik': '🏃', 'Kognitif': '🧠', 'Bahasa': '💬',
    'Sosial': '🤝', 'Agama': '🕌', 'Karakter': '⭐', 'STEAM': '🔬',
}

DOMAIN_ORDER = ['Fisik', 'Kognitif', 'Bahasa', 'Sosial', 'Agama', 'Karakter', 'STEAM']


def _compute_teacher_score(siswa_id, section_kodes):
    """Return (tercapai, total, pct, item_details) for given section codes."""
    items = (
        AssessmentItem.query
        .join(AssessmentSection, AssessmentItem.section_id == AssessmentSection.id)
        .filter(AssessmentSection.kode.in_(section_kodes))
        .order_by(AssessmentItem.kode)
        .all()
    )
    results = AssessmentResult.query.filter_by(siswa_id=siswa_id).all()
    result_map = {r.item_id: r for r in results}

    total = len(items)
    tercapai = 0
    details = []
    for item in items:
        r = result_map.get(item.id)
        if r and r.nilai == '✔':
            status = '✔'
            tercapai += 1
        elif r and r.nilai == '✘':
            status = '✘'
        else:
            status = '-'
        details.append({
            'kode': item.kode,
            'nama': item.nama,
            'status': status,
        })

    pct = round((tercapai / total) * 100, 1) if total > 0 else 0.0
    return tercapai, total, pct, details


def _compute_ortu_rating(ortu_data, field_names):
    """Return (avg_rating, field_details) from ortu JSON data.

    avg_rating is on 1-5 scale. field_details is a list of
    {'field': str, 'label': str, 'value': int|None}.
    """
    LABELS = {
        'persepsi_motorhalus': 'Motorik Halus',
        'persepsi_motorkasar': 'Motorik Kasar',
        'persepsi_konsentrasi': 'Konsentrasi',
        'persepsi_ingat': 'Daya Ingat',
        'persepsi_problem': 'Problem Solving',
        'akademik_huruf': 'Mengenal Huruf',
        'akademik_baca': 'Membaca',
        'akademik_hitung': 'Menghitung',
        'persepsi_keberanian': 'Keberanian Bicara',
        'persepsi_instruksi': 'Mengikuti Instruksi',
        'akademik_cerita': 'Bercerita',
        'akademik_english': 'English',
        'persepsi_kerjasama': 'Kerjasama',
        'persepsi_empati': 'Empati',
        'persepsi_leader': 'Kepemimpinan',
        'akademik_mengaji': 'Mengaji',
        'akademik_quran': 'Hafalan Quran',
        'persepsi_disiplin': 'Disiplin',
        'persepsi_mandiri': 'Mandiri',
        'persepsi_kreatif': 'Kreativitas',
        'persepsi_tahu': 'Pengetahuan',
    }

    details = []
    values = []
    for f in field_names:
        raw = ortu_data.get(f)
        try:
            val = int(raw) if raw is not None and str(raw).strip() != '' else None
        except (ValueError, TypeError):
            val = None
        details.append({
            'field': f,
            'label': LABELS.get(f, f),
            'value': val,
        })
        if val is not None:
            values.append(val)

    avg = round(sum(values) / len(values), 2) if values else None
    return avg, details


def _gap_status(gap):
    """Return (status_text, color_class) based on absolute gap."""
    abs_g = abs(gap)
    if abs_g <= 15:
        return 'Sejalan', 'success'
    elif abs_g <= 30:
        return 'Moderat', 'warning'
    else:
        return 'Signifikan', 'danger'


def _generate_insight(domain, gap, guru_pct, ortu_pct):
    """Auto-generated insight text per domain."""
    if ortu_pct is None and guru_pct > 0:
        return f"ℹ️ Belum ada data persepsi orang tua untuk domain {domain}. Guru mengamati skor {guru_pct}%."
    if guru_pct == 0 and ortu_pct is not None:
        return f"⚠️ Belum ada data observasi guru untuk domain {domain}. Persepsi orang tua: {ortu_pct}%."
    if guru_pct == 0 and ortu_pct is None:
        return f"📭 Belum ada data assessment untuk domain {domain} dari guru maupun orang tua."

    if gap > 30:
        return (f"⚠️ Orang tua menilai <strong>{domain}</strong> lebih tinggi "
                f"({ortu_pct}%) dari observasi guru ({guru_pct}%). "
                f"Diskusi diperlukan.")
    elif gap < -30:
        return (f"ℹ️ Guru mengamati <strong>{domain}</strong> lebih baik "
                f"({guru_pct}%) dari persepsi orang tua ({ortu_pct}%). "
                f"Orang tua perlu informasi lebih.")
    else:
        return (f"✅ Persepsi orang tua ({ortu_pct}%) dan "
                f"observasi guru ({guru_pct}%) sejalan untuk <strong>{domain}</strong>.")


# ── Route ──────────────────────────────────────────────────────────────
@routes_bp.route('/siswa/<int:id>/gap-analysis')
@login_required
def gap_analysis(id):
    siswa = Siswa.query.get_or_404(id)
    ta = TahunAjaran.query.filter_by(is_active=True).first()

    # Load ortu data
    ortu_record = AssessmentOrtu.query.filter_by(
        siswa_id=id,
        tahun_ajaran_id=ta.id if ta else None
    ).first()
    ortu_data = {}
    if ortu_record and ortu_record.data_json:
        try:
            ortu_data = json.loads(ortu_record.data_json)
        except (json.JSONDecodeError, TypeError):
            ortu_data = {}

    has_ortu_data = bool(ortu_data)

    # Build domain comparison data
    domains = []
    aligned_count = 0
    moderate_count = 0
    significant_count = 0

    for domain_name in DOMAIN_ORDER:
        section_kodes = TEACHER_DOMAIN_MAP[domain_name]
        ortu_fields = ORTU_FIELD_MAP[domain_name]

        tercapai, total, guru_pct, guru_items = _compute_teacher_score(id, section_kodes)
        ortu_avg, ortu_details = _compute_ortu_rating(ortu_data, ortu_fields)

        ortu_pct = round((ortu_avg / 5) * 100, 1) if ortu_avg is not None else None

        if guru_pct is not None and ortu_pct is not None:
            gap = round(ortu_pct - guru_pct, 1)
        else:
            gap = None

        status_text, status_color = _gap_status(gap) if gap is not None else ('N/A', 'secondary')

        insight = _generate_insight(domain_name, gap or 0, guru_pct, ortu_pct or 0)

        if gap is not None:
            if abs(gap) <= 15:
                aligned_count += 1
            elif abs(gap) <= 30:
                moderate_count += 1
            else:
                significant_count += 1

        domains.append({
            'name': domain_name,
            'emoji': DOMAIN_EMOJI[domain_name],
            'guru_pct': guru_pct,
            'ortu_pct': ortu_pct,
            'guru_tercapai': tercapai,
            'guru_total': total,
            'gap': gap,
            'status_text': status_text,
            'status_color': status_color,
            'guru_items': guru_items,
            'ortu_details': ortu_details,
            'insight': insight,
            'has_guru': total > 0 and any(i['status'] != '-' for i in guru_items),
            'has_ortu': ortu_pct is not None,
        })

    # Data for chart.js
    chart_labels = [d['name'] for d in domains]
    chart_guru = [d['guru_pct'] if d['guru_pct'] is not None else 0 for d in domains]
    chart_ortu = [d['ortu_pct'] if d['ortu_pct'] is not None else 0 for d in domains]

    has_any_data = any(d['has_guru'] or d['has_ortu'] for d in domains)

    return render_template(
        'siswa/gap_analysis.html',
        siswa=siswa,
        domains=domains,
        aligned_count=aligned_count,
        moderate_count=moderate_count,
        significant_count=significant_count,
        has_ortu_data=has_ortu_data,
        has_any_data=has_any_data,
        chart_labels=chart_labels,
        chart_guru=chart_guru,
        chart_ortu=chart_ortu,
    )
