
import os
import httpx
from fastapi import FastAPI, Request
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# Configuration
nocodb_url = os.getenv("NOCODB_URL")
nocodb_api_key = os.getenv("NOCODB_API_KEY")
nocodb_base_id = os.getenv("NOCODB_BASE_ID")
states_table_id = os.getenv("NOCODB_STATES_TABLE_ID")
reactions_table_id = os.getenv("NOCODB_REACTIONS_TABLE_ID")

headers = {
    "accept": "application/json",
    "xc-token": nocodb_api_key
}

# Chargement des états Flowme
flowme_states = []

async def load_states():
    global flowme_states
    url = f"{nocodb_url}/api/v2/tables/{states_table_id}/records"
    try:
        response = await httpx.AsyncClient().get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            flowme_states = data.get("list", [])
            print(f"📊 États disponibles: {len(flowme_states)}")
        else:
            print(f"❌ Erreur chargement NocoDB (HTTP {response.status_code})")
            print(f"❌ Réponse: {response.text}")
    except Exception as e:
        print(f"❌ Exception lors du chargement des états: {e}")

@app.on_event("startup")
async def startup_event():
    print("🔍 === CHARGEMENT NOCODB AVEC BASE ID ===")
    print(f"🔧 URL NocoDB: {nocodb_url}")
    print(f"🔧 Base ID: {nocodb_base_id}")
    print(f"🔧 API Key: {nocodb_api_key}")
    print(f"🔧 States Table ID: {states_table_id}")
    print(f"🎯 URL avec Table ID: {nocodb_url}/api/v2/tables/{states_table_id}/records")
    await load_states()
    print("✅ Module flowme_states_detection intégré avec succès")
    print("🚀 Démarrage de FlowMe v3")

class UserMessage(BaseModel):
    message: str

@app.post("/chat")
async def chat(user_message: UserMessage):
    detected_state = detect_state(user_message.message)
    print(f"💬 État détecté: {detected_state}")
    await save_reaction(user_message.message, detected_state)
    return {"etat": detected_state, "message": generate_reply(detected_state)}

def detect_state(message: str) -> str:
    for state in flowme_states:
        mot_cle = state.get("Mot_Clé", "").lower()
        if mot_cle in message.lower():
            return state.get("Nom_État", "Présence")
    return "Présence"

def generate_reply(etat: str) -> str:
    if etat == "Présence":
        return "Je suis là avec toi, pleinement."
    elif etat == "Questionnement":
        return "Tu te poses des questions profondes. Parle-moi davantage."
    elif etat == "Éveil":
        return "Quelque chose s'éveille en toi."
    return f"Tu sembles traverser l’état : {etat}"

async def save_reaction(message: str, etat: str):
    url = f"{nocodb_url}/api/v2/bases/{nocodb_base_id}/tables/{reactions_table_id}/records"
    payload = {
        "fields": {
            "etat_nom": etat,
            "message": message
        }
    }
    try:
        response = await httpx.AsyncClient().post(url, headers=headers, json=payload)
        if response.status_code == 200:
            print("✅ Interaction sauvegardée dans NocoDB v2")
        else:
            print(f"❌ Erreur sauvegarde NocoDB: HTTP {response.status_code}")
    except Exception as e:
        print(f"❌ Exception sauvegarde: {e}")
