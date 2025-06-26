import os
import json
import httpx
import logging
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
import uvicorn
from datetime import datetime

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="FlowMe v3", version="3.0.0")

# Configuration depuis les variables d'environnement
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
NOCODB_URL = os.getenv("NOCODB_URL", "https://app.nocodb.com")
NOCODB_API_KEY = os.getenv("NOCODB_API_KEY")
NOCODB_STATES_TABLE_ID = os.getenv("NOCODB_STATES_TABLE_ID", "mpcze1f1cb4x64x")
NOCODB_REACTIONS_TABLE_ID = os.getenv("NOCODB_REACTIONS_TABLE_ID", "m8lwhj640ohzg7m")

# États par défaut (fallback si NocoDB ne répond pas)
DEFAULT_STATES = {
    "Joie": {"description": "Sentiment de bonheur et de satisfaction", "color": "#FFD700", "emoji": "😊"},
    "Tristesse": {"description": "Sentiment de mélancolie ou de peine", "color": "#4682B4", "emoji": "😢"},
    "Colère": {"description": "Sentiment d'irritation ou de frustration", "color": "#DC143C", "emoji": "😠"},
    "Peur": {"description": "Sentiment d'anxiété ou d'appréhension", "color": "#800080", "emoji": "😨"},
    "Surprise": {"description": "Sentiment d'étonnement", "color": "#FF6347", "emoji": "😲"},
    "Dégoût": {"description": "Sentiment de répulsion", "color": "#228B22", "emoji": "😒"},
    "Amour": {"description": "Sentiment d'affection profonde", "color": "#FF69B4", "emoji": "❤️"},
    "Espoir": {"description": "Sentiment d'optimisme pour l'avenir", "color": "#87CEEB", "emoji": "🌟"},
    "Nostalgie": {"description": "Sentiment de mélancolie liée au passé", "color": "#DDA0DD", "emoji": "🌅"},
    "Présence": {"description": "État de pleine conscience et d'attention", "color": "#32CD32", "emoji": "🧘"}
}

class ChatMessage(BaseModel):
    message: str
    user_id: Optional[str] = "anonymous"

class FlowMeStatesDetection:
    def __init__(self, states_data: Dict[str, Any]):
        self.states = states_data
        logger.info(f"✅ Module flowme_states_detection intégré avec succès")
    
    def detect_emotion(self, text: str) -> str:
        """Détection simple d'émotion basée sur des mots-clés"""
        text_lower = text.lower()
        
        # Mots-clés pour chaque émotion
        keywords = {
            "Joie": ["heureux", "content", "joyeux", "super", "génial", "fantastique", "parfait"],
            "Tristesse": ["triste", "malheureux", "déprimé", "mélancolique", "sombre"],
            "Colère": ["énervé", "furieux", "irrité", "en colère", "fâché"],
            "Peur": ["peur", "anxieux", "stressé", "inquiet", "nerveux"],
            "Amour": ["amour", "aimer", "affection", "tendresse", "passion"],
            "Espoir": ["espoir", "optimiste", "confiant", "positif", "encouragé"],
            "Présence": ["présent", "ici", "maintenant", "conscience", "méditation"]
        }
        
        for emotion, words in keywords.items():
            if any(word in text_lower for word in words):
                return emotion
        
        return "Présence"  # État par défaut

# Instance globale
flowme_states = None

