"""
FlowMe v3 - Version Flask Ultra-Simple
Compatible Python 3.13 - Pas de Pydantic !
"""

from flask import Flask, request, jsonify, render_template_string
import os
import logging
import uuid
from datetime import datetime
import httpx
import asyncio
import json

# Configuration logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Application Flask
app = Flask(__name__)

# Configuration des services
MISTRAL_API_KEY = os.getenv('MISTRAL_API_KEY')
NOCODB_API_KEY = os.getenv('NOCODB_API_KEY')
NOCODB_URL = os.getenv('NOCODB_URL', 'https://app.nocodb.com')
NOCODB_REACTIONS_TABLE_ID = os.getenv('NOCODB_REACTIONS_TABLE_ID')

# Vérifications
PRODUCTION_MODE = bool(MISTRAL_API_KEY and NOCODB_API_KEY)

# États de conscience
STATES = {
    1: {"name": "Présence", "advice": "Cultivez cette présence consciente, elle ancre dans l'instant."},
    8: {"name": "Résonance", "advice": "Cette harmonie connecte profondément, laissez-la vous porter."},
    16: {"name": "Amour", "advice": "Laissez cette énergie d'amour rayonner, elle transforme tout."},
    22: {"name": "Compassion", "advice": "Votre empathie guérit et apaise, c'est un don précieux."},
    25: {"name": "Confusion", "advice": "Cette confusion est temporaire, l'clarté émergera du chaos."},
    32: {"name": "Carnage", "advice": "Recherchez de l'aide pour canaliser cette intensité destructrice."},
    58: {"name": "Inclusion", "advice": "Vous intégrez les contradictions avec sagesse, c'est une force."}
}

def detect_state_simple(message: str) -> dict:
    """Détection d'état simplifiée mais efficace"""
    msg = message.lower()
    
    # Détection par patterns
    if any(w in msg for w in ["présent", "ici", "maintenant", "attention", "conscient"]):
        return {"state_id": 1, "state_name": "Présence"}
    elif any(w in msg for w in ["harmonie", "résonance", "accord", "vibration", "connexion"]):
        return {"state_id": 8, "state_name": "Résonance"}
    elif any(w in msg for w in ["amour", "aime", "affection", "tendresse", "cœur"]):
        return {"state_id": 16, "state_name": "Amour"}
    elif any(w in msg for w in ["compassion", "empathie", "comprends", "bienveillance"]):
        return {"state_id": 22, "state_name": "Compassion"}
    elif any(w in msg for w in ["confus", "perdu", "trouble", "mélange", "flou"]):
        return {"state_id": 25, "state_name": "Confusion"}
    elif any(w in msg for w in ["violence", "rage", "colère", "tuer", "détruit", "carnage"]):
        return {"state_id": 32, "state_name": "Carnage"}
    elif any(w in msg for w in ["contradiction", "paradoxe", "complexe", "nuance", "intègre"]):
        return {"state_id": 58, "state_name": "Inclusion"}
    else:
        # État par défaut basé sur le sentiment général
        if any(w in msg for w in ["bien", "heureux", "joie", "content"]):
            return {"state_id": 8, "state_name": "Résonance"}
        elif any(w in msg for w in ["mal", "triste", "difficile", "dur"]):
            return {"state_id": 25, "state_name": "Confusion"}
        else:
            return {"state_id": 1, "state_name": "Présence"}

async def call_mistral_async(prompt: str, message: str) -> str:
    """Appel Mistral AI asynchrone"""
    if not MISTRAL_API_KEY:
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
                {"role": "user", "content": message}
            ],
            "temperature": 0.7,
            "max_tokens": 250
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
                logger.error(f"Mistral error: {response.status_code}")
                return None
                
    except Exception as e:
        logger.error(f"Mistral exception: {e}")
        return None

def call_mistral(prompt: str, message: str) -> str:
    """Wrapper synchrone pour Mistral"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(call_mistral_async(prompt, message))
    except Exception as e:
        logger.error(f"Mistral sync error: {e}")
        return None
    finally:
        loop.close()

async def save_to_nocodb_async(session_id: str, message: str, state: dict, response: str) -> bool:
    """Sauvegarde NocoDB asynchrone"""
    if not (NOCODB_API_KEY and NOCODB_REACTIONS_TABLE_ID):
        return False
    
    try:
        headers = {
            "xc-token": NOCODB_API_KEY,
            "Content-Type": "application/json"
        }
        
        record = {
            "etat_id_flowme": str(state["state_id"]),
            "etat_nom": state["state_name"],
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat(),
            "pattern_detecte": "FlowMe v3 Flask",
            "recommandations": response[:400] if response else "",
            "score_bien_etre": 7.0,
            "evolution_tendance": "Interaction en cours"
        }
        
        url = f"{NOCODB_URL}/api/v1/db/data/v1/{NOCODB_REACTIONS_TABLE_ID}"
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=record, headers=headers)
            
            if resp.status_code in [200, 201]:
                logger.info("Interaction sauvegardée dans NocoDB")
                return True
            else:
                logger.error(f"NocoDB error: {resp.status_code}")
                return False
                
    except Exception as e:
        logger.error(f"NocoDB error: {e}")
        return False

def save_to_nocodb(session_id: str, message: str, state: dict, response: str) -> bool:
    """Wrapper synchrone pour NocoDB"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(save_to_nocodb_async(session_id, message, state, response))
    except Exception as e:
        logger.error(f"NocoDB sync error: {e}")
        return False
    finally:
        loop.close()

