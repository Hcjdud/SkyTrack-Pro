from flask_mail import Mail, Message
from threading import Thread
from flask import current_app
import logging
import smtplib
import socket

# Настройка логирования
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

mail = Mail()

def send_async_email(app, msg):
    """Отправка email в фоновом потоке с обработкой ошибок"""
    with app.app_context():
        try:
            logger.info("=" * 50)
            logger.info(f"📧 НАЧАЛО ОТПРАВКИ EMAIL")
            logger.info(f"📧 Получатель: {msg.recipients}")
            logger.info(f"📧 Тема: {msg.subject}")
            logger.info(f"📧 SMTP сервер: {app.config.get('MAIL_SERVER')}:{app.config.get('MAIL_PORT')}")
            logger.info(f"📧 Отправитель: {app.config.get('MAIL_USERNAME')}")
            logger.info(f"📧 Использовать SSL: {app.config.get('MAIL_USE_SSL')}")
            
            # Проверяем, настроена ли почта
            if not app.config.get('MAIL_USERNAME') or not app.config.get('MAIL_PASSWORD'):
                logger.error("❌ Почта не настроена: нет MAIL_USERNAME или MAIL_PASSWORD")
                logger.info("=" * 50)
                return
                
            # Пытаемся отправить
            mail.send(msg)
            logger.info(f"✅ Email успешно отправлен на {msg.recipients}")
            logger.info("=" * 50)
            
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"❌ ОШИБКА АУТЕНТИФИКАЦИИ SMTP: {e}")
            logger.error("❌ Причины:")
            logger.error("   1. Неправильный пароль")
            logger.error("   2. Не включён доступ для внешних приложений в Mail.ru")
            logger.error("   3. Используется основной пароль вместо пароля для приложений")
            logger.info("=" * 50)
            
        except smtplib.SMTPException as e:
            logger.error(f"❌ SMTP ОШИБКА: {e}")
            logger.info("=" * 50)
            
        except socket.gaierror as e:
            logger.error(f"❌ ОШИБКА DNS: Не удалось найти сервер {app.config.get('MAIL_SERVER')}")
            logger.error(f"❌ Проверьте правильность EMAIL_HOST в переменных окружения")
            logger.info("=" * 50)
            
        except ConnectionRefusedError as e:
            logger.error(f"❌ ОШИБКА ПОДКЛЮЧЕНИЯ: Сервер отказал в соединении")
            logger.error(f"❌ Проверьте порт {app.config.get('MAIL_PORT')} и наличие SSL/TLS")
            logger.info("=" * 50)
            
        except Exception as e:
            logger.error(f"❌ НЕИЗВЕСТНАЯ ОШИБКА: {e}")
            logger.error(f"❌ Тип ошибки: {type(e).__name__}")
            import traceback
            logger.error(traceback.format_exc())
            logger.info("=" * 50)

