import os
import sys
from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from flask_login import LoginManager, login_required, current_user
from flask_cors import CORS
from flask_mail import Mail
from dotenv import load_dotenv

# Загружаем .env в локальной разработке
if os.path.exists('.env'):
    load_dotenv()

from config import Config
from models import db, User
from auth import auth_bp
from email_service import mail
from opensky_client import OpenSkyClient

# Создание приложения
app = Flask(__name__)
app.config.from_object(Config)

# Проверка конфигурации
Config.validate_config()

# Инициализация расширений
CORS(app, supports_credentials=True)
db.init_app(app)
mail.init_app(app)

# Инициализация Login Manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Пожалуйста, войдите для доступа к этой странице'

# Инициализация клиента OpenSky
opensky = OpenSkyClient(
    Config.OPENSKY_CLIENT_ID,
    Config.OPENSKY_CLIENT_SECRET
)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# Регистрация blueprint
app.register_blueprint(auth_bp, url_prefix='/auth')

# Создание таблиц в базе данных
with app.app_context():
    try:
        db.create_all()
        print("✅ Таблицы в базе данных созданы/проверены")
    except Exception as e:
        print(f"❌ Ошибка создания таблиц: {e}")

@app.route('/')
@login_required
def index():
    """Главная страница с Google Maps"""
    return render_template('index.html', 
                         username=current_user.username,
                         google_maps_api_key=Config.GOOGLE_MAPS_API_KEY,
                         update_interval=Config.FLIGHT_UPDATE_INTERVAL)

@app.route('/api/flights')
@login_required
def get_flights():
    """API endpoint для получения всех рейсов"""
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
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/flight/<icao24>')
@login_required
def get_flight(icao24):
    """API endpoint для деталей конкретного рейса"""
    try:
        details = opensky.get_flight_details(icao24)
        track = opensky.get_track(icao24)
        
        return jsonify({
            'success': True,
            'details': details,
            'track': track
        })
    except Exception as e:
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
        
        data = request.get_json()
        if 'show_trails' in data:
            current_user.show_trails = bool(data['show_trails'])
        if 'map_style' in data:
            current_user.map_style = str(data['map_style'])
        
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/stats')
@login_required
def get_stats():
    """Статистика по самолётам"""
    try:
        data = opensky.get_all_flights()
        
        if 'success' in data and data['success']:
            flights = data.get('flights', [])
            
            in_air = sum(1 for f in flights if not f.get('on_ground', True))
            on_ground = len(flights) - in_air
            countries = set(f.get('country') for f in flights if f.get('country'))
            
            return jsonify({
                'success': True,
                'total': len(flights),
                'in_air': in_air,
                'on_ground': on_ground,
                'countries': len(countries),
                'timestamp': data.get('time', 0)
            })
        
        return jsonify({'success': False, 'error': 'No data'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/health')
def health():
    """Endpoint для проверки работоспособности на Render"""
    from datetime import datetime
    return jsonify({
        'status': 'healthy',
        'database': 'connected' if db.engine else 'disconnected',
        'timestamp': datetime.utcnow().isoformat(),
        'environment': 'production' if not Config.DEBUG else 'development'
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(
        host='0.0.0.0',
        port=port,
        debug=Config.DEBUG
                  )
