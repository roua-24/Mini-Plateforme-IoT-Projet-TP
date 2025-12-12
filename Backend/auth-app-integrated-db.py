"""
SensorFlow Hub - Backend API with Authentification
Backend built with Flask featuring a complete authentication system and sensor management
Auteur: Roua Jendoubi
Date: 2025
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
from datetime import datetime, timedelta
import json
import hashlib
import secrets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from functools import wraps

# Initialise Flask application
app = Flask(__name__)
CORS(app)

# Configuration
DATABASE = 'sensorflow.db'
SECRET_KEY = os.environ.get('SECRET_KEY', 'votre_cle_secrete_changez_moi')

# ============================================
# Security Utilities
# ============================================  

def hash_password(password):
    """
    Hash le mot de passe avec SHA256
    En production, utiliser bcrypt ou argon2!
    """
    return hashlib.sha256(password.encode()).hexdigest()

def generate_token():
    """Génère un token de session sécurisé"""
    return secrets.token_urlsafe(32)

def generate_reset_code():
    """Génère un code de réinitialisation à 6 chiffres"""
    return str(secrets.randbelow(900000) + 100000)

# ============================================
# GESTION DE LA BASE DE DONNÉES
# ============================================

def init_db():
    """Initialise la base de données avec toutes les tables nécessaires"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    # Table des utilisateurs
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_login DATETIME
        )
    ''')
    
    # Table des sessions
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token TEXT UNIQUE NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            expires_at DATETIME NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # Table de réinitialisation de mot de passe
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS password_resets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            reset_code TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            expires_at DATETIME NOT NULL,
            used BOOLEAN DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # Table des lectures de capteurs
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sensor_readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            device_id TEXT NOT NULL,
            temperature REAL NOT NULL,
            humidity REAL NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ Base de données initialisée avec succès!")

def get_db_connection():
    """Établit une connexion à la base de données"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

# ============================================
# DÉCORATEUR D'AUTHENTIFICATION
# ============================================

def require_auth(f):
    """
    Décorateur pour protéger les routes nécessitant une authentification
    Vérifie le token dans le header Authorization
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Récupérer le token depuis le header
        auth_header = request.headers.get('Authorization')
        
        if not auth_header:
            return jsonify({
                'status': 'error',
                'message': 'Token d\'authentification manquant'
            }), 401
        
        # Format attendu: "Bearer <token>"
        try:
            token = auth_header.split(' ')[1]
        except IndexError:
            return jsonify({
                'status': 'error',
                'message': 'Format de token invalide'
            }), 401
        
        # Vérifier le token dans la base de données
        conn = get_db_connection()
        session = conn.execute('''
            SELECT s.*, u.id as user_id, u.username, u.email
            FROM sessions s
            JOIN users u ON s.user_id = u.id
            WHERE s.token = ? AND s.expires_at > datetime('now')
        ''', (token,)).fetchone()
        conn.close()
        
        if not session:
            return jsonify({
                'status': 'error',
                'message': 'Session invalide ou expirée'
            }), 401
        
        # Ajouter les infos utilisateur à la requête
        request.current_user = {
            'id': session['user_id'],
            'username': session['username'],
            'email': session['email']
        }
        
        return f(*args, **kwargs)
    
    return decorated_function

# ============================================
# ROUTES D'AUTHENTIFICATION
# ============================================

@app.route('/api/auth/register', methods=['POST'])
def register():
    """
    Inscription d'un nouvel utilisateur
    Body: { "username": "...", "email": "...", "password": "..." }
    """
    try:
        data = request.get_json()
        
        # Validation des données
        if not all(k in data for k in ['username', 'email', 'password']):
            return jsonify({
                'status': 'error',
                'message': 'Données manquantes'
            }), 400
        
        username = data['username'].strip()
        email = data['email'].strip().lower()
        password = data['password']
        
        # Validation
        if len(username) < 3:
            return jsonify({
                'status': 'error',
                'message': 'Nom d\'utilisateur trop court (min 3 caractères)'
            }), 400
        
        if len(password) < 6:
            return jsonify({
                'status': 'error',
                'message': 'Mot de passe trop court (min 6 caractères)'
            }), 400
        
        # Vérifier si l'utilisateur existe déjà
        conn = get_db_connection()
        existing = conn.execute(
            'SELECT id FROM users WHERE username = ? OR email = ?',
            (username, email)
        ).fetchone()
        
        if existing:
            conn.close()
            return jsonify({
                'status': 'error',
                'message': 'Nom d\'utilisateur ou email déjà utilisé'
            }), 409
        
        # Créer l'utilisateur
        password_hash = hash_password(password)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO users (username, email, password_hash)
            VALUES (?, ?, ?)
        ''', (username, email, password_hash))
        
        user_id = cursor.lastrowid
        conn.commit()
        
        # Créer une session
        token = generate_token()
        expires_at = datetime.now() + timedelta(days=7)
        
        cursor.execute('''
            INSERT INTO sessions (user_id, token, expires_at)
            VALUES (?, ?, ?)
        ''', (user_id, token, expires_at))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'status': 'success',
            'message': 'Inscription réussie',
            'user': {
                'id': user_id,
                'username': username,
                'email': email
            },
            'token': token,
            'expires_at': expires_at.isoformat()
        }), 201
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Erreur lors de l\'inscription: {str(e)}'
        }), 500

