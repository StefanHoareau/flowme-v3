from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import httpx
import os
from flowme_states_detection import detect_flowme_state

app = FastAPI()

# Configuration (à adapter selon environnement)
NOCODB_API_KEY = os.getenv("NOCODB_API_KEY")
NOCODB_BASE_ID = os.getenv("NOCODB_BASE_ID")
NOCODB_URL = "https://app.nocodb.com"
STATES_TABLE_ID = "mpcze1flcb4x64x"
REACTIONS_TABLE_ID = "m8lwhj640ohzg7m"

HEADERS = {
    "accept": "application/json",
    "xc-token": NOCODB_API_KEY
}

# Fonction pour charger les états
async def fetch_flowme_states():
    endpoints = [
        f"{NOCODB_URL}/api/v2/bases/{NOCODB_BASE_ID}/tables/{STATES_TABLE_ID}/records",
        f"{NOCODB_URL}/api/v2/tables/{STATES_TABLE_ID}/records"
    ]

    for url in endpoints:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=HEADERS)
                if response.status_code == 200:
                    print(f"✅ États chargés depuis : {url}")
                    return response.json().get("list", [])
                else:
                    print(f"⚠️ Échec {response.status_code} sur {url} – {response.text}")
        except Exception as e:
            print(f"❌ Exception lors de la requête : {e}")

    print("❌ Impossible de charger les états Flowme.")
    return []

# Endpoint principal
@app.post("/chat")
async def analyze_input(request: Request):
    data = await request.json()
    user_input = data.get("message", "")

    # Chargement dynamique des états
    flowme_states = await fetch_flowme_states()
    if not flowme_states:
        return JSONResponse(status_code=500, content={"error": "Échec de chargement des états Flowme."})

    # Détection d’état
    detected_state = detect_flowme_state(user_input, flowme_states)

    # Construction de la réponse
    flowme_reply = f"Je ressens que tu es en état de **{detected_state.get('Nom_État', 'Inconnu')}**."

    # Enregistrement dans la table des réactions
    save_url = f"{NOCODB_URL}/api/v2/bases/{NOCODB_BASE_ID}/tables/{REACTIONS_TABLE_ID}/records"
    payload = {
        "fields": {
            "etat_id_flowme": detected_state.get("ID_État"),
            "etat_nom": detected_state.get("Nom_État"),
            "tension_dominante": detected_state.get("Tension_Dominante"),
            "famille_symbolique": detected_state.get("Famille_Symbolique"),
            "posture_adaptative": detected_state.get("Posture_Adaptative"),
            "message_utilisateur": user_input
        }
    }

    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(save_url, headers=HEADERS, json=payload)
            if res.status_code == 200:
                print("✅ Réaction enregistrée")
            else:
                print(f"⚠️ Erreur enregistrement NocoDB : {res.status_code} – {res.text}")
    except Exception as e:
        print(f"❌ Exception sauvegarde : {e}")

    return {"etat": detected_state.get("Nom_État", "Inconnu"), "reponse": flowme_reply}
