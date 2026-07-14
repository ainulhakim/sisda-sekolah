from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.routes import routes_bp
from app.models import AssessmentSection, AssessmentItem, AssessmentResult, Siswa, TahunAjaran
from app import db
from datetime import date

@routes_bp.route('/siswa/<int:siswa_id>/assessment')
@login_required
def assessment_view(siswa_id):
    siswa = Siswa.query.get_or_404(siswa_id)
    sections = AssessmentSection.query.order_by(AssessmentSection.kode).all()
    ta = TahunAjaran.query.filter_by(is_active=True).first()
    results = {}
    if ta:
        for r in AssessmentResult.query.filter_by(siswa_id=siswa_id, tahun_ajaran_id=ta.id).all():
            results[r.item_id] = r
    else:
        for r in AssessmentResult.query.filter_by(siswa_id=siswa_id).all():
            results[r.item_id] = r
    return render_template('siswa/assessment.html', siswa=siswa, sections=sections, results=results, ta=ta)

@routes_bp.route('/siswa/<int:siswa_id>/assessment/save', methods=['POST'])
@login_required
def assessment_save(siswa_id):
    siswa = Siswa.query.get_or_404(siswa_id)
    ta = TahunAjaran.query.filter_by(is_active=True).first()
    data = request.form
    for key, value in data.items():
        if key.startswith('item_'):
            item_id = int(key.replace('item_', ''))
            existing = AssessmentResult.query.filter_by(
                siswa_id=siswa_id, item_id=item_id, tahun_ajaran_id=ta.id if ta else None
            ).first()
            if existing:
                existing.nilai = value
                existing.catatan = data.get(f'catatan_{item_id}', '')
            else:
                r = AssessmentResult(
                    siswa_id=siswa_id, item_id=item_id,
                    tahun_ajaran_id=ta.id if ta else None,
                    nilai=value,
                    catatan=data.get(f'catatan_{item_id}', ''),
                    assessor_id=current_user.guru_id if current_user.guru_id else None,
                    tanggal=date.today()
                )
                db.session.add(r)
    db.session.commit()
    flash('Data assessment berhasil disimpan!', 'success')
    return redirect(url_for('routes.assessment_view', siswa_id=siswa_id))
