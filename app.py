import os
import json
import logging
import time
from datetime import datetime
from flask import Flask, request, jsonify, render_template, session
import requests
import secrets
from dotenv import load_dotenv # <-- IMPORT POUR LE .ENV
from database import get_db_connection # <-- Import de votre database.py

# ==========================================
# CHARGEMENT DU FICHIER .ENV
# ==========================================
load_dotenv()

# ==========================================
# IMPORT GOOGLE SHEETS
# ==========================================
import gspread
from google.oauth2.service_account import Credentials

app = Flask(__name__)
# Utilise la clé du .env ou en génère une aléatoire par défaut
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(16))

# ==========================================
# CONFIGURATION
# ==========================================
# --- GOOGLE SHEETS ---
SHEET_NAME = os.environ.get("SHEET_NAME", "suivi_app_oracle")
SHEET_VISITES_NAME = os.environ.get("SHEET_VISITES_NAME", "stats_visites_oracle")
GOOGLE_CREDS_ENV = os.environ.get("GOOGLE_CREDS_JSON")
CREDENTIALS_FILE = os.environ.get("CREDENTIALS_FILE", "credentials.json")

# --- SYSTEME.IO ---
SIO_API_KEY = os.environ.get("SIO_API_KEY")
SIO_TAG_ID = int(os.environ.get("SIO_TAG_ID", 1825340)) 
HEADERS_SIO = {"X-API-Key": SIO_API_KEY, "Content-Type": "application/json"}

# --- LEARNYBOX ---
# LB_API_KEY = os.environ.get("LB_API_KEY")
# LB_BASE_URL = os.environ.get("LB_BASE_URL", "https://formation-elearning.learnybox.com/api/v2")
# LB_SEQUENCE_ID = int(os.environ.get("LB_SEQUENCE_ID", 280252)) if os.environ.get("LB_SEQUENCE_ID") else 280252
# LB_TOKEN_CACHE = {"access_token": None, "expires_at": 0}

# ==========================================
# LOGGING & UTILS
# ==========================================
logging.basicConfig(level=logging.INFO, format="🔍 [%(levelname)s] %(message)s")
def log(msg): app.logger.info(msg)

def get_utms_from_request():
    return {
        "utm_source": request.args.get('utm_source', ''),
        "utm_medium": request.args.get('utm_medium', ''),
        "utm_campaign": request.args.get('utm_campaign', ''),
        "utm_content": request.args.get('utm_content', ''),
        "utm_term": request.args.get('utm_term', ''),
        "gclid": request.args.get('gclid', '')
    }

# ==========================================
# LEARNYBOX (DÉSACTIVÉ)
# ==========================================
# def get_valid_lb_token():
#     global LB_TOKEN_CACHE
#     now = time.time()
#     if LB_TOKEN_CACHE["access_token"] and LB_TOKEN_CACHE["expires_at"] > (now + 300):
#         return LB_TOKEN_CACHE["access_token"]
#     url = f"{LB_BASE_URL}/oauth/token/"
#     payload = {"grant_type": "access_token"}
#     try:
#         resp = requests.post(url, headers={"X-API-Key": LB_API_KEY, "Content-Type": "application/x-www-form-urlencoded"}, data=payload, verify=False)
#         data = resp.json()
#         if resp.status_code == 200 and "data" in data:
#             LB_TOKEN_CACHE["access_token"] = data["data"]["access_token"]
#             LB_TOKEN_CACHE["expires_at"] = now + int(data["data"]["expires_in"])
#             return LB_TOKEN_CACHE["access_token"]
#     except Exception as e: log(f"LB Token: {e}")
#     return None
# ==========================================

def save_to_gsheets(data_row, target_sheet):
    try:
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]

        # PRIORITÉ À RENDER (variable d’environnement)
        if GOOGLE_CREDS_ENV:
            creds_dict = json.loads(GOOGLE_CREDS_ENV)
            creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
            log("Auth Google Sheets via ENV (Render)")
        else:
            # MODE LOCAL (fichier credentials.json)
            creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scopes)
            log("Auth Google Sheets via fichier local")

        client = gspread.authorize(creds)
        sheet = client.open(target_sheet).sheet1
        sheet.append_row(data_row)
        return True

    except Exception as e:
        log(f"Error Sheet {target_sheet}: {e}")
        return False

# ==========================================
# ROUTES
# ==========================================

@app.route('/')
def index():
    # 1. UTM Capture
    utms = get_utms_from_request()
    if utms['utm_source'] or utms['gclid']:
        session['utm_data'] = utms

    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)

    # 2. Log Visite Technique (stats_visites_oracle)
    save_to_gsheets([current_time, "home_oracle", ip, request.headers.get("User-Agent", "unknown")], SHEET_VISITES_NAME)
    
    # 3. Log Visite Marketing (suivi_app_oracle - 13 colonnes)
    row_visite = [
        current_time, "VISITE", "", f"IP: {ip}", "App Oracle", 
        utms['utm_source'], utms['utm_medium'], utms['utm_campaign'], 
        utms['utm_content'], utms['utm_term'], utms['gclid']
    ]
    save_to_gsheets(row_visite, SHEET_NAME)
    
    return render_template('index.html')

