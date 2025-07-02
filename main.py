import os
import json
import httpx
import logging
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional
import uvicorn
from datetime import datetime

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="FlowMe v3", version="3.0.0")

# Variables d'environnement
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
NOCODB_URL = os.getenv("NOCODB_URL", "https://app.nocodb.com")
NOCODB_API_KEY = os.getenv("NOCODB_API_KEY")
NOCODB_STATES_TABLE_ID = os.getenv("NOCODB_STATES_TABLE_ID", "mpcze1flcb4x64x")
NOCODB_REACTIONS_TABLE_ID = os.getenv("NOCODB_REACTIONS_TABLE_ID", "m8lwhj640ohzg7m")

# États par défaut
LOCAL_FALLBACK_STATES = {
    "Joie": {"description": "Sentiment de bonheur et de satisfaction", "color": "#FFD700", "emoji": "😊"},
    "Tristesse": {"description": "Sentiment de mélancolie ou de peine", "color": "#4682B4", "emoji": "😢"},
    "Colère": {"description": "Sentiment d'irritation ou de frustration", "color": "#DC143C", "emoji": "😠"},
    "Peur": {"description": "Sentiment d'anxiété ou d'appréhension", "color": "#800080", "emoji": "😨"},
    "Surprise": {"description": "Sentiment d'étonnement", "color": "#FF6347", "emoji": "😲"},
    "Dégoût": {"description": "Sentiment de répulsion", "color": "#228B22", "emoji": "😒"},
    "Amour": {"description": "Sentiment d'affection profonde", "color": "#FF69B4", "emoji": "❤️"},
    "Espoir": {"description": "Sentiment d'optimisme pour l'avenir", "color": "#87CEEB", "emoji": "🌟"},
    "Nostalgie": {"description": "Sentiment de mélancolie liée au passé", "color": "#DDA0DD", "emoji": "🌅"},
    "Présence": {"description": "État de pleine conscience et d'attention", "color": "#32CD32", "emoji": "🧘"},
    "Curiosité": {"description": "Désir de découvrir et d'apprendre", "color": "#FF8C00", "emoji": "🤔"},
    "Éveil": {"description": "État de conscience élargie", "color": "#9370DB", "emoji": "✨"},
    "Analyse": {"description": "État de réflexion profonde", "color": "#4169E1", "emoji": "🔍"},
    "Étonnement": {"description": "Surprise mêlée d'admiration", "color": "#FF6B6B", "emoji": "😮"},
    "Sérénité": {"description": "État de calme profond", "color": "#20B2AA", "emoji": "🕊️"}
}

class ChatMessage(BaseModel):
    message: str
    user_id: Optional[str] = "anonymous"

class FlowMeStatesDetection:
    def __init__(self, states_data: Dict[str, Any], source: str = "local"):
        self.states = states_data
        self.source = source
        logger.info(f"✅ FlowMe initialisé - {len(states_data)} états - Source: {source}")
    
    def detect_emotion(self, text: str) -> str:
        text_lower = text.lower()
        keywords = {
            "Joie": ["heureux", "content", "joyeux", "super", "génial", "parfait"],
            "Tristesse": ["triste", "malheureux", "déprimé", "sombre"],
            "Colère": ["énervé", "furieux", "irrité", "en colère", "fâché"],
            "Peur": ["peur", "anxieux", "stressé", "inquiet", "nerveux"],
            "Amour": ["amour", "aimer", "affection", "tendresse"],
            "Espoir": ["espoir", "optimiste", "confiant", "positif"],
            "Présence": ["présent", "ici", "maintenant", "conscience"]
        }
        
        for emotion, words in keywords.items():
            if any(word in text_lower for word in words):
                return emotion
        return "Présence"

# Instance globale
flowme_states = None

async def load_nocodb_states():
    global flowme_states
    
    logger.info("🔍 Chargement des états FlowMe...")
    
    if NOCODB_API_KEY and NOCODB_STATES_TABLE_ID:
        try:
            headers = {"accept": "application/json", "xc-token": NOCODB_API_KEY}
            url = f"{NOCODB_URL}/api/v2/tables/{NOCODB_STATES_TABLE_ID}/records"
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, headers=headers)
                
                if response.status_code == 200:
                    data = response.json()
                    records = data.get("list", []) if isinstance(data, dict) else data
                    
                    if records:
                        nocodb_states = {}
                        for record in records:
                            if isinstance(record, dict):
                                name = record.get("Nom_État")
                                if name:
                                    nocodb_states[name] = {
                                        "description": record.get("Tension_Dominante", ""),
                                        "color": record.get("Couleur", "#808080"),
                                        "emoji": record.get("Emoji", "😐")
                                    }
                        
                        if nocodb_states:
                            flowme_states = FlowMeStatesDetection(nocodb_states, "NocoDB")
                            logger.info(f"✅ {len(nocodb_states)} états chargés depuis NocoDB")
                            return
                
                logger.warning("⚠️ NocoDB non disponible")
        except Exception as e:
            logger.warning(f"⚠️ Erreur NocoDB: {e}")
    
    # Fallback local
    flowme_states = FlowMeStatesDetection(LOCAL_FALLBACK_STATES, "Local")
    logger.info("🏠 États locaux chargés")

async def save_to_nocodb(user_message: str, ai_response: str, detected_state: str, user_id: str):
    if not NOCODB_API_KEY:
        return False
    
    try:
        headers = {
            "accept": "application/json",
            "Content-Type": "application/json",
            "xc-token": NOCODB_API_KEY
        }
        
        url = f"{NOCODB_URL}/api/v2/tables/{NOCODB_REACTIONS_TABLE_ID}/records"
        payload = {
            "etat_nom": detected_state,
            "tension_dominante": ai_response[:1000],
            "famille_symbolique": user_message[:500],
            "session_id": user_id,
            "timestamp": datetime.now().isoformat()
        }
        
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            return response.status_code in [200, 201]
    except:
        return False

