from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, timedelta
import random
import string

db = SQLAlchemy()

class User(UserMixin, db.Model):
    """Модель пользователя"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(200), nullable=False)
    is_verified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    
    # Настройки пользователя
    show_trails = db.Column(db.Boolean, default=True)
    map_style = db.Column(db.String(50), default='satellite')
    
    # Связи
    verification_codes = db.relationship('VerificationCode', backref='user', lazy=True, cascade='all, delete-orphan')
    favorites = db.relationship('FavoriteAircraft', backref='user', lazy=True, cascade='all, delete-orphan')
    
    def get_id(self):
        return str(self.id)
    
    def __repr__(self):
        return f'<User {self.username}>'

class VerificationCode(db.Model):
    """Модель для кодов верификации"""
    __tablename__ = 'verification_codes'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    code = db.Column(db.String(10), nullable=False)
    purpose = db.Column(db.String(50), default='email_verification')
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    @staticmethod
    def generate_code(length=5):
        """Генерация случайного цифрового кода"""
        return ''.join(random.choices(string.digits, k=length))
    
    @staticmethod
    def create_for_user(user, purpose='email_verification', minutes=5):
        """Создать код для пользователя"""
        # Деактивируем старые коды
        VerificationCode.query.filter_by(
            user_id=user.id, 
            purpose=purpose,
            used=False
        ).update({'used': True})
        
        code = VerificationCode(
            user_id=user.id,
            code=VerificationCode.generate_code(),
            purpose=purpose,
            expires_at=datetime.utcnow() + timedelta(minutes=minutes)
        )
        db.session.add(code)
        db.session.commit()
        return code
    
    def is_valid(self):
        """Проверка валидности кода"""
        return not self.used and self.expires_at > datetime.utcnow()

class FavoriteAircraft(db.Model):
    """Избранные самолёты пользователя"""
    __tablename__ = 'favorite_aircraft'
    __table_args__ = (
        db.UniqueConstraint('user_id', 'icao24', name='unique_user_aircraft'),
    )
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    icao24 = db.Column(db.String(10), nullable=False)
    callsign = db.Column(db.String(20))
    notes = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
