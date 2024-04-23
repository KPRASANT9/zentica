from flask import Flask
from flask_mail import Mail, Message

app = Flask(__name__)
app.config['MAIL_SERVER'] = 'smtp.example.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'your-email@example.com'
app.config['MAIL_PASSWORD'] = 'your-email-password'
mail = Mail(app)


def send_notification(email, subject, message):
    msg = Message(subject, sender=app.config['MAIL_USERNAME'], recipients=[email])
    msg.body = message
    mail.send(msg)