async def generate_mistral_response(message: str, detected_state: str) -> str:
    if not MISTRAL_API_KEY:
        return f"Je comprends que vous ressentez de la {detected_state.lower()}. Comment puis-je vous accompagner ?"
    
    try:
        state_info = flowme_states.states.get(detected_state, {})
        state_description = state_info.get("description", detected_state)
        
        system_prompt = f"""Tu es FlowMe, un compagnon IA empathique.

L'utilisateur ressent: {detected_state} ({state_description})

Réponds de manière empathique, bienveillante et encourageante en français (max 150 mots)."""

        headers = {
            "Authorization": f"Bearer {MISTRAL_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "mistral-small-latest",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message}
            ],
            "temperature": 0.7,
            "max_tokens": 200
        }
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                "https://api.mistral.ai/v1/chat/completions",
                headers=headers,
                json=payload
            )
            
            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]["content"].strip()
    except:
        pass
    
    return f"Je comprends votre état de {detected_state.lower()}. Parlons de ce qui vous préoccupe."

@app.on_event("startup")
async def startup_event():
    await load_nocodb_states()
    logger.info("🚀 FlowMe v3 démarré")

@app.get("/", response_class=HTMLResponse)
async def home():
    return HTMLResponse("""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>FlowMe v3</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: Arial, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; display: flex; justify-content: center; align-items: center; padding: 20px; }
            .container { background: rgba(255,255,255,0.95); border-radius: 20px; padding: 40px; max-width: 600px; width: 100%; }
            h1 { text-align: center; color: #333; margin-bottom: 30px; }
            .chat { background: #f8f9fa; border-radius: 15px; padding: 20px; margin-bottom: 20px; min-height: 300px; overflow-y: auto; }
            .message { margin-bottom: 15px; padding: 10px; border-radius: 10px; }
            .user-message { background: #667eea; color: white; margin-left: 20%; }
            .ai-message { background: white; border: 1px solid #ddd; margin-right: 20%; }
            .input-container { display: flex; gap: 10px; }
            input { flex: 1; padding: 12px; border: 2px solid #ddd; border-radius: 10px; }
            button { padding: 12px 24px; background: #667eea; color: white; border: none; border-radius: 10px; cursor: pointer; }
            button:hover { background: #5a6fd8; }
            .status { text-align: center; margin-top: 15px; font-size: 0.9em; color: #666; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🌊💙 FlowMe v3</h1>
            <div class="chat" id="chat">
                <div class="message ai-message">
                    <strong>FlowMe:</strong> Bonjour ! Comment vous sentez-vous aujourd'hui ?
                </div>
            </div>
            <div class="input-container">
                <input type="text" id="input" placeholder="Exprimez vos émotions..." maxlength="500">
                <button onclick="sendMessage()">Envoyer</button>
            </div>
            <div class="status" id="status">FlowMe v3 - Prêt</div>
        </div>
        
        <script>
            let isProcessing = false;
            
            async function sendMessage() {
                if (isProcessing) return;
                const input = document.getElementById('input');
                const message = input.value.trim();
                if (!message) return;
                
                isProcessing = true;
                document.getElementById('status').textContent = 'FlowMe réfléchit...';
                
                addMessage(message, 'user');
                input.value = '';
                
                try {
                    const response = await fetch('/chat', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({message: message})
                    });
                    
                    if (response.ok) {
                        const data = await response.json();
                        addMessage(data.response, 'ai');
                        document.getElementById('status').textContent = `État détecté: ${data.detected_state}`;
                    } else {
                        addMessage('Erreur de connexion.', 'ai');
                    }
                } catch (error) {
                    addMessage('Erreur de connexion.', 'ai');
                } finally {
                    isProcessing = false;
                }
            }
            
            function addMessage(text, sender) {
                const chat = document.getElementById('chat');
                const div = document.createElement('div');
                div.className = `message ${sender}-message`;
                div.innerHTML = `<strong>${sender === 'user' ? 'Vous' : 'FlowMe'}:</strong> ${text}`;
                chat.appendChild(div);
                chat.scrollTop = chat.scrollHeight;
            }
            
            document.getElementById('input').addEventListener('keypress', function(e) {
                if (e.key === 'Enter') sendMessage();
            });
        </script>
    </body>
    </html>
    """)

@app.post("/chat")
async def chat_endpoint(chat_message: ChatMessage):
    try:
        if not flowme_states:
            raise HTTPException(status_code=503, detail="Service non disponible")
        
        clean_message = chat_message.message.strip()[:500]
        user_id = chat_message.user_id[:50] if chat_message.user_id else "anonymous"
        
        detected_state = flowme_states.detect_emotion(clean_message)
        ai_response = await generate_mistral_response(clean_message, detected_state)
        
        # Sauvegarde asynchrone
        await save_to_nocodb(clean_message, ai_response, detected_state, user_id)
        
        return JSONResponse({
            "response": ai_response,
            "detected_state": detected_state,
            "source": flowme_states.source,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Erreur chat: {e}")
        return JSONResponse({
            "response": "Je rencontre une difficulté technique. Pouvez-vous réessayer ?",
            "detected_state": "Présence",
            "error": "Service indisponible"
        }, status_code=500)

@app.get("/health")
async def health_check():
    return JSONResponse({
        "status": "healthy",
        "version": "3.0.0",
        "states_count": len(flowme_states.states) if flowme_states else 0,
        "source": flowme_states.source if flowme_states else "none",
        "timestamp": datetime.now().isoformat()
    })

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
