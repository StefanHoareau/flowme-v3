
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

NOCODB_URL = os.getenv("NOCODB_URL", "https://app.nocodb.com")
NOCODB_API_KEY = os.getenv("NOCODB_API_KEY")
NOCODB_BASE_ID = os.getenv("NOCODB_BASE_ID")
NOCODB_STATES_TABLE_ID = os.getenv("NOCODB_STATES_TABLE_ID")
NOCODB_REACTIONS_TABLE_ID = os.getenv("NOCODB_REACTIONS_TABLE_ID")

MISTRAL_API_URL = os.getenv("MISTRAL_API_URL", "https://api.mistral.ai/v1/chat/completions")
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")

class Message(BaseModel):
    content: str
    session_id: Optional[str] = "anonymous"

@app.post("/chat")
async def chat_endpoint(message: Message):
    detected_state = {
        "etat_nom": "Présence",
        "tension_dominante": "Latente",
        "famille_symbolique": "Écoute subtile",
        "posture_adaptative": "Accueillir le ressenti",
        "timestamp": "auto",
        "session_id": message.session_id,
        "texte_brut": f"Message utilisateur: {message.content}"
    }

    headers = {"xc-token": NOCODB_API_KEY}
    save_url = f"{NOCODB_URL}/api/v2/tables/{NOCODB_REACTIONS_TABLE_ID}/records"

    try:
        async with httpx.AsyncClient() as client:
            await client.post(save_url, headers=headers, json={"fields": detected_state})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": "Failed to save to NocoDB", "details": str(e)})

    try:
        mistral_headers = {
            "Authorization": f"Bearer {MISTRAL_API_KEY}",
            "Content-Type": "application/json"
        }
        mistral_body = {
            "model": "mistral-tiny",
            "messages": [
                {"role": "system", "content": "You are FlowMe, a kind and emotionally supportive assistant."},
                {"role": "user", "content": message.content}
            ],
            "temperature": 0.7
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(MISTRAL_API_URL, headers=mistral_headers, json=mistral_body)
            response_data = response.json()
            reply = response_data.get("choices", [{}])[0].get("message", {}).get("content", "")

    except Exception as e:
        reply = "Je suis désolé, je ne parviens pas à répondre pour le moment."

    return {"response": reply, "etat_detecte": detected_state["etat_nom"]}

@app.get("/")
def index():
    return {"message": "FlowMe backend is running"}
