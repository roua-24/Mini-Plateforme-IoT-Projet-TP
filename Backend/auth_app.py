"""
SensorFlow Hub - Backend API Simplifié (Sans BD)
Backend Flask avec authentification en mémoire et collecte temps réel
Auteur: Roua Jendoubi
Date: 2025
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, timedelta
import hashlib
import secrets
from collections import defaultdict

# Initialisation de l'application Flask
app = Flask(__name__)
CORS(app)

# ============================================
# STOCKAGE EN MÉMOIRE
# ============================================

# Dictionnaires pour stocker les données en mémoire
users_db = {}  # {username: {email, password_hash, created_at}}
sessions_db = {}  # {token: {username, expires_at}}
reset_codes_db = {}  # {email: {code, expires_at}}
sensor_data_db = defaultdict(list)  # {username: [readings]}

# ============================================
# UTILITAIRES DE SÉCURITÉ
# ============================================

def hash_password(password):
    """Hash le mot de passe avec SHA256"""
    return hashlib.sha256(password.encode()).hexdigest()

def generate_token():
    """Génère un token de session sécurisé"""
    return secrets.token_urlsafe(32)

def generate_reset_code():
    """Génère un code de réinitialisation à 6 chiffres"""
    return str(secrets.randbelow(900000) + 100000)

def verify_token(token):
    """Vérifie si un token est valide"""
    if token not in sessions_db:
        return None
    
    session = sessions_db[token]
    if datetime.now() > session['expires_at']:
        del sessions_db[token]
        return None
    
    return session['username']

# ============================================
# DÉCORATEUR D'AUTHENTIFICATION
# ============================================

def require_auth(f):
    """Décorateur pour protéger les routes"""
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        
        if not auth_header:
            return jsonify({
                'status': 'error',
                'message': 'Token d\'authentification manquant'
            }), 401
        
        try:
            token = auth_header.split(' ')[1]
        except IndexError:
            return jsonify({
                'status': 'error',
                'message': 'Format de token invalide'
            }), 401
        
        username = verify_token(token)
        if not username:
            return jsonify({
                'status': 'error',
                'message': 'Session invalide ou expirée'
            }), 401
        
        request.current_user = username
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
        if username in users_db:
            return jsonify({
                'status': 'error',
                'message': 'Nom d\'utilisateur déjà utilisé'
            }), 409
        
        if any(u['email'] == email for u in users_db.values()):
            return jsonify({
                'status': 'error',
                'message': 'Email déjà utilisé'
            }), 409
        
        # Créer l'utilisateur
        password_hash = hash_password(password)
        users_db[username] = {
            'email': email,
            'password_hash': password_hash,
            'created_at': datetime.now().isoformat()
        }
        
        # Créer une session
        token = generate_token()
        sessions_db[token] = {
            'username': username,
            'expires_at': datetime.now() + timedelta(days=7)
        }
        
        return jsonify({
            'status': 'success',
            'message': 'Inscription réussie',
            'user': {
                'username': username,
                'email': email
            },
            'token': token
        }), 201
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Erreur: {str(e)}'
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
        if username not in users_db:
            return jsonify({
                'status': 'error',
                'message': 'Identifiants incorrects'
            }), 401
        
        if users_db[username]['password_hash'] != password_hash:
            return jsonify({
                'status': 'error',
                'message': 'Identifiants incorrects'
            }), 401
        
        # Créer une nouvelle session
        token = generate_token()
        sessions_db[token] = {
            'username': username,
            'expires_at': datetime.now() + timedelta(days=7)
        }
        
        return jsonify({
            'status': 'success',
            'message': 'Connexion réussie',
            'user': {
                'username': username,
                'email': users_db[username]['email']
            },
            'token': token
        }), 200
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Erreur: {str(e)}'
        }), 500

@app.route('/api/auth/logout', methods=['POST'])
@require_auth
def logout():
    """Déconnexion - supprime la session active"""
    try:
        auth_header = request.headers.get('Authorization')
        token = auth_header.split(' ')[1]
        
        if token in sessions_db:
            del sessions_db[token]
        
        return jsonify({
            'status': 'success',
            'message': 'Déconnexion réussie'
        }), 200
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Erreur: {str(e)}'
        }), 500

@app.route('/api/auth/forgot-password', methods=['POST'])
def forgot_password():
    """
    Demande de réinitialisation de mot de passe
    Body: { "email": "..." }
    """
    try:
        data = request.get_json()
        
        if 'email' not in data:
            return jsonify({
                'status': 'error',
                'message': 'Email manquant'
            }), 400
        
        email = data['email'].strip().lower()
        
        # Chercher l'utilisateur par email
        user_found = None
        for username, user_data in users_db.items():
            if user_data['email'] == email:
                user_found = username
                break
        
        if not user_found:
            # Ne pas révéler si l'email existe ou non (sécurité)
            return jsonify({
                'status': 'success',
                'message': 'Si cet email existe, un code a été envoyé'
            }), 200
        
        # Générer un code de réinitialisation
        reset_code = generate_reset_code()
        reset_codes_db[email] = {
            'code': reset_code,
            'username': user_found,
            'expires_at': datetime.now() + timedelta(minutes=10)
        }
        
        # EN PRODUCTION: Envoyer par email
        print(f"📧 Code de réinitialisation pour {email}: {reset_code}")
        
        return jsonify({
            'status': 'success',
            'message': 'Code de réinitialisation envoyé',
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
        
        if email not in reset_codes_db:
            return jsonify({
                'status': 'error',
                'message': 'Code invalide ou expiré'
            }), 400
        
        reset_data = reset_codes_db[email]
        
        if datetime.now() > reset_data['expires_at']:
            del reset_codes_db[email]
            return jsonify({
                'status': 'error',
                'message': 'Code expiré'
            }), 400
        
        if reset_data['code'] != code:
            return jsonify({
                'status': 'error',
                'message': 'Code incorrect'
            }), 400
        
        return jsonify({
            'status': 'success',
            'message': 'Code vérifié avec succès'
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
        
        if email not in reset_codes_db:
            return jsonify({
                'status': 'error',
                'message': 'Code invalide ou expiré'
            }), 400
        
        reset_data = reset_codes_db[email]
        
        if datetime.now() > reset_data['expires_at']:
            del reset_codes_db[email]
            return jsonify({
                'status': 'error',
                'message': 'Code expiré'
            }), 400
        
        if reset_data['code'] != code:
            return jsonify({
                'status': 'error',
                'message': 'Code incorrect'
            }), 400
        
        # Mettre à jour le mot de passe
        username = reset_data['username']
        users_db[username]['password_hash'] = hash_password(new_password)
        
        # Supprimer le code et toutes les sessions
        del reset_codes_db[email]
        sessions_to_delete = [token for token, session in sessions_db.items() 
                             if session['username'] == username]
        for token in sessions_to_delete:
            del sessions_db[token]
        
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
# ROUTES CAPTEURS - TEMPS RÉEL UNIQUEMENT
# ============================================

@app.route('/api/sensors/data', methods=['POST'])
@require_auth
def receive_sensor_data():
    """
    Reçoit les données d'un capteur en temps réel
    Les données sont stockées en mémoire (effacées au redémarrage)
    Body: { "device_id": "...", "temperature": ..., "humidity": ... }
    """
    try:
        data = request.get_json()
        username = request.current_user
        
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
                'message': 'Température hors limites (-40 à 80°C)'
            }), 400
        
        if not (0 <= humidity <= 100):
            return jsonify({
                'status': 'error',
                'message': 'Humidité hors limites (0 à 100%)'
            }), 400
        
        # Ajouter la lecture en mémoire
        reading = {
            'id': len(sensor_data_db[username]) + 1,
            'device_id': device_id,
            'temperature': temperature,
            'humidity': humidity,
            'timestamp': datetime.now().isoformat()
        }
        
        # Garder seulement les 100 dernières lectures
        sensor_data_db[username].append(reading)
        if len(sensor_data_db[username]) > 100:
            sensor_data_db[username] = sensor_data_db[username][-100:]
        
        return jsonify({
            'status': 'success',
            'message': 'Données reçues',
            'reading': reading
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
    Récupère les données temps réel stockées en mémoire
    Query params: limit
    """
    try:
        username = request.current_user
        limit = request.args.get('limit', 100, type=int)
        
        data = sensor_data_db[username][-limit:]
        
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
    """Calcule les statistiques des données en mémoire"""
    try:
        username = request.current_user
        readings = sensor_data_db[username]
        
        if not readings:
            return jsonify({
                'status': 'success',
                'statistics': {
                    'total_readings': 0,
                    'temperature': {'average': 0, 'minimum': 0, 'maximum': 0},
                    'humidity': {'average': 0, 'minimum': 0, 'maximum': 0}
                }
            }), 200
        
        temps = [r['temperature'] for r in readings]
        hums = [r['humidity'] for r in readings]
        
        return jsonify({
            'status': 'success',
            'statistics': {
                'total_readings': len(readings),
                'temperature': {
                    'average': round(sum(temps) / len(temps), 2),
                    'minimum': round(min(temps), 2),
                    'maximum': round(max(temps), 2)
                },
                'humidity': {
                    'average': round(sum(hums) / len(hums), 2),
                    'minimum': round(min(hums), 2),
                    'maximum': round(max(hums), 2)
                }
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Erreur: {str(e)}'
        }), 500

@app.route('/api/sensors/clear', methods=['DELETE'])
@require_auth
def clear_sensor_data():
    """Efface toutes les données capteurs de l'utilisateur"""
    try:
        username = request.current_user
        sensor_data_db[username] = []
        
        return jsonify({
            'status': 'success',
            'message': 'Données effacées'
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
        'version': '2.0 - Temps Réel',
        'description': 'Plateforme IoT temps réel (sans base de données)',
        'storage': 'En mémoire - données perdues au redémarrage',
        'endpoints': {
            'auth': {
                'POST /api/auth/register': 'Inscription',
                'POST /api/auth/login': 'Connexion',
                'POST /api/auth/logout': 'Déconnexion',
                'POST /api/auth/forgot-password': 'Demande code',
                'POST /api/auth/verify-reset-code': 'Vérifier code',
                'POST /api/auth/reset-password': 'Nouveau mot de passe'
            },
            'sensors': {
                'POST /api/sensors/data': 'Envoyer données (temps réel)',
                'GET /api/sensors/data': 'Récupérer données',
                'GET /api/sensors/stats': 'Statistiques',
                'DELETE /api/sensors/clear': 'Effacer données'
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

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🚀 SensorFlow Hub API v2.0 - Temps Réel (Sans BD)")
    print("="*60)
    print("⚠️  Données stockées EN MÉMOIRE uniquement")
    print("⚠️  Les données seront perdues au redémarrage du serveur")
    print("\n📡 Endpoints Authentification:")
    print("   POST   /api/auth/register")
    print("   POST   /api/auth/login")
    print("   POST   /api/auth/logout")
    print("   POST   /api/auth/forgot-password")
    print("   POST   /api/auth/verify-reset-code")
    print("   POST   /api/auth/reset-password")
    print("\n📊 Endpoints Capteurs (temps réel):")
    print("   POST   /api/sensors/data")
    print("   GET    /api/sensors/data")
    print("   GET    /api/sensors/stats")
    print("   DELETE /api/sensors/clear")
    print("="*60 + "\n")
    
    app.run(host='0.0.0.0', port=5000, debug=True)