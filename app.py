#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SkyTrack Pro - Главный файл приложения
Профессиональный трекер самолётов с картой
"""

import os
import sys
from datetime import datetime, timedelta

# Импорты Flask и расширений
from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from flask_login import LoginManager, login_required, current_user
from flask_cors import CORS
from flask_mail import Mail
from dotenv import load_dotenv

# Загружаем переменные окружения из .env (только для локальной разработки)
if os.path.exists('.env'):
    load_dotenv()
    print("✅ Загружен .env файл")
else:
    print("ℹ️ .env файл не найден, используем переменные окружения системы")

# Импорт конфигурации
from config import Config

# Проверка версий критических пакетов
import werkzeug
import flask_login
print(f"✅ Werkzeug версия: {werkzeug.__version__}")
print(f"✅ Flask-Login версия: {flask_login.__version__}")

# Импорт моделей и модулей приложения
from models import db, User
from auth import auth_bp
from email_service import mail
from opensky_client import OpenSkyClient

# Создание экземпляра приложения Flask
app = Flask(__name__)
app.config.from_object(Config)

# Проверка конфигурации
Config.validate_config()

# Инициализация расширений
CORS(app, supports_credentials=True)  # Включаем CORS для всех маршрутов
db.init_app(app)  # Инициализация SQLAlchemy
mail.init_app(app)  # Инициализация Flask-Mail

# Инициализация Login Manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'  # Перенаправление на страницу входа
login_manager.login_message = 'Пожалуйста, войдите для доступа к этой странице'
login_manager.login_message_category = 'info'

# Инициализация клиента OpenSky
opensky = OpenSkyClient(
    Config.OPENSKY_CLIENT_ID,
    Config.OPENSKY_CLIENT_SECRET
)

@login_manager.user_loader
def load_user(user_id):
    """Загрузка пользователя по ID для Flask-Login"""
    try:
        return db.session.get(User, int(user_id))
    except Exception as e:
        print(f"❌ Ошибка загрузки пользователя: {e}")
        return None

# Регистрация blueprint для аутентификации
app.register_blueprint(auth_bp, url_prefix='/auth')

# Создание таблиц в базе данных
with app.app_context():
    try:
        db.create_all()
        print("✅ Таблицы в базе данных созданы/проверены")
    except Exception as e:
        print(f"❌ Ошибка создания таблиц: {e}")
        print("⚠️ Проверьте подключение к базе данных")

@app.route('/')
@login_required
def index():
    """Главная страница с картой (только для авторизованных)"""
    try:
        return render_template('index.html', 
                             username=current_user.username,
                             update_interval=Config.FLIGHT_UPDATE_INTERVAL)
    except Exception as e:
        print(f"❌ Ошибка загрузки главной страницы: {e}")
        return "Ошибка загрузки страницы", 500

@app.route('/api/flights')
@login_required
def get_flights():
    """API endpoint для получения всех рейсов в реальном времени"""
    try:
        data = opensky.get_all_flights()
        
        if 'error' in data:
            if data['error'] == 'rate_limit':
                return jsonify({
                    'success': False,
                    'error': 'rate_limit',
                    'retry_after': data.get('retry_after', 60)
                }), 429
            else:
                return jsonify({'success': False, 'error': data['error']}), 500
        
        return jsonify(data)
    except Exception as e:
        print(f"❌ Ошибка получения рейсов: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/flight/<icao24>')
@login_required
def get_flight(icao24):
    """API endpoint для детальной информации о конкретном рейсе"""
    try:
        details = opensky.get_flight_details(icao24)
        track = opensky.get_track(icao24)
        
        return jsonify({
            'success': True,
            'details': details,
            'track': track
        })
    except Exception as e:
        print(f"❌ Ошибка получения деталей рейса: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/user/preferences', methods=['GET', 'POST'])
@login_required
def user_preferences():
    """Управление настройками пользователя"""
    try:
        if request.method == 'GET':
            return jsonify({
                'success': True,
                'show_trails': current_user.show_trails,
                'map_style': current_user.map_style,
                'username': current_user.username,
                'email': current_user.email,
                'verified': current_user.is_verified
            })
        
        # POST запрос - обновление настроек
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Нет данных'}), 400
            
        if 'show_trails' in data:
            current_user.show_trails = bool(data['show_trails'])
        if 'map_style' in data:
            current_user.map_style = str(data['map_style'])
        
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        print(f"❌ Ошибка обновления настроек: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/favorites', methods=['GET', 'POST', 'DELETE'])
@login_required
def favorites():
    """Избранные самолёты пользователя"""
    try:
        if request.method == 'GET':
            from models import FavoriteAircraft
            favs = FavoriteAircraft.query.filter_by(user_id=current_user.id).all()
            return jsonify({
                'success': True,
                'favorites': [{
                    'icao24': f.icao24,
                    'callsign': f.callsign,
                    'notes': f.notes,
                    'created_at': f.created_at.isoformat() if f.created_at else None
                } for f in favs]
            })
        
        elif request.method == 'POST':
            from models import FavoriteAircraft
            data = request.get_json()
            if not data or 'icao24' not in data:
                return jsonify({'success': False, 'error': 'Не указан ICAO код'}), 400
            
            # Проверяем, нет ли уже в избранном
            existing = FavoriteAircraft.query.filter_by(
                user_id=current_user.id,
                icao24=data['icao24']
            ).first()
            
            if not existing:
                fav = FavoriteAircraft(
                    user_id=current_user.id,
                    icao24=data['icao24'],
                    callsign=data.get('callsign', ''),
                    notes=data.get('notes', '')
                )
                db.session.add(fav)
                db.session.commit()
                return jsonify({'success': True, 'message': 'Добавлено в избранное'})
            else:
                return jsonify({'success': False, 'error': 'Уже в избранном'}), 400
        
        elif request.method == 'DELETE':
            from models import FavoriteAircraft
            data = request.get_json()
            if not data or 'icao24' not in data:
                return jsonify({'success': False, 'error': 'Не указан ICAO код'}), 400
                
            deleted = FavoriteAircraft.query.filter_by(
                user_id=current_user.id,
                icao24=data['icao24']
            ).delete()
            db.session.commit()
            
            if deleted:
                return jsonify({'success': True, 'message': 'Удалено из избранного'})
            else:
                return jsonify({'success': False, 'error': 'Не найдено в избранном'}), 404
    except Exception as e:
        db.session.rollback()
        print(f"❌ Ошибка работы с избранным: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/stats')
@login_required
def get_stats():
    """Статистика по самолётам в реальном времени"""
    try:
        data = opensky.get_all_flights()
        
        if 'success' in data and data['success']:
            flights = data.get('flights', [])
            
            # Подсчёт статистики
            total = len(flights)
            in_air = sum(1 for f in flights if not f.get('on_ground', True))
            on_ground = total - in_air
            
            # Уникальные страны
            countries = set(f.get('country') for f in flights if f.get('country'))
            
            return jsonify({
                'success': True,
                'total': total,
                'in_air': in_air,
                'on_ground': on_ground,
                'countries': len(countries),
                'timestamp': data.get('time', int(datetime.now().timestamp()))
            })
        
        return jsonify({'success': False, 'error': 'Нет данных'})
    except Exception as e:
        print(f"❌ Ошибка получения статистики: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/test-email')
def test_email():
    """Тестовый маршрут для проверки отправки почты"""
    from email_service import send_verification_email
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 50)
    logger.info("🔍 ТЕСТОВЫЙ ЗАПРОС НА ОТПРАВКУ ПОЧТЫ")
    logger.info(f"MAIL_USERNAME: {app.config.get('MAIL_USERNAME')}")
    logger.info(f"MAIL_SERVER: {app.config.get('MAIL_SERVER')}:{app.config.get('MAIL_PORT')}")
    logger.info("=" * 50)
    
    test_email = app.config.get('MAIL_USERNAME')  # Отправляем на тот же ящик
    test_code = "12345"
    
    try:
        send_verification_email(test_email, test_code, app)
        return jsonify({
            'success': True,
            'message': 'Тестовое письмо отправляется',
            'check_logs': 'Проверьте логи Render для подробностей',
            'config': {
                'MAIL_SERVER': app.config.get('MAIL_SERVER'),
                'MAIL_PORT': app.config.get('MAIL_PORT'),
                'MAIL_USERNAME': app.config.get('MAIL_USERNAME'),
                'MAIL_USE_SSL': app.config.get('MAIL_USE_SSL')
            }
        })
    except Exception as e:
        logger.error(f"❌ Ошибка тестовой отправки: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'error_type': type(e).__name__
        }), 500

@app.route('/health')
def health():
    """Endpoint для проверки работоспособности приложения"""
    try:
        db_status = 'connected' if db.engine else 'disconnected'
        opensky_status = 'configured' if Config.OPENSKY_CLIENT_ID else 'not configured'
        
        return jsonify({
            'status': 'healthy',
            'database': db_status,
            'opensky': opensky_status,
            'timestamp': datetime.utcnow().isoformat(),
            'environment': 'production' if not Config.DEBUG else 'development'
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500

@app.errorhandler(404)
def not_found_error(error):
    """Обработчик ошибки 404"""
    return jsonify({'success': False, 'error': 'Страница не найдена'}), 404

@app.errorhandler(500)
def internal_error(error):
    """Обработчик ошибки 500"""
    db.session.rollback()
    return jsonify({'success': False, 'error': 'Внутренняя ошибка сервера'}), 500

@app.errorhandler(401)
def unauthorized_error(error):
    """Обработчик ошибки 401 (не авторизован)"""
    return jsonify({'success': False, 'error': 'Требуется авторизация'}), 401

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    
    print(f"""
    ╔══════════════════════════════════════════════════════════════╗
    ║                                                              ║
    ║   ✈️  SkyTrack Pro - Профессиональный трекер рейсов         ║
    ║                                                              ║
    ║   📍 Адрес: http://localhost:{port}                          ║
    ║   🔄 Обновление: каждые {Config.FLIGHT_UPDATE_INTERVAL} секунд   ║
    ║   🔑 OpenSky: {'✅' if Config.OPENSKY_CLIENT_ID else '❌'}                   ║
    ║   📧 Email: {'✅' if Config.MAIL_USERNAME else '❌'}                    ║
    ║   🗄️  База: {'✅' if Config.SQLALCHEMY_DATABASE_URI else '❌'}           ║
    ║   🔧 Werkzeug: {werkzeug.__version__}                             ║
    ║                                                              ║
    ╚══════════════════════════════════════════════════════════════╝
    """)
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=Config.DEBUG,
        threaded=True
)