@app.route('/subscribe', methods=['POST'])
def subscribe():
    try:
        data = request.json
        email = data.get('email', '').strip()
        firstname = data.get('firstname', '').strip()
        lastname = data.get('lastname', '').strip() or "Nom"

        if not email: return jsonify({"error": "L'email est requis"}), 400

        utms = session.get('utm_data', {})
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # --- 1. GOOGLE SHEETS (LEAD) ---
        row_lead = [
            current_time, "LEAD", f"{firstname} {lastname}", email, "Inscrit Oracle",
            utms.get('utm_source', 'direct'), utms.get('utm_medium', ''), 
            utms.get('utm_campaign', ''), utms.get('utm_content', ''), 
            utms.get('utm_term', ''), utms.get('gclid', '')
        ]
        save_to_gsheets(row_lead, SHEET_NAME)

        # --- 2. POSTGRES (TABLE DÉDIÉE : resultats_oracle) ---
        conn = get_db_connection()
        if conn:
            try:
                cur = conn.cursor()
                # On crée la table si elle n'existe pas (structure spécifique Oracle)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS resultats_oracle (
                        id SERIAL PRIMARY KEY,
                        username VARCHAR(255),
                        email VARCHAR(255),
                        type_inscription VARCHAR(100),
                        utm_source VARCHAR(100),
                        utm_campaign VARCHAR(100),
                        date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cur.execute("""
                    INSERT INTO resultats_oracle (username, email, type_inscription, utm_source, utm_campaign)
                    VALUES (%s, %s, %s, %s, %s)
                """, (f"{firstname} {lastname}", email, "Inscription Oracle", utms.get('utm_source'), utms.get('utm_campaign')))
                conn.commit()
                log("Postgres : Enregistré dans 'resultats_oracle'")
            except Exception as e: log(f"❌ Postgres Oracle Error: {e}")
            finally: conn.close()

        # --- 3. SYSTEME.IO (VOTRE LOGIQUE) ---
        contact_payload = {"email": email, "fields": [{"slug": "first_name", "value": firstname}, {"slug": "surname", "value": lastname}]}
        contact_res = requests.post("https://api.systeme.io/api/contacts", json=contact_payload, headers=HEADERS_SIO)
        contact_id = None

        if contact_res.status_code in [200, 201]:
            contact_id = contact_res.json().get('id')
        elif contact_res.status_code == 422:
            search_res = requests.get(f"https://api.systeme.io/api/contacts?email={email}", headers=HEADERS_SIO)
            if search_res.status_code == 200:
                items = search_res.json().get('items', [])
                if items:
                    contact_id = items[0].get('id')
                    patch_headers = HEADERS_SIO.copy()
                    patch_headers["Content-Type"] = "application/merge-patch+json"
                    requests.patch(f"https://api.systeme.io/api/contacts/{contact_id}", json=contact_payload, headers=patch_headers)

        if contact_id:
            requests.post(f"https://api.systeme.io/api/contacts/{contact_id}/tags", json={"tagId": SIO_TAG_ID}, headers=HEADERS_SIO)

        # --- 4. LEARNYBOX (DÉSACTIVÉ TEMPORAIREMENT) ---
        # lb_token = get_valid_lb_token()
        # if lb_token:
        #     lb_headers = {"Authorization": f"Bearer {lb_token}"}
        #     requests.post(f"{LB_BASE_URL}/users/", headers=lb_headers, data={"email": email, "fname": firstname, "lname": lastname, "newsletter": "true", "rgpd": "true"}, verify=False)
        #     requests.post(f"{LB_BASE_URL}/mail/contacts/", headers=lb_headers, data={"email": email, "prenom": firstname, "nom": lastname, "id_sequence": LB_SEQUENCE_ID, "rgpd": 1}, verify=False)

        return jsonify({"message": "Inscription réussie"}), 200

    except Exception as e:
        log(f"ERREUR : {e}")
        return jsonify({"error": str(e)}), 500
    
@app.route('/test-db')
def test_db():
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            # On demande la version de Postgres pour être sûr
            cur.execute('SELECT version();')
            db_version = cur.fetchone()
            conn.close()
            return jsonify({
                "status": "success",
                "message": "Connexion à la base de données réussie !",
                "postgres_version": db_version
            }), 200
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500
    else:
        return jsonify({"status": "error", "message": "Impossible de se connecter à la base de données"}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)