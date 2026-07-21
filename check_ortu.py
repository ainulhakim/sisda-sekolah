
from app import create_app
from app.models import AssessmentOrtu
import json
app = create_app()
with app.app_context():
    a = AssessmentOrtu.query.filter_by(siswa_id=5).first()
    if a and a.data_json:
        d = json.loads(a.data_json)
        for k in sorted(d.keys()):
            if 'minat' in k or 'kese' in k or 'belajar' in k:
                print("key=%s, val=%s" % (k, d[k]))
    else:
        print("No data")