async def test_nocodb_endpoints():
    """Test de différents endpoints NocoDB pour diagnostic"""
    if not NOCODB_API_KEY:
        logger.error("🔴 NOCODB_API_KEY manquante")
        return
    
    headers = {
        "accept": "application/json",
        "xc-token": NOCODB_API_KEY
    }
    
    test_urls = [
        f"{NOCODB_URL}/api/v2/tables/{NOCODB_STATES_TABLE_ID}/records",
        f"{NOCODB_URL}/api/v2/tables/{NOCODB_REACTIONS_TABLE_ID}/records",
        f"{NOCODB_URL}/api/v1/db/data/noco/{NOCODB_STATES_TABLE_ID}",
        f"{NOCODB_URL}/api/v2/meta/tables/{NOCODB_STATES_TABLE_ID}",
    ]
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        for i, url in enumerate(test_urls):
            try:
                logger.info(f"🧪 Test {i+1}: {url}")
                response = await client.get(url, headers=headers)
                logger.info(f"📊 Réponse {i+1}: HTTP {response.status_code}")
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        logger.info(f"✅ Données reçues: {len(str(data))} caractères")
                        if isinstance(data, dict) and "list" in data:
                            logger.info(f"📋 Nombre d'enregistrements: {len(data.get('list', []))}")
                        elif isinstance(data, list):
                            logger.info(f"📋 Nombre d'enregistrements: {len(data)}")
                    except:
                        logger.info(f"📄 Réponse texte: {response.text[:200]}...")
                else:
                    logger.warning(f"❌ Erreur {response.status_code}: {response.text[:200]}")
                    
            except Exception as e:
                logger.error(f"💥 Exception test {i+1}: {e}")

async def load_nocodb_states():
    """Charge les états depuis NocoDB v2 avec diagnostic complet"""
    global flowme_states
    
    logger.info("🔍 === DIAGNOSTIC NOCODB COMPLET ===")
    logger.info(f"🔧 URL NocoDB: {NOCODB_URL}")
    logger.info(f"🔧 API Key: {NOCODB_API_KEY[:10]}...{NOCODB_API_KEY[-10:] if NOCODB_API_KEY else 'MANQUANTE'}")
    logger.info(f"🔧 States Table ID: {NOCODB_STATES_TABLE_ID}")
    logger.info(f"🔧 Reactions Table ID: {NOCODB_REACTIONS_TABLE_ID}")
    
    # Test des endpoints
    await test_nocodb_endpoints()
    
    if not NOCODB_API_KEY or not NOCODB_STATES_TABLE_ID:
        logger.warning("⚠️ Configuration NocoDB manquante, utilisation états par défaut")
        flowme_states = FlowMeStatesDetection(DEFAULT_STATES)
        return
    
    try:
        headers = {
            "accept": "application/json",
            "xc-token": NOCODB_API_KEY
        }
        
        # Essai principal avec l'API v2
        url = f"{NOCODB_URL}/api/v2/tables/{NOCODB_STATES_TABLE_ID}/records"
        logger.info(f"🎯 Tentative principale: {url}")
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url, headers=headers)
            
            logger.info(f"📡 Status Code: {response.status_code}")
            logger.info(f"📡 Headers: {dict(response.headers)}")
            logger.info(f"📡 Response Text: {response.text[:500]}...")
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"🎉 Succès! Type de données: {type(data)}")
                
                # Traitement des données NocoDB v2
                states_dict = {}
                records = data.get("list", []) if isinstance(data, dict) else data
                
                logger.info(f"📋 Nombre d'enregistrements trouvés: {len(records)}")
                
                for i, record in enumerate(records[:3]):  # Log des 3 premiers pour debug
                    logger.info(f"📝 Enregistrement {i+1}: {record}")
                
                for record in records:
                    if isinstance(record, dict):
                        # Essai de différents noms de colonnes
                        name = (record.get("État") or 
                               record.get("Nom") or 
                               record.get("Name") or 
                               record.get("etat_nom") or
                               record.get("titre") or
                               record.get("Title"))
                        
                        if name:
                            states_dict[name] = {
                                "description": (record.get("Description") or 
                                              record.get("description") or ""),
                                "color": (record.get("Couleur") or 
                                         record.get("couleur") or 
                                         record.get("Color") or "#808080"),
                                "emoji": (record.get("Emoji") or 
                                         record.get("emoji") or "😐")
                            }
                
                if states_dict:
                    flowme_states = FlowMeStatesDetection(states_dict)
                    logger.info(f"🎉 {len(states_dict)} états FlowMe chargés depuis NocoDB v2")
                    logger.info(f"📋 États chargés: {list(states_dict.keys())[:5]}")
                else:
                    logger.warning("⚠️ Aucun état valide trouvé dans les données NocoDB")
                    flowme_states = FlowMeStatesDetection(DEFAULT_STATES)
                    
            else:
                logger.error(f"❌ Échec chargement NocoDB (HTTP {response.status_code})")
                logger.error(f"❌ Réponse complète: {response.text}")
                flowme_states = FlowMeStatesDetection(DEFAULT_STATES)
                
    except Exception as e:
        logger.error(f"💥 Erreur connexion NocoDB: {e}")
        import traceback
        logger.error(f"💥 Traceback: {traceback.format_exc()}")
        flowme_states = FlowMeStatesDetection(DEFAULT_STATES)