@app.route('/api/auth/login', methods=['POST'])
def login():
    """
    Connexion d'un utilisateur
    Body: { "username": "...", "password": "..." }
    """
    try:
        data = request.get_json()
        
        if not all(k in data for k in ['username', 'password']):
            return jsonify({
                'status': 'error',
                'message': 'Identifiants manquants'
            }), 400
        
        username = data['username'].strip()
        password = data['password']
        password_hash = hash_password(password)
        
        # Vérifier les identifiants
        conn = get_db_connection()
        user = conn.execute('''
            SELECT id, username, email, password_hash
            FROM users
            WHERE username = ? AND password_hash = ?
        ''', (username, password_hash)).fetchone()
        
        if not user:
            conn.close()
            return jsonify({
                'status': 'error',
                'message': 'Identifiants incorrects'
            }), 401
        
        # Créer une nouvelle session
        token = generate_token()
        expires_at = datetime.now() + timedelta(days=7)
        
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO sessions (user_id, token, expires_at)
            VALUES (?, ?, ?)
        ''', (user['id'], token, expires_at))
        
        # Mettre à jour last_login
        cursor.execute('''
            UPDATE users SET last_login = datetime('now')
            WHERE id = ?
        ''', (user['id'],))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'status': 'success',
            'message': 'Connexion réussie',
            'user': {
                'id': user['id'],
                'username': user['username'],
                'email': user['email']
            },
            'token': token,
            'expires_at': expires_at.isoformat()
        }), 200
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Erreur de connexion: {str(e)}'
        }), 500

@app.route('/api/auth/logout', methods=['POST'])
@require_auth
def logout():
    """Déconnexion - supprime la session active"""
    try:
        auth_header = request.headers.get('Authorization')
        token = auth_header.split(' ')[1]
        
        conn = get_db_connection()
        conn.execute('DELETE FROM sessions WHERE token = ?', (token,))
        conn.commit()
        conn.close()
        
        return jsonify({
            'status': 'success',
            'message': 'Déconnexion réussie'
        }), 200
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Erreur de déconnexion: {str(e)}'
        }), 500

@app.route('/api/auth/forgot-password', methods=['POST'])
def forgot_password():
    """
    Demande de réinitialisation de mot de passe
    Body: { "email": "..." }
    Envoie un code par email
    """
    try:
        data = request.get_json()
        
        if 'email' not in data:
            return jsonify({
                'status': 'error',
                'message': 'Email manquant'
            }), 400
        
        email = data['email'].strip().lower()
        
        # Vérifier si l'utilisateur existe
        conn = get_db_connection()
        user = conn.execute(
            'SELECT id, username, email FROM users WHERE email = ?',
            (email,)
        ).fetchone()
        
        if not user:
            # Ne pas révéler si l'email existe ou non (sécurité)
            return jsonify({
                'status': 'success',
                'message': 'Si cet email existe, un code de réinitialisation a été envoyé'
            }), 200
        
        # Générer un code de réinitialisation
        reset_code = generate_reset_code()
        expires_at = datetime.now() + timedelta(minutes=10)
        
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO password_resets (user_id, reset_code, expires_at)
            VALUES (?, ?, ?)
        ''', (user['id'], reset_code, expires_at))
        
        conn.commit()
        conn.close()
        
        # TODO: Envoyer le code par email
        # Pour la démo, on retourne le code dans la réponse
        # EN PRODUCTION: Supprimer cette ligne et envoyer vraiment l'email
        
        print(f"📧 Code de réinitialisation pour {email}: {reset_code}")
        
        return jsonify({
            'status': 'success',
            'message': 'Code de réinitialisation envoyé par email',
            'debug_code': reset_code  # À SUPPRIMER EN PRODUCTION!
        }), 200
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Erreur: {str(e)}'
        }), 500

