
import json
import os
import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Autoriser toutes les origines pour développement
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Variables d'environnement (Render ou .env local)
NOCODB_API_KEY = os.getenv("NOCODB_API_KEY")
NOCODB_URL = os.getenv("NOCODB_URL")
NOCODB_STATES_TABLE_ID = os.getenv("NOCODB_STATES_TABLE_ID")
NOCODB_REACTIONS_TABLE_ID = os.getenv("NOCODB_REACTIONS_TABLE_ID")
ENVIRONMENT = os.getenv("ENVIRONMENT", "production")

# Cache local des états FlowMe
flowme_states = []

@app.on_event("startup")
async def load_states():
    global flowme_states
    try:
        async with httpx.AsyncClient() as client:
            url = f"{NOCODB_URL}/api/v2/tables/{NOCODB_STATES_TABLE_ID}/records"
            headers = {"xc-token": NOCODB_API_KEY, "Accept-Charset": "utf-8"}
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            flowme_states = [
                {
                    "nom": item["Nom_État"],
                    "tension": item.get("Tension_Dominante", ""),
                    "mots_cles": [mot.strip().lower() for mot in item.get("Mots_Clés", "").split(",") if mot.strip()]
                }
                for item in data.get("list", [])
            ]
            print(f"✅ {len(flowme_states)} états chargés depuis NocoDB")
    except Exception as e:
        print("❌ Erreur de chargement des états :", e)

@app.post("/chat")
async def chat(request: Request):
    global flowme_states
    body = await request.json()
    user_input = body.get("message", "").lower()
    emotions = body.get("emotions", [])

    # Détection de l'état dominant
    scores = []
    for state in flowme_states:
        score = sum(1 for mot in state["mots_cles"] if mot in user_input)
        scores.append((score, state))

    scores.sort(reverse=True, key=lambda x: x[0])
    dominant_state = scores[0][1] if scores and scores[0][0] > 0 else {"nom": "Inconnu", "tension": "Non détectée"}

    # Réponse simulée
    response_text = (
        f"🌊 État détecté : **{dominant_state['nom']}**\n"
        f"Tension : {dominant_state['tension']}\n\n"
        "Merci pour ton partage, je suis là pour t'écouter."
    )

    # Sauvegarde dans la table Reactions_Mistral
    try:
        async with httpx.AsyncClient() as client:
            post_url = f"{NOCODB_URL}/api/v2/tables/{NOCODB_REACTIONS_TABLE_ID}/records"
            headers = {"xc-token": NOCODB_API_KEY, "Content-Type": "application/json"}
            payload = {
                "fields": {
                    "message_utilisateur": user_input,
                    "etat_detecte": dominant_state["nom"],
                    "tension": dominant_state["tension"],
                    "reponse_envoyee": response_text,
                    "emotions": ", ".join(emotions),
                }
            }
            await client.post(post_url, headers=headers, json=payload)
    except Exception as e:
        print("⚠️ Échec de la sauvegarde dans NocoDB :", e)

    return {
        "etat": dominant_state["nom"],
        "tension": dominant_state["tension"],
        "reponse": response_text,
    }

@app.get("/health")
def health():
    return {"status": "ok", "states_loaded": len(flowme_states)}