async def save_to_nocodb(user_message: str, ai_response: str, detected_state: str, user_id: str = "anonymous"):
    """Sauvegarde l'interaction dans NocoDB v2"""
    if not NOCODB_API_KEY or not NOCODB_REACTIONS_TABLE_ID:
        return False
    
    try:
        headers = {
            "accept": "application/json",
            "Content-Type": "application/json",
            "xc-token": NOCODB_API_KEY
        }
        
        url = f"{NOCODB_URL}/api/v2/tables/{NOCODB_REACTIONS_TABLE_ID}/records"
        
        payload = {
            "User_Message": user_message[:500],
            "AI_Response": ai_response[:1000],
            "Detected_State": detected_state,
            "User_ID": user_id,
            "Timestamp": datetime.now().isoformat()
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            
            if response.status_code in [200, 201]:
                logger.info("✅ Interaction sauvegardée dans NocoDB v2")
                return True
            else:
                logger.error(f"❌ Erreur sauvegarde NocoDB: HTTP {response.status_code}")
                return False
                
    except Exception as e:
        logger.error(f"❌ Erreur sauvegarde NocoDB: {e}")
        return False

async def generate_mistral_response(message: str, detected_state: str) -> str:
    """Génère une réponse empathique avec Mistral AI"""
    if not MISTRAL_API_KEY:
        return f"Je comprends que vous ressentez de la {detected_state.lower()}. Comment puis-je vous accompagner ?"
    
    try:
        state_info = flowme_states.states.get(detected_state, {})
        state_description = state_info.get("description", detected_state)
        
        system_prompt = f"""Tu es FlowMe, un compagnon IA empathique spécialisé dans le bien-être émotionnel.
        
L'utilisateur semble ressentir: {detected_state} ({state_description})

Réponds de manière:
- Empathique et bienveillante
- Adaptée à l'état émotionnel détecté
- Encourageante et positive
- En français, de façon naturelle et chaleureuse
- Maximum 150 mots

Ton but est d'offrir un soutien émotionnel authentique."""

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
                try:
                    result = response.json()
                    return result["choices"][0]["message"]["content"].strip()
                except (KeyError, json.JSONDecodeError) as e:
                    logger.warning("Réponse Mistral non-JSON")
                    return f"Je sens que vous traversez un moment de {detected_state.lower()}. Je suis là pour vous écouter et vous accompagner. Que ressentez-vous en ce moment ?"
            else:
                logger.error(f"Erreur Mistral API: {response.status_code}")
                return f"Je perçois votre état de {detected_state.lower()}. Comment puis-je vous aider à mieux vous sentir ?"
                
    except Exception as e:
        logger.error(f"Erreur génération réponse: {e}")
        return f"Je comprends votre ressenti. Parlons de ce qui vous préoccupe en ce moment."

@app.on_event("startup")
async def startup_event():
    """Initialisation au démarrage"""
    await load_nocodb_states()
    logger.info("🚀 Démarrage de FlowMe v3")
    logger.info(f"✅ Mistral API: {'✓ Configuré' if MISTRAL_API_KEY else '✗ Manquant'}")
    logger.info(f"✅ NocoDB: {'✓ Configuré' if NOCODB_API_KEY else '✗ Manquant'}")
    logger.info(f"🔧 States Table ID: {NOCODB_STATES_TABLE_ID}")
    logger.info(f"🔧 Reactions Table ID: {NOCODB_REACTIONS_TABLE_ID}")
    logger.info(f"📊 États disponibles: {len(flowme_states.states) if flowme_states else 0}")

@app.get("/", response_class=HTMLResponse)
async def home():
    """Page d'accueil FlowMe v3"""
    states_json = json.dumps(flowme_states.states if flowme_states else DEFAULT_STATES)
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>FlowMe v3 - Votre Compagnon Émotionnel IA</title>
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                justify-content: center;
                align-items: center;
                padding: 20px;
            }}
            
            .container {{
                background: rgba(255, 255, 255, 0.95);
                border-radius: 20px;
                padding: 40px;
                box-shadow: 0 20px 40px rgba(0,0,0,0.1);
                max-width: 800px;
                width: 100%;
                backdrop-filter: blur(10px);
            }}
            
            .header {{
                text-align: center;
                margin-bottom: 40px;
            }}
            
            .logo {{
                font-size: 3em;
                margin-bottom: 10px;
            }}
            
            h1 {{
                color: #333;
                font-size: 2.5em;
                margin-bottom: 10px;
                background: linear-gradient(45deg, #667eea, #764ba2);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
            }}
            
            .subtitle {{
                color: #666;
                font-size: 1.2em;
                margin-bottom: 30px;
            }}
            
            .debug-info {{
                background: #f8f9fa;
                border: 1px solid #e9ecef;
                border-radius: 8px;
                padding: 15px;
                margin-bottom: 20px;
                font-family: monospace;
                font-size: 0.9em;
            }}
            
            .chat-container {{
                background: #f8f9fa;
                border-radius: 15px;
                padding: 30px;
                margin-bottom: 30px;
                max-height: 400px;
                overflow-y: auto;
            }}
            
            .message {{
                margin-bottom: 20px;
                padding: 15px;
                border-radius: 12px;
                animation: fadeIn 0.5s ease-in;
            }}
            
            .user-message {{
                background: linear-gradient(45deg, #667eea, #764ba2);
                color: white;
                margin-left: 20%;
                border-bottom-right-radius: 5px;
            }}
            
            .ai-message {{
                background: white;
                color: #333;
                margin-right: 20%;
                border: 1px solid #e0e0e0;
                border-bottom-left-radius: 5px;
            }}
            
            .state-indicator {{
                display: inline-block;
                padding: 5px 12px;
                border-radius: 20px;
                font-size: 0.9em;
                font-weight: bold;
                margin-top: 10px;
                color: white;
            }}
            
            .input-container {{
                display: flex;
                gap: 15px;
                margin-bottom: 20px;
            }}
            
            #userInput {{
                flex: 1;
                padding: 15px;
                border: 2px solid #e0e0e0;
                border-radius: 12px;
                font-size: 1.1em;
                transition: border-color 0.3s;
            }}
            
            #userInput:focus {{
                outline: none;
                border-color: #667eea;
            }}
            
            #sendButton {{
                padding: 15px 30px;
                background: linear-gradient(45deg, #667eea, #764ba2);
                color: white;
                border: none;
                border-radius: 12px;
                font-size: 1.1em;
                cursor: pointer;
                transition: transform 0.2s;
            }}
            
            #sendButton:hover {{
                transform: translateY(-2px);
            }}
            
            #sendButton:disabled {{
                opacity: 0.6;
                cursor: not-allowed;
                transform: none;
            }}
            
            .states-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 15px;
                margin-top: 20px;
            }}
            
            .state-card {{
                background: white;
                padding: 20px;
                border-radius: 12px;
                border: 2px solid #f0f0f0;
                text-align: center;
                transition: transform 0.2s, box-shadow 0.2s;
                cursor: pointer;
            }}
            
            .state-card:hover {{
                transform: translateY(-5px);
                box-shadow: 0 10px 20px rgba(0,0,0,0.1);
            }}
            
            .state-emoji {{
                font-size: 2em;
                margin-bottom: 10px;
            }}
            
            .state-name {{
                font-weight: bold;
                color: #333;
                margin-bottom: 5px;
            }}
            
            .state-description {{
                font-size: 0.9em;
                color: #666;
            }}
            
            @keyframes fadeIn {{
                from {{ opacity: 0; transform: translateY(20px); }}
                to {{ opacity: 1; transform: translateY(0); }}
            }}
            
            .typing {{
                display: none;
                padding: 15px;
                color: #666;
                font-style: italic;
            }}
            
            .typing.show {{
                display: block;
            }}
            
            .stats {{
                text-align: center;
                margin-top: 20px;
                padding: 20px;
                background: #f8f9fa;
                border-radius: 12px;
            }}
            
            .version {{
                position: fixed;
                bottom: 10px;
                right: 10px;
                background: rgba(0,0,0,0.7);
                color: white;
                padding: 5px 10px;
                border-radius: 5px;
                font-size: 0.8em;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="logo">🌊💙</div>
                <h1>FlowMe v3 - Debug</h1>
                <p class="subtitle">Diagnostic complet de la connexion NocoDB</p>
            </div>
            
            <div class="debug-info">
                <strong>🔍 Informations de Debug:</strong><br>
                API Key: {NOCODB_API_KEY[:10] if NOCODB_API_KEY else 'MANQUANTE'}...{NOCODB_API_KEY[-10:] if NOCODB_API_KEY else ''}<br>
                States Table ID: {NOCODB_STATES_TABLE_ID}<br>
                États chargés: {len(flowme_states.states) if flowme_states else 0}<br>
                URL Test: {NOCODB_URL}/api/v2/tables/{NOCODB_STATES_TABLE_ID}/records
            </div>
            
            <div class="chat-container" id="chatContainer">
                <div class="ai-message">
                    <strong>FlowMe:</strong> Version DEBUG active ! Consultez les logs pour voir les détails de connexion NocoDB. 
                    Les états disponibles: {len(flowme_states.states) if flowme_states else len(DEFAULT_STATES)}
                </div>
            </div>
            
            <div class="typing" id="typing">FlowMe réfléchit...</div>
            
            <div class="input-container">
                <input type="text" id="userInput" placeholder="Testez une émotion..." maxlength="500">
                <button id="sendButton" onclick="sendMessage()">Test</button>
            </div>
            
            <div class="stats">
                <p><strong>📊 États émotionnels:</strong> {len(flowme_states.states) if flowme_states else len(DEFAULT_STATES)} (Mode: {'NocoDB' if len(flowme_states.states if flowme_states else []) > 10 else 'Défaut'})</p>
            </div>
            
            <div class="states-grid" id="statesGrid">
                <!-- Les états seront générés dynamiquement -->
            </div>
        </div>
        
        <div class="version">FlowMe v3.0 - DEBUG</div>
        
        <script>
            const states = {states_json};
            let isProcessing = false;
            
            // Génération des cartes d'états
            function generateStatesGrid() {{
                const grid = document.getElementById('statesGrid');
                grid.innerHTML = '';
                
                Object.entries(states).forEach(([name, info]) => {{
                    const card = document.createElement('div');
                    card.className = 'state-card';
                    card.style.borderColor = info.color;
                    card.innerHTML = `
                        <div class="state-emoji">${{info.emoji || '😐'}}</div>
                        <div class="state-name">${{name}}</div>
                        <div class="state-description">${{info.description || ''}}</div>
                    `;
                    card.onclick = () => {{
                        document.getElementById('userInput').value = `Je me sens ${{name.toLowerCase()}}`;
                        document.getElementById('userInput').focus();
                    }};
                    grid.appendChild(card);
                }});
            }}
            
            // Envoi de message
            async function sendMessage() {{
                if (isProcessing) return;
                
                const input = document.getElementById('userInput');
                const message = input.value.trim();
                
                if (!message) return;
                
                isProcessing = true;
                document.getElementById('sendButton').disabled = true;
                document.getElementById('typing').classList.add('show');
                
                // Affichage du message utilisateur
                addMessage(message, 'user');
                input.value = '';
                
                try {{
                    const response = await fetch('/chat', {{
                        method: 'POST',
                        headers: {{
                            'Content-Type': 'application/json'
                        }},
                        body: JSON.stringify({{ message: message }})
                    }});
                    
                    const data = await response.json();
                    
                    if (data.response) {{
                        addMessage(data.response, 'ai', data.detected_state);
                    }} else {{
                        addMessage('Erreur de traitement. Consultez les logs serveur.', 'ai');
                    }}
                }} catch (error) {{
                    console.error('Erreur:', error);
                    addMessage('Erreur de connexion.', 'ai');
                }} finally {{
                    isProcessing = false;
                    document.getElementById('sendButton').disabled = false;
                    document.getElementById('typing').classList.remove('show');
                }}
            }}
            
            // Ajout de message dans le chat
            function addMessage(text, sender, detectedState = null) {{
                const container = document.getElementById('chatContainer');
                const messageDiv = document.createElement('div');
                messageDiv.className = `message ${{sender}}-message`;
                
                let content = `<strong>${{sender === 'user' ? 'Vous' : 'FlowMe'}}:</strong> ${{text}}`;
                
                if (detectedState && states[detectedState]) {{
                    const stateInfo = states[detectedState];
                    content += `<div class="state-indicator" style="background-color: ${{stateInfo.color}}">
                        ${{stateInfo.emoji || '😐'}} État détecté: ${{detectedState}}
                    </div>`;
                }}
                
                messageDiv.innerHTML = content;
                container.appendChild(messageDiv);
                container.scrollTop = container.scrollHeight;
            }}
            
            // Événement touche Entrée
            document.getElementById('userInput').addEventListener('keypress', function(e) {{
                if (e.key === 'Enter' && !e.shiftKey) {{
                    e.preventDefault();
                    sendMessage();
                }}
            }});
            
            // Initialisation
            document.addEventListener('DOMContentLoaded', function() {{
                generateStatesGrid();
                document.getElementById('userInput').focus();
            }});
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.post("/chat")
async def chat_endpoint(chat_message: ChatMessage):
    """Endpoint principal de chat"""
    try:
        if not flowme_states:
            raise HTTPException(status_code=500, detail="Service FlowMe non initialisé")
        
        # Détection de l'état émotionnel
        detected_state = flowme_states.detect_emotion(chat_message.message)
        logger.info(f"💬 État détecté: {detected_state}")
        
        # Génération de la réponse
        ai_response = await generate_mistral_response(chat_message.message, detected_state)
        
        # Sauvegarde asynchrone
        await save_to_nocodb(
            chat_message.message, 
            ai_response, 
            detected_state, 
            chat_message.user_id
        )
        
        return JSONResponse({
            "response": ai_response,
            "detected_state": detected_state,
            "state_info": flowme_states.states.get(detected_state, {}),
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Erreur chat endpoint: {e}")
        return JSONResponse({
            "response": "Je rencontre une difficulté technique. Consultez les logs pour plus de détails.",
            "detected_state": "Présence",
            "error": str(e)
        }, status_code=500)

@app.get("/health")
async def health_check():
    """Vérification de santé du service"""
    return JSONResponse({
        "status": "healthy",
        "version": "3.0.0-debug",
        "states_loaded": len(flowme_states.states) if flowme_states else 0,
        "mistral_configured": bool(MISTRAL_API_KEY),
        "nocodb_configured": bool(NOCODB_API_KEY),
        "debug_info": {
            "nocodb_url": NOCODB_URL,
            "states_table_id": NOCODB_STATES_TABLE_ID,
            "reactions_table_id": NOCODB_REACTIONS_TABLE_ID,
            "api_key_present": bool(NOCODB_API_KEY),
            "api_key_preview": f"{NOCODB_API_KEY[:10]}...{NOCODB_API_KEY[-5:]}" if NOCODB_API_KEY else "MISSING"
        },
        "timestamp": datetime.now().isoformat()
    })

@app.get("/debug/nocodb")
async def debug_nocodb():
    """Endpoint de debug spécifique pour NocoDB"""
    await test_nocodb_endpoints()
    return JSONResponse({
        "message": "Tests NocoDB terminés. Consultez les logs pour les résultats détaillés.",
        "timestamp": datetime.now().isoformat()
    })

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
