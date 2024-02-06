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
 
class MonHandler(FileSystemEventHandler):
    def __init__(self, email):
self.email = email
 
    def on_modified(self, event):
        self.envoyer_email(f'Le fichier {event.src_path} a été modifié')
 
    def on_created(self, event):
        self.envoyer_email(f'Le fichier {event.src_path} a été créé')
 
    def envoyer_email(self, message):
        msg = MIMEMultipart()
        msg['From'] = 'votre_email@office365.com'
msg['To'] = self.email
        msg['Subject'] = 'Notification de modification de fichier'
        msg.attach(MIMEText(message, 'plain'))
server = smtplib.SMTP('smtp.office365.com', 587)
        server.starttls()
        server.login(msg['From'], 'votre_mot_de_passe')
        server.send_message(msg)
        server.quit()
 
app = Flask(__name__)
observer = Observer()
 
def init_db():
    conn = sqlite3.connect('mon_application/database.db')
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS watchers (email TEXT, path TEXT)')
    conn.commit()
 
    # Démarrer la surveillance pour chaque entrée dans la base de données
    c.execute('SELECT * FROM watchers')
    for row in c.fetchall():
        email, path = row
        event_handler = MonHandler(email)
        observer.schedule(event_handler, path=path, recursive=True)
        observer.start()
 
    conn.close()
 
@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        email = request.form.get('email')
        path = request.form.get('path')
        conn = sqlite3.connect('mon_application/database.db')
        c = conn.cursor()
        c.execute('INSERT INTO watchers VALUES (?, ?)', (email, path))
        conn.commit()
        conn.close()
        return f"Surveillance programmée pour le dossier {path} avec l'e-mail {email}"
    return render_template('index.html')
 
@app.route('/start', methods=['POST'])
def start():
    email = request.form.get('email')
    path = request.form.get('path')
    event_handler = MonHandler(email)
    observer.schedule(event_handler, path=path, recursive=True)
    observer.start()
    return f"Surveillance démarrée pour le dossier {path} avec l'e-mail {email}"
 
@app.route('/stop', methods=['POST'])
def stop():
    observer.unschedule_all()
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