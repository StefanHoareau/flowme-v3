"""
FlowMe v3 - Fix d'Urgence
Suppression complète de suggest_transition pour résoudre l'erreur d'import
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import uuid
import logging
from datetime import datetime
from typing import Optional, Dict, Any
import os
import httpx
import asyncio

# Configuration logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import sécurisé de la détection d'états
try:
    from flowme_states_detection import detect_consciousness_state, get_state_advice
    STATES_DETECTION_AVAILABLE = True
    logger.info("✅ Module flowme_states_detection importé avec succès")
except ImportError as e:
    logger.warning(f"⚠️ Import partiel flowme_states_detection: {e}")
    STATES_DETECTION_AVAILABLE = False
    
    # Fonctions de fallback ultra-simples
    def detect_consciousness_state(message: str) -> Dict[str, Any]:
        # Détection basique par mots-clés
        msg = message.lower()
        if any(w in msg for w in ["amour", "aime", "tendresse"]):
            return {"state_id": 16, "state_name": "Amour", "confidence": 0.8}
        elif any(w in msg for w in ["confus", "perdu", "trouble"]):
            return {"state_id": 25, "state_name": "Confusion", "confidence": 0.7}
        elif any(w in msg for w in ["violence", "rage", "colère"]):
            return {"state_id": 32, "state_name": "Carnage", "confidence": 0.9}
        else:
            return {"state_id": 1, "state_name": "Présence", "confidence": 0.5}
    
    def get_state_advice(state_id: int) -> str:
        advice_map = {
            1: "Cultivez cette présence consciente, elle ancre dans l'instant.",
            16: "Laissez cette énergie d'amour rayonner, elle transforme tout.",
            25: "Cette confusion est temporaire, l'clarté émergera du chaos.",
            32: "Recherchez de l'aide pour canaliser cette intensité destructrice."
        }
        return advice_map.get(state_id, "Accueillez ce que vous vivez avec bienveillance.")

except Exception as e:
    logger.error(f"❌ Erreur fatale lors de l'import: {e}")
    # On continue quand même avec les fonctions de base
    STATES_DETECTION_AVAILABLE = False
    
    def detect_consciousness_state(message: str) -> Dict[str, Any]:
        return {"state_id": 1, "state_name": "Présence", "confidence": 0.5}
    
    def get_state_advice(state_id: int) -> str:
        return "Je vous accompagne avec bienveillance dans ce moment."

# Configuration FastAPI
app = FastAPI(
    title="FlowMe v3 - Emergency Fix",
    description="IA Empathique - Version de secours fonctionnelle",
    version="3.0.0-emergency"
)

# Configuration des services
MISTRAL_API_KEY = os.getenv('MISTRAL_API_KEY')
NOCODB_URL = os.getenv('NOCODB_URL', 'https://app.nocodb.com')
NOCODB_API_KEY = os.getenv('NOCODB_API_KEY')
NOCODB_REACTIONS_TABLE_ID = os.getenv('NOCODB_REACTIONS_TABLE_ID')

# Vérification de la configuration
MISTRAL_CONFIGURED = bool(MISTRAL_API_KEY)
NOCODB_CONFIGURED = bool(NOCODB_API_KEY and NOCODB_REACTIONS_TABLE_ID)
PRODUCTION_MODE = MISTRAL_CONFIGURED and NOCODB_CONFIGURED

# Modèles Pydantic
class ChatMessage(BaseModel):
    message: str
    session_id: Optional[str] = None

# Cache de session
session_contexts = {}

async def call_mistral_api(prompt: str, user_message: str) -> str:
    """Appel à l'API Mistral AI"""
    if not MISTRAL_CONFIGURED:
        return None
    
    try:
        headers = {
            "Authorization": f"Bearer {MISTRAL_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "mistral-small-latest",
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_message}
            ],
            "temperature": 0.7,
            "max_tokens": 300
        }
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                "https://api.mistral.ai/v1/chat/completions",
                json=payload,
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                return data['choices'][0]['message']['content'].strip()
            else:
                logger.error(f"Erreur API Mistral: {response.status_code}")
                return None
                
    except Exception as e:
        logger.error(f"Erreur appel Mistral: {e}")
        return None