@app.route('/api/auth/verify-reset-code', methods=['POST'])
def verify_reset_code():
    """
    Vérifie le code de réinitialisation
    Body: { "email": "...", "code": "..." }
    """
    try:
        data = request.get_json()
        
        if not all(k in data for k in ['email', 'code']):
            return jsonify({
                'status': 'error',
                'message': 'Données manquantes'
            }), 400
        
        email = data['email'].strip().lower()
        code = data['code'].strip()
        
        conn = get_db_connection()
        
        # Vérifier le code
        reset = conn.execute('''
            SELECT pr.*, u.email
            FROM password_resets pr
            JOIN users u ON pr.user_id = u.id
            WHERE u.email = ? AND pr.reset_code = ?
            AND pr.expires_at > datetime('now') AND pr.used = 0
            ORDER BY pr.created_at DESC
            LIMIT 1
        ''', (email, code)).fetchone()
        
        conn.close()
        
        if not reset:
            return jsonify({
                'status': 'error',
                'message': 'Code invalide ou expiré'
            }), 400
        
        return jsonify({
            'status': 'success',
            'message': 'Code vérifié avec succès',
            'reset_id': reset['id']
        }), 200
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Erreur: {str(e)}'
        }), 500

@app.route('/api/auth/reset-password', methods=['POST'])
def reset_password():
    """
    Réinitialise le mot de passe
    Body: { "email": "...", "code": "...", "new_password": "..." }
    """
    try:
        data = request.get_json()
        
        if not all(k in data for k in ['email', 'code', 'new_password']):
            return jsonify({
                'status': 'error',
                'message': 'Données manquantes'
            }), 400
        
        email = data['email'].strip().lower()
        code = data['code'].strip()
        new_password = data['new_password']
        
        if len(new_password) < 6:
            return jsonify({
                'status': 'error',
                'message': 'Mot de passe trop court'
            }), 400
        
        conn = get_db_connection()
        
        # Vérifier le code
        reset = conn.execute('''
            SELECT pr.*, u.id as user_id
            FROM password_resets pr
            JOIN users u ON pr.user_id = u.id
            WHERE u.email = ? AND pr.reset_code = ?
            AND pr.expires_at > datetime('now') AND pr.used = 0
            ORDER BY pr.created_at DESC
            LIMIT 1
        ''', (email, code)).fetchone()
        
        if not reset:
            conn.close()
            return jsonify({
                'status': 'error',
                'message': 'Code invalide ou expiré'
            }), 400
        
        # Mettre à jour le mot de passe
        new_password_hash = hash_password(new_password)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE users SET password_hash = ?
            WHERE id = ?
        ''', (new_password_hash, reset['user_id']))
        
        # Marquer le code comme utilisé
        cursor.execute('''
            UPDATE password_resets SET used = 1
            WHERE id = ?
        ''', (reset['id'],))
        
        # Supprimer toutes les sessions actives de l'utilisateur
        cursor.execute('''
            DELETE FROM sessions WHERE user_id = ?
        ''', (reset['user_id'],))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'status': 'success',
            'message': 'Mot de passe modifié avec succès'
        }), 200
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Erreur: {str(e)}'
        }), 500

# ============================================
# ROUTES CAPTEURS (PROTÉGÉES)
# ============================================

@app.route('/api/sensors/data', methods=['POST'])
@require_auth
def receive_sensor_data():
    """
    Reçoit les données d'un capteur
    Body: { "device_id": "...", "temperature": ..., "humidity": ... }
    """
    try:
        data = request.get_json()
        user_id = request.current_user['id']
        
        if not all(k in data for k in ['temperature', 'humidity']):
            return jsonify({
                'status': 'error',
                'message': 'Données manquantes'
            }), 400
        
        device_id = data.get('device_id', 'ESP32_DEFAULT')
        temperature = float(data['temperature'])
        humidity = float(data['humidity'])
        
        # Validation
        if not (-40 <= temperature <= 80):
            return jsonify({
                'status': 'error',
                'message': 'Température hors limites'
            }), 400
        
        if not (0 <= humidity <= 100):
            return jsonify({
                'status': 'error',
                'message': 'Humidité hors limites'
            }), 400
        
        # Enregistrer les données
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO sensor_readings (user_id, device_id, temperature, humidity)
            VALUES (?, ?, ?, ?)
        ''', (user_id, device_id, temperature, humidity))
        
        reading_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return jsonify({
            'status': 'success',
            'message': 'Données enregistrées',
            'id': reading_id,
            'timestamp': datetime.now().isoformat()
        }), 201
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Erreur: {str(e)}'
        }), 500

