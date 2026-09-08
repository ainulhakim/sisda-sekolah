"""
Face recognition service for SiSD — NO dlib dependency.
All face detection runs client-side via face-api.js (browser).
Server only stores/retrieves 128-dim embeddings and compares them using numpy.

Flow:
  1. Browser: face-api.js detects face → extracts 128-dim descriptor
  2. Client sends embedding to server
  3. Server: compare with enrolled embeddings (cosine similarity via numpy)
"""

import json
import math
from app import db
from app.models import Siswa


def euclidean_distance(emb1: list, emb2: list) -> float:
    """
    Compute Euclidean distance between two 128-dim face embeddings.
    Lower = more similar. Standard metric for face-api.js descriptors.
    Typical threshold: 0.6 (same person if < 0.6).
    """
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(emb1, emb2)))


def match_student_face(client_embedding: list, threshold: float = 0.55) -> tuple:
    """
    Match a client face embedding against all enrolled students.
    Uses Euclidean distance — lower = more similar.
    Returns (siswa_id, confidence) or (None, 0.0).
    """
    enrolled = Siswa.query.filter_by(face_enrolled=True).all()
    if not enrolled:
        return (None, 0.0)

    best_id = None
    best_dist = float('inf')

    for student in enrolled:
        try:
            stored = json.loads(student.face_embedding)
            dist = euclidean_distance(client_embedding, stored)
            if dist < best_dist:
                best_dist = dist
                best_id = student.id
        except (json.JSONDecodeError, ValueError, TypeError):
            continue

    # Lower distance = more similar; must be below threshold
    if best_id is not None and best_dist < threshold:
        confidence = round(1.0 - best_dist, 4)  # convert to 0-1 scale (1=identical)
        return (best_id, confidence)

    return (None, 0.0)


def enroll_student_face(siswa_id: int, embedding: list) -> dict:
    """
    Store a face embedding for a student.
    embedding: 128-dim list of floats from face-api.js client.
    """
    try:
        student = Siswa.query.get(siswa_id)
        if not student:
            return {'success': False, 'message': 'Siswa tidak ditemukan'}

        if len(embedding) != 128:
            return {'success': False, 'message': 'Embedding harus 128 dimensi'}

        student.face_embedding = json.dumps(embedding)
        student.face_enrolled = True
        db.session.commit()

        return {
            'success': True,
            'message': f'Wajah {student.nama_panggilan or student.nama_lengkap} berhasil didaftarkan',
            'siswa_id': student.id,
        }
    except Exception as e:
        db.session.rollback()
        return {'success': False, 'message': f'Gagal: {str(e)}'}