@app.route('/')
def get_interface():
    """Interface principale"""
    
    mode = "PRODUCTION" if PRODUCTION_MODE else "DÉGRADÉ"
    color = "#48bb78" if PRODUCTION_MODE else "#ed8936"
    
    html_template = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>FlowMe v3 - IA Empathique</title>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                font-family: 'Segoe UI', sans-serif;
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
            .header {{ text-align: center; margin-bottom: 30px; }}
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
                background: {color};
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
                <p class="subtitle">IA Empathique - États de Conscience Stefan Hoareau</p>
                <span class="status">🚀 MODE {mode}</span>
                
                <div class="features">
                    <div class="feature">
                        <span>🧠</span> Mistral AI {'✅' if MISTRAL_API_KEY else '⚠️'}
                    </div>
                    <div class="feature">
                        <span>💾</span> NocoDB {'✅' if NOCODB_API_KEY else '⚠️'}
                    </div>
                    <div class="feature">
                        <span>🎯</span> États ✅
                    </div>
                    <div class="feature">
                        <span>⚡</span> Flask ✅
                    </div>
                </div>
            </div>
            
            <div class="chat-container" id="chat-container">
                <div class="message ai-message">
                    Bonjour ! Je suis FlowMe v3 {'avec Mistral AI' if PRODUCTION_MODE else 'en mode local'}. 
                    Partagez ce que vous ressentez, je détecte votre état de conscience et vous accompagne avec empathie. ✨
                    <div class="state-info">💫 Détection des états de conscience active (Flask)</div>
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
                loadingDiv.innerHTML = '🧠 Analyse de votre état de conscience...';
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
    
    return html_template

@app.route('/chat', methods=['POST'])
def chat_endpoint():
    """Endpoint de chat principal"""
    try:
        data = request.get_json()
        
        if not data or not data.get('message'):
            return jsonify({"success": False, "error": "Message requis"}), 400
        
        session_id = data.get('session_id') or str(uuid.uuid4())
        user_message = data['message'].strip()
        
        logger.info(f"[{session_id[:8]}] Message: {user_message[:50]}...")
        
        # 1. Détection d'état
        detected_state = detect_state_simple(user_message)
        state_advice = STATES.get(detected_state["state_id"], {}).get("advice", "Accueillez ce que vous vivez avec bienveillance.")
        
        logger.info(f"[{session_id[:8]}] État détecté: {detected_state['state_id']} - {detected_state['state_name']}")
        
        # 2. Génération de réponse
        if MISTRAL_API_KEY:
            prompt = f"""Tu es un coach empathique spécialisé dans les états de conscience selon Stefan Hoareau.

L'utilisateur exprime actuellement l'état "{detected_state['state_name']}".

Conseil contextualisé: {state_advice}

DIRECTIVES:
- Réponds avec empathie et bienveillance profonde
- Évite tout jugement ou critique
- Utilise un ton chaleureux et compréhensif
- Maximum 2-3 phrases courtes mais profondes
- Utilise "tu" pour créer la proximité

Objectif: Accompagner l'utilisateur avec sagesse et compassion."""
            
            ai_response = call_mistral(prompt, user_message)
            if not ai_response:
                ai_response = state_advice
        else:
            ai_response = state_advice
        
        # 3. Sauvegarde NocoDB
        saved = save_to_nocodb(session_id, user_message, detected_state, ai_response)
        
        return jsonify({
            "success": True,
            "response": ai_response,
            "detected_state": detected_state,
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat(),
            "services": {
                "mistral": bool(MISTRAL_API_KEY),
                "nocodb_saved": saved
            }
        })
        
    except Exception as e:
        logger.error(f"Chat error: {e}")
        return jsonify({
            "success": False,
            "response": "Je rencontre une difficulté technique mais je reste à votre écoute avec bienveillance.",
            "error": str(e)
        })

@app.route('/health')
def health_check():
    """Status de santé"""
    return jsonify({
        "status": "healthy",
        "mode": "production" if PRODUCTION_MODE else "degraded",
        "version": "3.0.0-flask-stable",
        "services": {
            "mistral": {"configured": bool(MISTRAL_API_KEY)},
            "nocodb": {"configured": bool(NOCODB_API_KEY)},
            "state_detection": {"available": True, "method": "pattern_matching"}
        },
        "technical": {
            "framework": "Flask",
            "python_compatible": "3.13+",
            "no_pydantic": True
        }
    })

@app.route('/states')
def states_info():
    """Information sur les états disponibles"""
    return jsonify({
        "available_states": len(STATES),
        "states": {k: v["name"] for k, v in STATES.items()},
        "detection_method": "Pattern matching + sentiment analysis",
        "architecture": "Stefan Hoareau - États de Conscience"
    })

if __name__ == "__main__":
    logger.info("🚀 FlowMe v3 Flask - Démarrage")
    logger.info(f"Mode: {'Production' if PRODUCTION_MODE else 'Dégradé'}")
    logger.info(f"Mistral: {'✅' if MISTRAL_API_KEY else '❌'}")
    logger.info(f"NocoDB: {'✅' if NOCODB_API_KEY else '❌'}")
    logger.info("Framework: Flask (compatible Python 3.13)")
    
    port = int(os.getenv("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=False)