@app.route('/api/sensors/data', methods=['GET'])
@require_auth
def get_sensor_data():
    """
    Récupère les données des capteurs de l'utilisateur
    Query params: limit, device_id
    """
    try:
        user_id = request.current_user['id']
        limit = request.args.get('limit', 100, type=int)
        device_id = request.args.get('device_id', None)
        
        conn = get_db_connection()
        
        if device_id:
            readings = conn.execute('''
                SELECT * FROM sensor_readings
                WHERE user_id = ? AND device_id = ?
                ORDER BY timestamp DESC LIMIT ?
            ''', (user_id, device_id, limit)).fetchall()
        else:
            readings = conn.execute('''
                SELECT * FROM sensor_readings
                WHERE user_id = ?
                ORDER BY timestamp DESC LIMIT ?
            ''', (user_id, limit)).fetchall()
        
        conn.close()
        
        data = [dict(row) for row in readings]
        
        return jsonify({
            'status': 'success',
            'count': len(data),
            'data': data
        }), 200
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Erreur: {str(e)}'
        }), 500

@app.route('/api/sensors/stats', methods=['GET'])
@require_auth
def get_stats():
    """Récupère les statistiques des capteurs de l'utilisateur"""
    try:
        user_id = request.current_user['id']
        
        conn = get_db_connection()
        
        stats = conn.execute('''
            SELECT 
                COUNT(*) as total_readings,
                AVG(temperature) as avg_temp,
                MIN(temperature) as min_temp,
                MAX(temperature) as max_temp,
                AVG(humidity) as avg_hum,
                MIN(humidity) as min_hum,
                MAX(humidity) as max_hum
            FROM sensor_readings
            WHERE user_id = ?
        ''', (user_id,)).fetchone()
        
        conn.close()
        
        return jsonify({
            'status': 'success',
            'statistics': {
                'total_readings': stats['total_readings'],
                'temperature': {
                    'average': round(stats['avg_temp'], 2) if stats['avg_temp'] else 0,
                    'minimum': round(stats['min_temp'], 2) if stats['min_temp'] else 0,
                    'maximum': round(stats['max_temp'], 2) if stats['max_temp'] else 0
                },
                'humidity': {
                    'average': round(stats['avg_hum'], 2) if stats['avg_hum'] else 0,
                    'minimum': round(stats['min_hum'], 2) if stats['min_hum'] else 0,
                    'maximum': round(stats['max_hum'], 2) if stats['max_hum'] else 0
                }
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Erreur: {str(e)}'
        }), 500

# ============================================
# ROUTE RACINE
# ============================================

@app.route('/')
def home():
    """Informations sur l'API"""
    return jsonify({
        'project': 'SensorFlow Hub',
        'version': '2.0',
        'description': 'Plateforme IoT avec authentification',
        'endpoints': {
            'auth': {
                'POST /api/auth/register': 'Inscription',
                'POST /api/auth/login': 'Connexion',
                'POST /api/auth/logout': 'Déconnexion (auth requise)',
                'POST /api/auth/forgot-password': 'Demande de réinitialisation',
                'POST /api/auth/verify-reset-code': 'Vérifier code',
                'POST /api/auth/reset-password': 'Réinitialiser mot de passe'
            },
            'sensors': {
                'POST /api/sensors/data': 'Envoyer données (auth requise)',
                'GET /api/sensors/data': 'Récupérer données (auth requise)',
                'GET /api/sensors/stats': 'Statistiques (auth requise)'
            }
        }
    })

# ============================================
# GESTION DES ERREURS
# ============================================

@app.errorhandler(404)
def not_found(error):
    return jsonify({'status': 'error', 'message': 'Route non trouvée'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'status': 'error', 'message': 'Erreur interne'}), 500

# ============================================
# POINT D'ENTRÉE
# ============================================
    # Initialiser la base de données au démarrage

if __name__ == '__main__':
    init_db()
    
    print("\n" + "="*60)
    print("🚀 SensorFlow Hub API v2.0 - Avec Authentification")
    print("="*60)
    print("📡 Endpoints Authentification:")
    print("   POST   /api/auth/register")
    print("   POST   /api/auth/login")
    print("   POST   /api/auth/logout")
    print("   POST   /api/auth/forgot-password")
    print("   POST   /api/auth/verify-reset-code")
    print("   POST   /api/auth/reset-password")
    print("\n📊 Endpoints Capteurs (authentification requise):")
    print("   POST   /api/sensors/data")
    print("   GET    /api/sensors/data")
    print("   GET    /api/sensors/stats")
    print("="*60 + "\n")
     # Lancement du serveur Flask
    # debug=True pour le développement (désactiver en production)
    app.run(host='0.0.0.0', port=5000, debug=True)