from flask import Blueprint, render_template, request, jsonify, session, current_app
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, VerificationCode
from email_service import send_verification_email, send_welcome_email
from datetime import datetime
import re

auth_bp = Blueprint('auth', __name__)

def is_valid_email(email):
    """Проверка валидности email"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def is_valid_username(username):
    """Проверка валидности username"""
    pattern = r'^[a-zA-Z0-9_]{3,20}$'
    return bool(re.match(pattern, username))

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Страница входа"""
    if request.method == 'GET':
        return render_template('login.html')
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Нет данных'}), 400
        
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        
        if not email or not password:
            return jsonify({'success': False, 'error': 'Заполните все поля'}), 400
        
        user = User.query.filter_by(email=email).first()
        
        if not user or not check_password_hash(user.password_hash, password):
            return jsonify({'success': False, 'error': 'Неверный email или пароль'}), 401
        
        if not user.is_verified:
            return jsonify({'success': False, 'error': 'email_not_verified', 'email': email}), 403
        
        login_user(user, remember=True)
        user.last_login = datetime.utcnow()
        db.session.commit()
        
        return jsonify({'success': True, 'redirect': '/'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Регистрация нового пользователя"""
    if request.method == 'GET':
        return render_template('register.html')
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Нет данных'}), 400
        
        email = data.get('email', '').strip().lower()
        username = data.get('username', '').strip()
        password = data.get('password', '')
        password_confirm = data.get('password_confirm', '')
        
        # Валидация
        if not is_valid_email(email):
            return jsonify({'success': False, 'error': 'Некорректный email'}), 400
        
        if not is_valid_username(username):
            return jsonify({'success': False, 'error': 'Имя пользователя должно быть 3-20 символов (буквы, цифры, _)'}), 400
        
        if len(password) < 6:
            return jsonify({'success': False, 'error': 'Пароль должен быть минимум 6 символов'}), 400
        
        if password != password_confirm:
            return jsonify({'success': False, 'error': 'Пароли не совпадают'}), 400
        
        # Проверка существования
        if User.query.filter_by(email=email).first():
            return jsonify({'success': False, 'error': 'Email уже зарегистрирован'}), 400
        
        if User.query.filter_by(username=username).first():
            return jsonify({'success': False, 'error': 'Имя пользователя уже занято'}), 400
        
        # Создание пользователя
        user = User(
            email=email,
            username=username,
            password_hash=generate_password_hash(password),
            is_verified=False
        )
        
        db.session.add(user)
        db.session.commit()
        
        # Генерация кода подтверждения
        verification = VerificationCode.create_for_user(user)
        
        # Отправка email с кодом
        try:
            send_verification_email(email, verification.code, current_app._get_current_object())
            print(f"✅ Код отправлен на {email}: {verification.code}")
        except Exception as e:
            print(f"❌ Ошибка отправки email: {e}")
            # Даже если почта не отправилась, код сохраняется в БД
        
        # Сохраняем email в сессии
        session['verification_email'] = email
        
        return jsonify({
            'success': True,
            'message': 'Код подтверждения отправлен на почту',
            'redirect': '/auth/verify'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@auth_bp.route('/verify', methods=['GET', 'POST'])
def verify():
    """Подтверждение email по коду"""
    if request.method == 'GET':
        email = session.get('verification_email', '')
        return render_template('verify.html', email=email)
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Нет данных'}), 400
        
        email = data.get('email', '').strip().lower()
        code = data.get('code', '').strip()
        
        if not email or not code:
            return jsonify({'success': False, 'error': 'Не указан email или код'}), 400
        
        user = User.query.filter_by(email=email).first()
        if not user:
            return jsonify({'success': False, 'error': 'Пользователь не найден'}), 404
        
        # Поиск действующего кода
        verification = VerificationCode.query.filter_by(
            user_id=user.id,
            code=code,
            purpose='email_verification',
            used=False
        ).filter(VerificationCode.expires_at > datetime.utcnow()).first()
        
        if not verification:
            return jsonify({'success': False, 'error': 'Неверный или истёкший код'}), 400
        
        # Активация пользователя
        verification.used = True
        user.is_verified = True
        db.session.commit()
        
        # Отправка приветственного письма
        try:
            send_welcome_email(email, user.username, current_app._get_current_object())
        except Exception as e:
            print(f"❌ Ошибка отправки приветствия: {e}")
        
        # Автоматический вход
        login_user(user, remember=True)
        
        # Очистка сессии
        session.pop('verification_email', None)
        
        return jsonify({
            'success': True,
            'message': 'Email успешно подтверждён',
            'redirect': '/'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@auth_bp.route('/resend-code', methods=['POST'])
def resend_code():
    """Повторная отправка кода"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Нет данных'}), 400
        
        email = data.get('email', '').strip().lower()
        
        user = User.query.filter_by(email=email, is_verified=False).first()
        if not user:
            return jsonify({'success': False, 'error': 'Пользователь не найден или уже верифицирован'}), 404
        
        # Создаём новый код
        verification = VerificationCode.create_for_user(user)
        
        # Отправляем email
        try:
            send_verification_email(email, verification.code, current_app._get_current_object())
            print(f"✅ Новый код отправлен на {email}: {verification.code}")
        except Exception as e:
            print(f"❌ Ошибка отправки email: {e}")
        
        return jsonify({
            'success': True,
            'message': 'Код отправлен повторно'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@auth_bp.route('/logout')
@login_required
def logout():
    """Выход из системы"""
    logout_user()
    return redirect('/auth/login')
