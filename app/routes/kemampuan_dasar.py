from flask import render_template
from flask_login import login_required
from app.routes import routes_bp
from app.models import Siswa, AssessmentSection, AssessmentItem, AssessmentResult


# Domain mapping: domain name -> list of section kode
DOMAIN_MAP = {
    'Fisik': ['B'],
    'Kognitif': ['F', 'G'],
    'Bahasa': ['C', 'D'],
    'Sosial': ['H'],
    'Agama': ['E'],
    'Karakter': ['I'],
}


def compute_domain_data(siswa_id):
    """Compute percentage per domain for a student.

    Returns dict: { 'Fisik': {'pct': 45.5, 'tercapai': 5, 'total': 11, 'items': [...]}, ... }
    """
    # Fetch all assessment results for this student
    results = AssessmentResult.query.filter_by(siswa_id=siswa_id).all()
    # Build lookup: item_id -> result
    result_map = {r.item_id: r for r in results}

    domain_data = {}

    for domain_name, section_kodes in DOMAIN_MAP.items():
        # Get all items for these sections
        items = (
            AssessmentItem.query
            .join(AssessmentSection, AssessmentItem.section_id == AssessmentSection.id)
            .filter(AssessmentSection.kode.in_(section_kodes))
            .order_by(AssessmentItem.kode)
            .all()
        )

        total = len(items)
        tercapai = 0
        item_details = []

        for item in items:
            result = result_map.get(item.id)
            if result and result.nilai == '✔':
                status = '✔'
                tercapai += 1
            elif result and result.nilai == '✘':
                status = '✘'
            else:
                status = '-'
            item_details.append({
                'kode': item.kode,
                'nama': item.nama,
                'status': status,
            })

        pct = round((tercapai / total) * 100, 1) if total > 0 else 0.0
        domain_data[domain_name] = {
            'pct': pct,
            'tercapai': tercapai,
            'total': total,
            'items': item_details,
        }

    return domain_data


@routes_bp.route('/siswa/<int:id>/kemampuan-dasar')
@login_required
def kemampuan_dasar(id):
    siswa = Siswa.query.get_or_404(id)
    domain_data = compute_domain_data(id)

    # Check if there's any assessment data at all
    has_data = any(d['tercapai'] > 0 for d in domain_data.values())
    total_results = sum(d['total'] for d in domain_data.values())
    has_any_results = any(d['items'][0]['status'] != '-' for d in domain_data.values()
                          if d['items'])

    # Compute overall
    total_tercapai = sum(d['tercapai'] for d in domain_data.values())
    total_items = sum(d['total'] for d in domain_data.values())

    return render_template(
        'siswa/kemampuan_dasar.html',
        siswa=siswa,
        domain_data=domain_data,
        has_data=has_data,
        has_any_results=has_any_results,
        total_tercapai=total_tercapai,
        total_items=total_items,
    )
