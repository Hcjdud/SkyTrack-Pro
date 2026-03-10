#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Сервис отправки email для SkyTrack Pro
"""

from flask_mail import Mail, Message
from threading import Thread
from flask import current_app

mail = Mail()

def send_async_email(app, msg):
    """Отправка email в фоновом потоке"""
    with app.app_context():
        try:
            mail.send(msg)
            print(f"✅ Email отправлен на {msg.recipients}")
        except Exception as e:
            print(f"❌ Ошибка отправки email: {e}")

def send_verification_email(user_email, code, app):
    """Отправка кода верификации на почту"""
    msg = Message(
        subject="✈️ SkyTrack Pro - Подтверждение email",
        recipients=[user_email]
    )
    
    msg.html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{
                font-family: 'Inter', sans-serif;
                background: #0B0F16;
                margin: 0;
                padding: 0;
            }}
            .container {{
                max-width: 600px;
                margin: 20px auto;
                background: linear-gradient(135deg, #1a1f2e, #0f1219);
                border-radius: 24px;
                overflow: hidden;
            }}
            .header {{
                background: linear-gradient(135deg, #3b82f6, #8b5cf6);
                padding: 40px 30px;
                text-align: center;
            }}
            .header h1 {{
                color: white;
                font-size: 32px;
                margin: 0;
            }}
            .content {{
                padding: 40px 30px;
                color: #fff;
            }}
            .code {{
                font-family: monospace;
                font-size: 48px;
                font-weight: 700;
                letter-spacing: 8px;
                text-align: center;
                background: rgba(255,255,255,0.05);
                padding: 30px;
                border-radius: 16px;
                margin: 20px 0;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>✈️ SkyTrack Pro</h1>
            </div>
            <div class="content">
                <h2>Подтверждение email</h2>
                <p>Ваш код подтверждения:</p>
                <div class="code">{code}</div>
                <p>Код действителен 5 минут.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    Thread(target=send_async_email, args=(app, msg)).start()

def send_welcome_email(user_email, username, app):
    """Отправка приветственного письма"""
    msg = Message(
        subject="✈️ Добро пожаловать в SkyTrack Pro!",
        recipients=[user_email]
    )
    
    msg.html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{
                font-family: 'Inter', sans-serif;
                background: #0B0F16;
                margin: 0;
                padding: 0;
            }}
            .container {{
                max-width: 600px;
                margin: 20px auto;
                background: linear-gradient(135deg, #1a1f2e, #0f1219);
                border-radius: 24px;
                overflow: hidden;
            }}
            .header {{
                background: linear-gradient(135deg, #3b82f6, #8b5cf6);
                padding: 40px 30px;
                text-align: center;
            }}
            .content {{
                padding: 40px 30px;
                color: #fff;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Добро пожаловать, {username}!</h1>
            </div>
            <div class="content">
                <p>Ваш email успешно подтверждён.</p>
                <p>Теперь вы можете отслеживать все самолёты мира в реальном времени!</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    Thread(target=send_async_email, args=(app, msg)).start()

def init_mail(app):
    """Инициализация почты"""
    mail.init_app(app)
