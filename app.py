from flask import Flask, request, render_template
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import time
import atexit
import signal
import os
import sqlite3
from contextlib import closing

class MonHandler(FileSystemEventHandler):
    def __init__(self, email, server):
        self.email = email
        self.server = server

    def on_modified(self, event):
        self.envoyer_email(f'Le fichier {event.src_path} a été modifié')

    def on_created(self, event):
        self.envoyer_email(f'Le fichier {event.src_path} a été créé')

    def envoyer_email(self, message):
        msg = MIMEMultipart()
        msg['From'] = 'notification@saintjeancapferrat.fr'
        msg['To'] = self.email
        msg['Subject'] = 'Notification de modification de fichier'
        msg.attach(MIMEText(message, 'plain'))
        self.server.send_message(msg)

app = Flask(__name__)
observer = Observer()

def init_db():
    with closing(sqlite3.connect('./database.db')) as conn:
        c = conn.cursor()
        c.execute('CREATE TABLE IF NOT EXISTS watchers (email TEXT, path TEXT, notification_sent INTEGER DEFAULT 0)')
        conn.commit()
        c.execute('SELECT * FROM watchers')
        for row in c.fetchall():
            email, path = row
            server = smtplib.SMTP('smtp.office365.com', 587)
            server.starttls()
            server.login('notification@saintjeancapferrat.fr', os.getenv('EMAIL_PASSWORD'))
            # Ne pas oublier de définir cette variable d'env à la création du conteneur
            event_handler = MonHandler(email, server)
            observer.schedule(event_handler, path=path, recursive=True)
            observer.start()

@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        email = request.form.get('email')
        path = request.form.get('path')
        with closing(sqlite3.connect('./database.db')) as conn:
            c = conn.cursor()
            c.execute('INSERT INTO watchers VALUES (?, ?)', (email, path))
            conn.commit()
        return f"Surveillance programmée pour le dossier {path} avec l'e-mail {email}"
    return render_template('index.html')

@app.route('/start', methods=['POST'])
def start():
    email = request.form.get('email')
    path = request.form.get('path')
    with closing(sqlite3.connect('./database.db')) as conn:
        c = conn.cursor()
        c.execute('SELECT notification_sent FROM watchers WHERE email = ? AND path = ?', (email, path))
        notification_sent = c.fetchone()[0]
        if notification_sent == 0:
            server = smtplib.SMTP('smtp.office365.com', 587)
            server.starttls()
            server.login('notification@saintjeancapferrat.fr', os.getenv('EMAIL_PASSWORD'))
            event_handler = MonHandler(email, server)
            observer.schedule(event_handler, path=path, recursive=True)
            observer.start()
            event_handler.envoyer_email("La surveillance a commencé pour le dossier " + path)
            c.execute('UPDATE watchers SET notification_sent = 1 WHERE email = ? AND path = ?', (email, path))
            conn.commit()
    return f"Surveillance démarrée pour le dossier {path} avec l'e-mail {email}"

@app.route('/stop', methods=['POST'])
def stop():
    email = request.form.get('email')
    path = request.form.get('path')
    with closing(sqlite3.connect('./database.db')) as conn:
        c = conn.cursor()
        c.execute('DELETE FROM watchers WHERE email = ? AND path = ?', (email, path))
        conn.commit()
    server = smtplib.SMTP('smtp.office365.com', 587)
    server.starttls()
    server.login('notification@saintjeancapferrat.fr', os.getenv('EMAIL_PASSWORD'))
    event_handler = MonHandler(email, server)
    observer.unschedule_all()
    event_handler.envoyer_email("La surveillance a été arrêtée pour le dossier " + path)
    return "Surveillance arrêtée"

def stop_observer():
    observer.stop()
    observer.join()

atexit.register(stop_observer)

def signal_handler(signum, frame):
    print(f"Signal {signum} reçu, arrêt de l'observateur...")
    stop_observer()
    os._exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

if __name__ == "__main__":
    init_db()
app.run(debug=True)
