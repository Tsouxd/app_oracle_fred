from flask import Flask, request, jsonify, render_template
import requests

app = Flask(__name__)

# --- CONFIGURATION ---
SIO_API_KEY = "tngtaps6mg2bx9qbmzhkp8ck2uxgafc17fimyce6l1ys8tebg08twqug09ton0xd"
TAG_ID = 1825340 

HEADERS = {
    "X-API-Key": SIO_API_KEY,
    "Content-Type": "application/json"
}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/subscribe', methods=['POST'])
def subscribe():
    try:
        data = request.json
        email = data.get('email')
        firstname = data.get('firstname')
        lastname = data.get('lastname')

        if not email:
            return jsonify({"error": "L'email est requis"}), 400

        # Payload pour le contact (Utilisé pour création et mise à jour)
        contact_payload = {
            "email": email,
            "fields": [
                {"slug": "first_name", "value": firstname},
                {"slug": "surname", "value": lastname}
            ]
        }

        print(f"Tentative pour l'email : {email}")
        
        # 1. ÉTAPE : Création du contact (POST)
        contact_res = requests.post(
            "https://api.systeme.io/api/contacts",
            json=contact_payload,
            headers=HEADERS
        )

        contact_id = None

        if contact_res.status_code in [200, 201]:
            contact_id = contact_res.json().get('id')
            print(f"Nouveau contact créé. ID: {contact_id}")
        
        elif contact_res.status_code == 422:
            # Le contact existe déjà, on le récupère ET on le met à jour via PATCH
            print("Le contact existe déjà, récupération et mise à jour via PATCH...")
            
            # Recherche de l'ID existant
            search_res = requests.get(
                f"https://api.systeme.io/api/contacts?email={email}",
                headers=HEADERS
            )
            
            if search_res.status_code == 200:
                items = search_res.json().get('items', [])
                if items:
                    contact_id = items[0].get('id')
                    
                    # --- MISE À JOUR (PATCH) ---
                    # Il faut changer le Content-Type spécifiquement pour cet appel
                    patch_headers = HEADERS.copy()
                    patch_headers["Content-Type"] = "application/merge-patch+json"
                    
                    update_res = requests.patch(
                        f"https://api.systeme.io/api/contacts/{contact_id}",
                        json=contact_payload,
                        headers=patch_headers
                    )
                    
                    if update_res.status_code in [200, 204]:
                        print(f"Mise à jour réussie pour l'ID: {contact_id}")
                    else:
                        print(f"Échec de l'update : {update_res.status_code} - {update_res.text}")

        # Si on n'a toujours pas d'ID, on s'arrête
        if not contact_id:
            print(f"Erreur API Système.io : {contact_res.text}")
            return jsonify({"error": "Erreur lors du traitement du contact"}), 500

        # 2. ÉTAPE : AJOUT DU TAG
        tag_url = f"https://api.systeme.io/api/contacts/{contact_id}/tags"
        tag_payload = {"tagId": TAG_ID}

        print(f"Ajout du tag {TAG_ID} au contact {contact_id}...")
        
        tag_res = requests.post(
            tag_url,
            json=tag_payload,
            headers=HEADERS
        )

        # On accepte le succès ou le fait que le tag soit déjà présent (422)
        if tag_res.status_code in [200, 201, 204] or tag_res.status_code == 422:
            print("Succès total (Tag assigné ou déjà présent) !")
            return jsonify({"message": "Inscription et tag réussis"}), 200
        else:
            print(f"Erreur lors de l'ajout du tag : {tag_res.text}")
            return jsonify({"message": "Contact traité, erreur tag secondaire"}), 200

    except Exception as e:
        print(f"ERREUR SERVEUR : {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)