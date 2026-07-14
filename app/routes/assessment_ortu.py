import json
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.routes import routes_bp
from app.models import AssessmentOrtu, Siswa, TahunAjaran
from app import db
from datetime import date


@routes_bp.route('/siswa/<int:siswa_id>/assessment-ortu')
@login_required
def assessment_ortu_view(siswa_id):
    """View and fill assessment ortu"""
    siswa = Siswa.query.get_or_404(siswa_id)
    ta = TahunAjaran.query.filter_by(is_active=True).first()
    assessment = AssessmentOrtu.query.filter_by(
        siswa_id=siswa_id,
        tahun_ajaran_id=ta.id if ta else None
    ).first()
    existing_data = json.loads(assessment.data_json) if assessment and assessment.data_json else {}
    return render_template('siswa/assessment_ortu.html', siswa=siswa, data=existing_data, ta=ta)


@routes_bp.route('/siswa/<int:siswa_id>/assessment-ortu/save', methods=['POST'])
@login_required
def assessment_ortu_save(siswa_id):
    """Save assessment ortu"""
    siswa = Siswa.query.get_or_404(siswa_id)
    ta = TahunAjaran.query.filter_by(is_active=True).first()

    # Collect all form data into JSON
    data = {}
    processed_keys = set()

    for key in request.form:
        if key.startswith('csrf_token'):
            continue
        if key in processed_keys:
            continue

        if key.endswith('[]'):
            clean_key = key[:-2]  # strip []
            data[clean_key] = request.form.getlist(key)
        else:
            data[key] = request.form.get(key, '')
        processed_keys.add(key)

    assessment = AssessmentOrtu.query.filter_by(
        siswa_id=siswa_id,
        tahun_ajaran_id=ta.id if ta else None
    ).first()

    if assessment:
        assessment.data_json = json.dumps(data, ensure_ascii=False)
        assessment.assessor_id = current_user.guru_id if hasattr(current_user, 'guru_id') and current_user.guru_id else None
    else:
        assessment = AssessmentOrtu(
            siswa_id=siswa_id,
            tahun_ajaran_id=ta.id if ta else None,
            data_json=json.dumps(data, ensure_ascii=False),
            assessor_id=current_user.guru_id if hasattr(current_user, 'guru_id') and current_user.guru_id else None,
            tanggal=date.today()
        )
        db.session.add(assessment)

    db.session.commit()
    flash('Assessment Orang Tua berhasil disimpan!', 'success')
    return redirect(url_for('routes.assessment_ortu_view', siswa_id=siswa_id))
