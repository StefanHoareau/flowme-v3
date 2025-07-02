# main.py – FlowMe v3 avec 64 états

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import requests, json, os
from typing import List

app = FastAPI()
flowme_states = []  # cache mémoire

NOCODB_URL = os.getenv("NOCODB_URL", "https://app.nocodb.com")
API_KEY = os.getenv("NOCODB_API_KEY", "")
TABLE_ID = os.getenv("NOCODB_STATES_TABLE_ID", "")
HEADERS = {"xc-token": API_KEY}

# ---------- CHARGEMENT DES ÉTATS ----------
def load_states():
    global flowme_states
    try:
        url = f"{NOCODB_URL}/api/v2/tables/{TABLE_ID}/records?limit=256"
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        items = response.json().get("list", [])

        flowme_states = []
        for item in items:
            mots_cles = item.get("Mots_Clés", "")
            if isinstance(mots_cles, str):
                mots_cles = [k.strip().lower() for k in mots_cles.split(",") if k.strip()]
            flowme_states.append({
                "id": item.get("Id"),
                "nom": item.get("Nom_État", ""),
                "mots_cles": mots_cles
            })
        print(f"✅ {len(flowme_states)} états chargés depuis NocoDB")
    except Exception as e:
        print("⚠️ Erreur chargement états NocoDB :", e)
        flowme_states.clear()

# ---------- DÉTECTION D'ÉTAT ----------
def detect_state(message: str) -> str:
    message_lower = message.lower()
    scores = []

    for etat in flowme_states:
        count = sum(1 for mot in etat["mots_cles"] if mot in message_lower)
        if count > 0:
            scores.append((etat["nom"], count))

    if not scores:
        return "Présence"
    scores.sort(key=lambda x: x[1], reverse=True)
    return scores[0][0]

# ---------- DÉMARRAGE ----------
@app.on_event("startup")
def startup_event():
    load_states()

# ---------- ENDPOINT PRINCIPAL ----------
@app.post("/chat")
async def chat_endpoint(request: Request):
    data = await request.json()
    message = data.get("message", "")
    if not message:
        return JSONResponse({"error": "Message vide"}, status_code=400)

    etat_detecte = detect_state(message)

    # Placeholder réponse IA – à remplacer par ton appel Mistral
    reponse = f"Je ressens l'état de {etat_detecte}. Parle-moi davantage..."

    return {
        "response": reponse,
        "detected_state": etat_detecte,
        "source": "NocoDB"
    }

# ---------- HEALTH CHECK ----------
@app.get("/")
def health():
    return {"status": "ok", "version": "flowme-v3"}

