from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.auth import auth_bp
from app.models import User
from app import db

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('routes.dashboard'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            flash('Selamat datang, {}!'.format(user.username), 'success')
            return redirect(url_for('routes.dashboard'))
        flash('Username atau password salah!', 'danger')
    return render_template('auth/login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Anda telah logout.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/ganti-password', methods=['GET', 'POST'])
@login_required
def ganti_password():
    if request.method == 'POST':
        password_lama = request.form.get('password_lama', '')
        password_baru = request.form.get('password_baru', '')
        konfirmasi = request.form.get('konfirmasi_password', '')

        if not current_user.check_password(password_lama):
            flash('Password lama salah!', 'danger')
        elif password_baru != konfirmasi:
            flash('Password baru dan konfirmasi tidak cocok!', 'danger')
        elif len(password_baru) < 6:
            flash('Password baru minimal 6 karakter!', 'danger')
        else:
            current_user.set_password(password_baru)
            db.session.commit()
            flash('Password berhasil diubah!', 'success')
            return redirect(url_for('auth.ganti_password'))
    return render_template('auth/ganti_password.html')