def send_verification_email(user_email, code, app):
    """Отправка кода верификации на почту"""
    logger.info(f"📧 ПОДГОТОВКА КОДА {code} ДЛЯ {user_email}")
    
    # Проверяем, настроена ли почта
    if not app.config.get('MAIL_USERNAME') or not app.config.get('MAIL_PASSWORD'):
        logger.error(f"❌ Почта не настроена. Код для {user_email}: {code}")
        logger.error(f"❌ Письмо НЕ будет отправлено!")
        return
    
    try:
        msg = Message(
            subject="✈️ SkyTrack Pro - Подтверждение email",
            recipients=[user_email],
            sender=app.config.get('MAIL_DEFAULT_SENDER')
        )
        
        # HTML версия
        msg.html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{
                    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
                    background: #0a0c14;
                    margin: 0;
                    padding: 0;
                }}
                .container {{
                    max-width: 600px;
                    margin: 20px auto;
                    background: linear-gradient(135deg, #1a1f2e, #0f1219);
                    border-radius: 24px;
                    overflow: hidden;
                    border: 1px solid rgba(59, 130, 246, 0.2);
                }}
                .header {{
                    background: linear-gradient(135deg, #3b82f6, #8b5cf6);
                    padding: 40px 30px;
                    text-align: center;
                }}
                .header h1 {{
                    color: white;
                    font-size: 28px;
                    margin: 0;
                    font-weight: 600;
                }}
                .content {{
                    padding: 40px 30px;
                    color: #fff;
                }}
                .code-box {{
                    background: rgba(255,255,255,0.05);
                    border: 1px solid rgba(59, 130, 246, 0.3);
                    border-radius: 16px;
                    padding: 30px;
                    text-align: center;
                    margin: 20px 0;
                }}
                .code {{
                    font-family: 'Monaco', monospace;
                    font-size: 48px;
                    font-weight: 700;
                    letter-spacing: 8px;
                    color: #3b82f6;
                    margin: 10px 0;
                }}
                .footer {{
                    text-align: center;
                    padding: 30px;
                    color: rgba(255,255,255,0.4);
                    font-size: 12px;
                    border-top: 1px solid rgba(255,255,255,0.05);
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>✈️ SkyTrack Pro</h1>
                </div>
                <div class="content">
                    <h2>Подтверждение регистрации</h2>
                    <p>Здравствуйте! Для завершения регистрации введите код:</p>
                    <div class="code-box">
                        <div style="color: rgba(255,255,255,0.5); margin-bottom: 10px;">Ваш код подтверждения</div>
                        <div class="code">{code}</div>
                    </div>
                    <p>Код действителен 5 минут.</p>
                    <p>Если вы не регистрировались на SkyTrack Pro, просто проигнорируйте это письмо.</p>
                </div>
                <div class="footer">
                    <p>© 2025 SkyTrack Pro. Все права защищены.</p>
                    <p>Это автоматическое письмо, пожалуйста, не отвечайте на него.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Текстовая версия
        msg.body = f"""
        SkyTrack Pro - Подтверждение регистрации
        
        Ваш код подтверждения: {code}
        
        Код действителен 5 минут.
        
        Если вы не регистрировались на SkyTrack Pro, просто проигнорируйте это письмо.
        
        © 2025 SkyTrack Pro
        """
        
        # Отправляем в фоне
        Thread(target=send_async_email, args=(app, msg)).start()
        logger.info(f"✅ Поток отправки запущен для {user_email}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при создании письма: {e}")

def send_welcome_email(user_email, username, app):
    """Отправка приветственного письма"""
    logger.info(f"📧 ПОДГОТОВКА ПРИВЕТСТВИЯ ДЛЯ {username} НА {user_email}")
    
    if not app.config.get('MAIL_USERNAME') or not app.config.get('MAIL_PASSWORD'):
        logger.warning(f"⚠️ Почта не настроена. Приветствие для {username} не отправлено")
        return
    
    try:
        msg = Message(
            subject="✈️ Добро пожаловать в SkyTrack Pro!",
            recipients=[user_email],
            sender=app.config.get('MAIL_DEFAULT_SENDER')
        )
        
        msg.html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{
                    font-family: 'Inter', sans-serif;
                    background: #0a0c14;
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
                    font-size: 28px;
                    margin: 0;
                }}
                .content {{
                    padding: 40px 30px;
                    color: #fff;
                }}
                .features {{
                    background: rgba(255,255,255,0.03);
                    border-radius: 16px;
                    padding: 20px;
                    margin: 20px 0;
                }}
                .feature-item {{
                    display: flex;
                    align-items: center;
                    gap: 10px;
                    margin: 15px 0;
                }}
                .feature-item i {{
                    color: #3b82f6;
                    width: 24px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Добро пожаловать, {username}!</h1>
                </div>
                <div class="content">
                    <p>Ваш email успешно подтверждён. Теперь вы можете:</p>
                    <div class="features">
                        <div class="feature-item">
                            <i class="fas fa-plane"></i>
                            <span>Отслеживать все самолёты мира в реальном времени</span>
                        </div>
                        <div class="feature-item">
                            <i class="fas fa-chart-line"></i>
                            <span>Получать детальную информацию о каждом рейсе</span>
                        </div>
                        <div class="feature-item">
                            <i class="fas fa-map-marked-alt"></i>
                            <span>Смотреть траектории полётов на карте</span>
                        </div>
                    </div>
                    <p style="margin-top: 25px;">Приятного использования!</p>
                </div>
                <div class="footer">
                    <p>© 2025 SkyTrack Pro</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        msg.body = f"Добро пожаловать в SkyTrack Pro, {username}!\n\nВаш email успешно подтверждён."
        
        Thread(target=send_async_email, args=(app, msg)).start()
        logger.info(f"✅ Поток приветствия запущен для {username}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при создании приветствия: {e}")
