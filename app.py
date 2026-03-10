#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SkyTrack Pro - Главный файл приложения
Версия: 2.0
Совместимость: Python 3.11
"""

import os
import sys
import logging
from datetime import datetime
from pathlib import Path

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Flask и расширения
from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from flask_login import LoginManager, login_required, current_user
from flask_cors import CORS
from flask_mail import Mail
from dotenv import load_dotenv

# Загружаем переменные окружения
env_path = Path('.') / '.env'
if env_path.exists():
    load_dotenv()
    logger.info("✅ .env файл загружен")
else:
    logger.warning("⚠️ .env файл не найден, используются системные переменные")

# Импорт конфигурации
try:
    from config import Config
    logger.info("✅ Конфигурация загружена")
except ImportError as e:
    logger.error(f"❌ Ошибка импорта config: {e}")
    sys.exit(1)

# Импорт моделей и модулей
try:
    from models import db, User
    from auth import auth_bp
    from email_service import mail
    from opensky_client import OpenSkyClient
    logger.info("✅ Все модули импортированы")
except ImportError as e:
    logger.error(f"❌ Ошибка импорта модулей: {e}")
    sys.exit(1)

# Создание приложения Flask
app = Flask(__name__)
app.config.from_object(Config)

# Проверка секретного ключа
if not app.config.get('SECRET_KEY'):
    logger.error("❌ SECRET_KEY не установлен!")
    sys.exit(1)

# Инициализация расширений
try:
    CORS(app, supports_credentials=True)
    db.init_app(app)
    mail.init_app(app)
    logger.info("✅ Расширения инициализированы")
except Exception as e:
    logger.error(f"❌ Ошибка инициализации расширений: {e}")
    sys.exit(1)

# Инициализация Login Manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Пожалуйста, войдите для доступа к этой странице'
login_manager.login_message_category = 'info'

# Инициализация клиента OpenSky
try:
    opensky = OpenSkyClient(
        app.config.get('OPENSKY_CLIENT_ID'),
        app.config.get('OPENSKY_CLIENT_SECRET')
    )
    logger.info("✅ OpenSky клиент инициализирован")
except Exception as e:
    logger.error(f"❌ Ошибка инициализации OpenSky клиента: {e}")
    opensky = None

@login_manager.user_loader
def load_user(user_id):
    """Загрузка пользователя по ID для Flask-Login"""
    try:
        return db.session.get(User, int(user_id))
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки пользователя {user_id}: {e}")
        return None

# Регистрация blueprint
app.register_blueprint(auth_bp, url_prefix='/auth')
logger.info("✅ Blueprint зарегистрирован")

# Создание таблиц в базе данных
with app.app_context():
    try:
        db.create_all()
        logger.info("✅ Таблицы в базе данных созданы/проверены")
        
        # Проверка подключения к БД
        db.session.execute('SELECT 1')
        logger.info("✅ Подключение к базе данных работает")
    except Exception as e:
        logger.error(f"❌ Ошибка базы данных: {e}")

@app.route('/')
@login_required
def index():
    """Главная страница с картой"""
    try:
        return render_template('index.html', 
                             username=current_user.username,
                             update_interval=app.config.get('FLIGHT_UPDATE_INTERVAL', 5))
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки главной страницы: {e}")
        return "Ошибка сервера", 500

@app.route('/api/flights')
@login_required
def get_flights():
    """API endpoint для получения всех рейсов"""
    if not opensky:
        return jsonify({'success': False, 'error': 'OpenSky клиент не инициализирован'}), 500
    
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
        
        # Подсчёт статистики
        flights = data.get('flights', [])
        in_air = sum(1 for f in flights if not f.get('on_ground', True))
        on_ground = len(flights) - in_air
        
        return jsonify({
            'success': True,
            'flights': flights,
            'total': len(flights),
            'in_air': in_air,
            'on_ground': on_ground,
            'timestamp': data.get('time', int(datetime.utcnow().timestamp()))
        })
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения рейсов: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/flight/<icao24>')
@login_required
def get_flight_details(icao24):
    """API endpoint для деталей конкретного рейса"""
    if not opensky:
        return jsonify({'success': False, 'error': 'OpenSky клиент не инициализирован'}), 500
    
    try:
        details = opensky.get_flight_details(icao24)
        track = opensky.get_track(icao24)
        
        return jsonify({
            'success': True,
            'details': details,
            'track': track
        })
    except Exception as e:
        logger.error(f"❌ Ошибка получения деталей рейса {icao24}: {e}")
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
                'verified': current_user.is_verified,
                'created_at': current_user.created_at.isoformat() if current_user.created_at else None,
                'last_login': current_user.last_login.isoformat() if current_user.last_login else None
            })
        
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
        logger.error(f"❌ Ошибка обновления настроек: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/stats')
@login_required
def get_global_stats():
    """Статистика по самолётам в реальном времени"""
    if not opensky:
        return jsonify({'success': False, 'error': 'OpenSky клиент не инициализирован'}), 500
    
    try:
        data = opensky.get_all_flights()
        
        if 'success' in data and data['success']:
            flights = data.get('flights', [])
            
            # Подсчёт статистики
            in_air = sum(1 for f in flights if not f.get('on_ground', True))
            on_ground = len(flights) - in_air
            countries = set(f.get('country') for f in flights if f.get('country'))
            
            # Подсчёт по типам самолётов
            aircraft_types = {}
            for f in flights:
                if f.get('typecode'):
                    aircraft_types[f['typecode']] = aircraft_types.get(f['typecode'], 0) + 1
            
            # Топ-10 самых популярных типов
            top_types = dict(sorted(aircraft_types.items(), key=lambda x: x[1], reverse=True)[:10])
            
            return jsonify({
                'success': True,
                'total': len(flights),
                'in_air': in_air,
                'on_ground': on_ground,
                'countries': len(countries),
                'top_types': top_types,
                'timestamp': data.get('time', int(datetime.utcnow().timestamp()))
            })
        
        return jsonify({'success': False, 'error': 'Нет данных'})
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения статистики: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/search')
@login_required
def search_flights():
    """Поиск рейсов по параметрам"""
    query = request.args.get('q', '').upper()
    filter_type = request.args.get('type', 'all')
    
    if not opensky:
        return jsonify({'success': False, 'error': 'OpenSky клиент не инициализирован'}), 500
    
    try:
        data = opensky.get_all_flights()
        
        if 'success' not in data or not data['success']:
            return jsonify({'success': False, 'error': 'Нет данных'}), 500
        
        flights = data.get('flights', [])
        results = []
        
        for flight in flights:
            match = False
            
            if filter_type == 'callsign' and flight.get('callsign'):
                match = query in flight['callsign']
            elif filter_type == 'country' and flight.get('country'):
                match = query in flight['country'].upper()
            elif filter_type == 'aircraft' and flight.get('typecode'):
                match = query in flight['typecode'].upper()
            else:  # all
                match = (query in flight.get('callsign', '') or 
                        query in flight.get('country', '').upper() or 
                        query in flight.get('typecode', '').upper())
            
            if match:
                results.append({
                    'icao24': flight['icao24'],
                    'callsign': flight.get('callsign', '-----'),
                    'country': flight.get('country', 'Unknown'),
                    'latitude': flight.get('latitude'),
                    'longitude': flight.get('longitude'),
                    'altitude': flight.get('altitude'),
                    'velocity': flight.get('velocity'),
                    'typecode': flight.get('typecode', '')
                })
        
        return jsonify({
            'success': True,
            'results': results[:50],  # Ограничиваем до 50 результатов
            'total': len(results)
        })
        
    except Exception as e:
        logger.error(f"❌ Ошибка поиска: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/health')
def health_check():
    """Endpoint для проверки работоспособности"""
    health_status = {
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'environment': 'production' if not app.config.get('DEBUG', False) else 'development',
        'python_version': sys.version,
        'modules': {}
    }
    
    # Проверка базы данных
    try:
        db.session.execute('SELECT 1')
        health_status['database'] = 'connected'
    except Exception as e:
        health_status['database'] = f'error: {str(e)}'
        health_status['status'] = 'degraded'
    
    # Проверка OpenSky клиента
    health_status['opensky'] = 'available' if opensky else 'unavailable'
    
    # Проверка почты
    health_status['email'] = 'configured' if app.config.get('MAIL_USERNAME') else 'not configured'
    
    return jsonify(health_status)

@app.errorhandler(404)
def not_found_error(error):
    """Обработка 404 ошибки"""
    return jsonify({'success': False, 'error': 'Страница не найдена'}), 404

@app.errorhandler(500)
def internal_error(error):
    """Обработка 500 ошибки"""
    db.session.rollback()
    logger.error(f"❌ Внутренняя ошибка сервера: {error}")
    return jsonify({'success': False, 'error': 'Внутренняя ошибка сервера'}), 500

@app.errorhandler(429)
def rate_limit_error(error):
    """Обработка превышения лимита запросов"""
    return jsonify({
        'success': False, 
        'error': 'Слишком много запросов',
        'retry_after': 60
    }), 429

if __name__ == '__main__':
    # Вывод информации при запуске
    port = int(os.environ.get('PORT', 5000))
    debug = app.config.get('DEBUG', False)
    
    print(f"""
    ╔══════════════════════════════════════════════════════════════╗
    ║                                                              ║
    ║   ✈️  SkyTrack Pro - Профессиональный трекер рейсов         ║
    ║                                                              ║
    ║   📍 Адрес: http://0.0.0.0:{port}                            ║
    ║   🔄 Обновление: каждые {app.config.get('FLIGHT_UPDATE_INTERVAL', 5)} секунд   ║
    ║   🐍 Python: {sys.version.split()[0]}                        ║
    ║   🔧 Режим: {'DEBUG' if debug else 'PRODUCTION'}             ║
    ║                                                              ║
    ║   🔑 OpenSky: {'✅ Доступен' if opensky else '❌ Недоступен'}              ║
    ║   🗄️  База данных: {'✅ Подключена' if db.engine else '❌ Ошибка'}         ║
    ║   📧 Email: {'✅ Настроен' if app.config.get('MAIL_USERNAME') else '❌ Нет'}║
    ║                                                              ║
    ╚══════════════════════════════════════════════════════════════╝
    """)
    
    # Запуск приложения
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug,
        threaded=True
    )