async def save_to_nocodb(session_id: str, user_message: str, detected_state: Dict, ai_response: str) -> bool:
    """Sauvegarde dans NocoDB"""
    if not NOCODB_CONFIGURED:
        return False
    
    try:
        headers = {
            "xc-token": NOCODB_API_KEY,
            "Content-Type": "application/json"
        }
        
        record = {
            "etat_id_flowme": str(detected_state.get('state_id', '')),
            "etat_nom": detected_state.get('state_name', ''),
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat(),
            "pattern_detecte": "FlowMe v3 Emergency",
            "recommandations": ai_response[:400] if ai_response else '',
            "score_bien_etre": 7.0,
            "evolution_tendance": "Interaction en cours"
        }
        
        url = f"{NOCODB_URL}/api/v1/db/data/v1/{NOCODB_REACTIONS_TABLE_ID}"
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=record, headers=headers)
            
            if response.status_code in [200, 201]:
                logger.info("Interaction sauvegardée dans NocoDB")
                return True
            else:
                logger.error(f"Erreur NocoDB: {response.status_code}")
                return False
                
    except Exception as e:
        logger.error(f"Erreur sauvegarde NocoDB: {e}")
        return False

@app.get("/", response_class=HTMLResponse)
async def get_interface():
    """Interface utilisateur - Version d'urgence"""
    
    mode = "PRODUCTION" if PRODUCTION_MODE else "DÉGRADÉ"
    mode_color = "#48bb78" if PRODUCTION_MODE else "#ed8936"
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>FlowMe v3 - IA Empathique</title>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
            }}
            
            .container {{
                background: rgba(255, 255, 255, 0.95);
                border-radius: 20px;
                padding: 30px;
                box-shadow: 0 20px 40px rgba(0,0,0,0.1);
                width: 100%;
                max-width: 500px;
                backdrop-filter: blur(10px);
            }}
            
            .header {{
                text-align: center;
                margin-bottom: 30px;
            }}
            
            .logo {{ font-size: 2.5rem; margin-bottom: 10px; }}
            .title {{
                font-size: 1.8rem;
                color: #4a5568;
                margin-bottom: 5px;
                font-weight: 600;
            }}
            .subtitle {{
                color: #718096;
                font-size: 0.9rem;
                margin-bottom: 15px;
            }}
            .status {{
                display: inline-block;
                padding: 6px 15px;
                background: {mode_color};
                color: white;
                border-radius: 20px;
                font-size: 0.9rem;
                font-weight: 600;
            }}
            .features {{
                display: flex;
                justify-content: center;
                gap: 15px;
                margin: 15px 0;
                font-size: 0.75rem;
                color: #718096;
            }}
            .feature {{
                display: flex;
                align-items: center;
                gap: 3px;
            }}
            .chat-container {{
                margin-bottom: 20px;
                max-height: 350px;
                overflow-y: auto;
                padding: 15px;
                background: #f7fafc;
                border-radius: 10px;
                border: 1px solid #e2e8f0;
            }}
            .message {{
                margin-bottom: 15px;
                padding: 12px;
                border-radius: 10px;
                line-height: 1.5;
            }}
            .user-message {{
                background: linear-gradient(45deg, #667eea, #764ba2);
                color: white;
                margin-left: 20px;
            }}
            .ai-message {{
                background: #e6fffa;
                color: #234e52;
                margin-right: 20px;
                border-left: 4px solid #38b2ac;
            }}
            .state-info {{
                font-size: 0.8rem;
                color: #4a5568;
                margin-top: 5px;
                font-style: italic;
            }}
            .input-container {{
                display: flex;
                gap: 10px;
                margin-bottom: 15px;
            }}
            .message-input {{
                flex: 1;
                padding: 15px;
                border: 2px solid #e2e8f0;
                border-radius: 10px;
                font-size: 1rem;
                transition: border-color 0.3s;
            }}
            .message-input:focus {{
                outline: none;
                border-color: #667eea;
            }}
            .send-button {{
                padding: 15px 25px;
                background: linear-gradient(45deg, #667eea, #764ba2);
                color: white;
                border: none;
                border-radius: 10px;
                cursor: pointer;
                font-weight: 600;
                transition: transform 0.2s;
            }}
            .send-button:hover {{ transform: translateY(-2px); }}
            .send-button:disabled {{
                opacity: 0.6;
                cursor: not-allowed;
                transform: none;
            }}
            .session-info {{
                text-align: center;
                font-size: 0.8rem;
                color: #718096;
                margin-top: 10px;
            }}
            .loading {{
                text-align: center;
                color: #667eea;
                font-style: italic;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="logo">🌊</div>
                <h1 class="title">FlowMe v3</h1>
                <p class="subtitle">IA Empathique - États de Conscience</p>
                <span class="status">🚀 MODE {mode}</span>
                
                <div class="features">
                    <div class="feature">
                        <span>🧠</span> Mistral AI {'✅' if MISTRAL_CONFIGURED else '⚠️'}
                    </div>
                    <div class="feature">
                        <span>💾</span> NocoDB {'✅' if NOCODB_CONFIGURED else '⚠️'}
                    </div>
                    <div class="feature">
                        <span>🎯</span> États {'✅' if STATES_DETECTION_AVAILABLE else '⚠️'}
                    </div>
                </div>
            </div>
            
            <div class="chat-container" id="chat-container">
                <div class="message ai-message">
                    Bonjour ! Je suis FlowMe v3 {'avec Mistral AI' if PRODUCTION_MODE else 'en mode de secours'}. 
                    Partagez ce que vous ressentez, je détecte votre état de conscience et vous accompagne avec empathie. ✨
                    <div class="state-info">💫 Système de détection {'avancé' if STATES_DETECTION_AVAILABLE else 'basique'} actif</div>
                </div>
            </div>
            
            <div class="input-container">
                <input 
                    type="text" 
                    id="message-input" 
                    class="message-input" 
                    placeholder="Partagez ce que vous ressentez..."
                    maxlength="500"
                >
                <button id="send-button" class="send-button">Envoyer</button>
            </div>
            
            <div class="session-info">
                Session: <span id="session-id">Génération...</span>
            </div>
        </div>

        <script>
            let sessionId = localStorage.getItem('flowme_session') || generateSessionId();
            localStorage.setItem('flowme_session', sessionId);
            document.getElementById('session-id').textContent = sessionId.substr(0, 8);
            
            const chatContainer = document.getElementById('chat-container');
            const messageInput = document.getElementById('message-input');
            const sendButton = document.getElementById('send-button');
            
            function generateSessionId() {{
                return 'sess_' + Math.random().toString(36).substr(2, 9) + '_' + Date.now().toString(36);
            }}
            
            function addMessage(content, isUser = false, stateInfo = null) {{
                const messageDiv = document.createElement('div');
                messageDiv.className = `message ${{isUser ? 'user-message' : 'ai-message'}}`;
                
                let html = content;
                if (stateInfo && !isUser) {{
                    html += `<div class="state-info">🎯 ${{stateInfo}}</div>`;
                }}
                
                messageDiv.innerHTML = html;
                chatContainer.appendChild(messageDiv);
                chatContainer.scrollTop = chatContainer.scrollHeight;
            }}
            
            function showLoading() {{
                const loadingDiv = document.createElement('div');
                loadingDiv.className = 'message ai-message loading';
                loadingDiv.id = 'loading-message';
                loadingDiv.innerHTML = '🧠 Analyse de votre état...';
                chatContainer.appendChild(loadingDiv);
                chatContainer.scrollTop = chatContainer.scrollHeight;
            }}
            
            function removeLoading() {{
                const loading = document.getElementById('loading-message');
                if (loading) loading.remove();
            }}
            
            async function sendMessage() {{
                const message = messageInput.value.trim();
                if (!message) return;
                
                addMessage(message, true);
                messageInput.value = '';
                sendButton.disabled = true;
                showLoading();
                
                try {{
                    const response = await fetch('/chat', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify({{
                            message: message,
                            session_id: sessionId
                        }})
                    }});
                    
                    const data = await response.json();
                    removeLoading();
                    
                    if (data.error) {{
                        addMessage(`❌ Erreur: ${{data.error}}`, false);
                    }} else {{
                        const stateInfo = `État ${{data.detected_state.state_id}}: ${{data.detected_state.state_name}}`;
                        addMessage(data.response, false, stateInfo);
                    }}
                }} catch (error) {{
                    removeLoading();
                    addMessage('❌ Erreur de connexion. Veuillez réessayer.', false);
                    console.error(error);
                }} finally {{
                    sendButton.disabled = false;
                    messageInput.focus();
                }}
            }}
            
            sendButton.addEventListener('click', sendMessage);
            messageInput.addEventListener('keypress', (e) => {{
                if (e.key === 'Enter') sendMessage();
            }});
            messageInput.focus();
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.post("/chat")
async def chat_endpoint(message: ChatMessage):
    """Endpoint de chat principal - Version d'urgence"""
    try:
        session_id = message.session_id or str(uuid.uuid4())
        user_message = message.message.strip()
        
        if not user_message:
            raise HTTPException(status_code=400, detail="Message vide")
        
        logger.info(f"[{session_id[:8]}] Message: {user_message[:50]}...")
        
        # 1. Détection d'état
        detected_state = detect_consciousness_state(user_message)
        state_advice = get_state_advice(detected_state['state_id'])
        
        logger.info(f"[{session_id[:8]}] État: {detected_state['state_id']} - {detected_state['state_name']}")
        
        # 2. Génération de réponse
        if MISTRAL_CONFIGURED:
            system_prompt = f"""Tu es un coach empathique spécialisé dans les états de conscience selon Stefan Hoareau.

L'utilisateur exprime l'État {detected_state['state_id']}: {detected_state['state_name']}.

Conseil: {state_advice}

DIRECTIVES:
- Réponds avec empathie et bienveillance
- Évite tout jugement
- Utilise un ton chaleureux
- Maximum 2-3 phrases courtes
- Utilise "tu"

Objectif: Accompagner avec sagesse et compassion."""

            ai_response = await call_mistral_api(system_prompt, user_message)
            if not ai_response:
                ai_response = state_advice
        else:
            ai_response = state_advice
        
        # 3. Sauvegarde NocoDB
        save_success = await save_to_nocodb(session_id, user_message, detected_state, ai_response)
        
        # 4. Réponse
        return JSONResponse({
            "success": True,
            "response": ai_response,
            "detected_state": {
                "state_id": detected_state['state_id'],
                "state_name": detected_state['state_name'],
                "confidence": detected_state.get('confidence', 0.7)
            },
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat(),
            "services_status": {
                "mistral_available": MISTRAL_CONFIGURED,
                "nocodb_saved": save_success,
                "states_detection": STATES_DETECTION_AVAILABLE
            }
        })
        
    except Exception as e:
        logger.error(f"Erreur chat: {e}")
        return JSONResponse({
            "success": False,
            "response": "Je vous accompagne avec bienveillance dans ce moment.",
            "detected_state": {"state_id": 1, "state_name": "Présence", "confidence": 0.5},
            "session_id": session_id or str(uuid.uuid4()),
            "error": "Mode de secours activé"
        })

@app.get("/health")
async def health_check():
    """Status de santé"""
    return {
        "status": "healthy",
        "mode": "emergency_fix",
        "version": "3.0.0-emergency",
        "services": {
            "mistral": {"configured": MISTRAL_CONFIGURED},
            "nocodb": {"configured": NOCODB_CONFIGURED},
            "state_detection": {"available": STATES_DETECTION_AVAILABLE}
        }
    }

@app.on_event("startup")
async def startup_event():
    logger.info("🚀 FlowMe v3 Emergency Fix - Démarrage")
    logger.info(f"Mode: {'Production' if PRODUCTION_MODE else 'Secours'}")
    logger.info(f"Mistral: {'✅' if MISTRAL_CONFIGURED else '❌'}")
    logger.info(f"NocoDB: {'✅' if NOCODB_CONFIGURED else '❌'}")
    logger.info(f"États: {'✅' if STATES_DETECTION_AVAILABLE else '⚠️ Basique'}")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
