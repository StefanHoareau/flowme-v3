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

# Configuration sécurisée du logging
logging.basicConfig(
    level=logging.INFO if os.getenv("DEBUG", "false").lower() == "true" else logging.WARNING,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="FlowMe v3", 
    version="3.0.0",
    docs_url="/docs" if os.getenv("ENVIRONMENT") != "production" else None,
    redoc_url="/redoc" if os.getenv("ENVIRONMENT") != "production" else None
)

# Configuration sécurisée depuis les variables d'environnement
def get_secure_env(key: str, default: str = None, required: bool = False) -> str:
    """Récupération sécurisée des variables d'environnement"""
    value = os.getenv(key, default)
    if required and not value:
        logger.error(f"Variable d'environnement requise manquante: {key}")
        raise ValueError(f"Variable d'environnement {key} manquante")
    return value

# Variables d'environnement sécurisées
MISTRAL_API_KEY = get_secure_env("MISTRAL_API_KEY", required=True)
NOCODB_URL = get_secure_env("NOCODB_URL", "https://app.nocodb.com")
NOCODB_API_KEY = get_secure_env("NOCODB_API_KEY")
NOCODB_STATES_TABLE_ID = get_secure_env("NOCODB_STATES_TABLE_ID", "mpcze1flcb4x64x")
NOCODB_REACTIONS_TABLE_ID = get_secure_env("NOCODB_REACTIONS_TABLE_ID", "m8lwhj640ohzg7m")
GITHUB_TOKEN = get_secure_env("GITHUB_TOKEN")
ENVIRONMENT = get_secure_env("ENVIRONMENT", "development")

# États par défaut complets - Système de secours local
LOCAL_FALLBACK_STATES = {
    "Joie": {
        "description": "Sentiment de bonheur et de satisfaction profonde",
        "color": "#FFD700",
        "emoji": "😊",
        "keywords": ["heureux", "content", "joyeux", "super", "génial", "fantastique", "parfait", "ravi"]
    },
    "Tristesse": {
        "description": "Sentiment de mélancolie ou de peine",
        "color": "#4682B4", 
        "emoji": "😢",
        "keywords": ["triste", "malheureux", "déprimé", "mélancolique", "sombre", "peine"]
    },
    "Colère": {
        "description": "Sentiment d'irritation ou de frustration intense",
        "color": "#DC143C",
        "emoji": "😠",
        "keywords": ["énervé", "furieux", "irrité", "en colère", "fâché", "rage"]
    },
    "Peur": {
        "description": "Sentiment d'anxiété ou d'appréhension",
        "color": "#800080",
        "emoji": "😨",
        "keywords": ["peur", "anxieux", "stressé", "inquiet", "nerveux", "angoisse"]
    },
    "Surprise": {
        "description": "Sentiment d'étonnement soudain",
        "color": "#FF6347",
        "emoji": "😲",
        "keywords": ["surpris", "étonné", "choqué", "stupéfait", "ébahi"]
    },
    "Dégoût": {
        "description": "Sentiment de répulsion ou d'aversion",
        "color": "#228B22",
        "emoji": "😒",
        "keywords": ["dégoûté", "écœuré", "répugnant", "horrible"]
    },
    "Amour": {
        "description": "Sentiment d'affection profonde et de tendresse",
        "color": "#FF69B4",
        "emoji": "❤️",
        "keywords": ["amour", "aimer", "affection", "tendresse", "passion", "adorer"]
    },
    "Espoir": {
        "description": "Sentiment d'optimisme et de confiance en l'avenir",
        "color": "#87CEEB",
        "emoji": "🌟",
        "keywords": ["espoir", "optimiste", "confiant", "positif", "encouragé", "motivé"]
    },
    "Nostalgie": {
        "description": "Sentiment de mélancolie liée aux souvenirs du passé",
        "color": "#DDA0DD",
        "emoji": "🌅",
        "keywords": ["nostalgie", "souvenir", "passé", "mélancolie", "regret"]
    },
    "Présence": {
        "description": "État de pleine conscience et d'attention au moment présent",
        "color": "#32CD32",
        "emoji": "🧘",
        "keywords": ["présent", "ici", "maintenant", "conscience", "méditation", "calme"]
    },
    "Curiosité": {
        "description": "Désir de découvrir et d'apprendre",
        "color": "#FF8C00",
        "emoji": "🤔",
        "keywords": ["curieux", "intéressé", "questionne", "découvrir", "apprendre"]
    },
    "Éveil": {
        "description": "État de conscience élargie et de lucidité",
        "color": "#9370DB",
        "emoji": "✨",
        "keywords": ["éveil", "conscient", "lucide", "réalisation", "révélation"]
    },
    "Analyse": {
        "description": "État de réflexion profonde et d'examen détaillé",
        "color": "#4169E1",
        "emoji": "🔍",
        "keywords": ["analyse", "réflexion", "examen", "étude", "comprendre"]
    },
    "Étonnement": {
        "description": "Sentiment de surprise mêlée d'admiration",
        "color": "#FF6B6B",
        "emoji": "😮",
        "keywords": ["étonné", "admiratif", "impressionné", "ébloui"]
    },
    "Sérénité": {
        "description": "État de calme profond et de paix intérieure",
        "color": "#20B2AA",
        "emoji": "🕊️",
        "keywords": ["serein", "paisible", "tranquille", "apaisé", "zen"]
    }
}

class ChatMessage(BaseModel):
    message: str
    user_id: Optional[str] = "anonymous"

class FlowMeStatesDetection:
    def __init__(self, states_data: Dict[str, Any], source: str = "local"):
        self.states = states_data
        self.source = source
        logger.info(f"✅ FlowMe States Detection initialisé - Source: {source}")
        logger.info(f"📊 {len(states_data)} états chargés")
    
    def detect_emotion(self, text: str) -> str:
        """Détection d'émotion basée sur les mots-clés avec fallback intelligent"""
        if not text:
            return "Présence"
            
        text_lower = text.lower().strip()
        
        # Score par émotion
        emotion_scores = {}
        
        for emotion_name, emotion_data in self.states.items():
            score = 0
            keywords = emotion_data.get("keywords", [])
            
            # Calcul du score basé sur les mots-clés
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    # Score pondéré selon la longueur du mot-clé
                    score += len(keyword) * text_lower.count(keyword.lower())
            
            if score > 0:
                emotion_scores[emotion_name] = score
        
        # Retourne l'émotion avec le score le plus élevé
        if emotion_scores:
            best_emotion = max(emotion_scores.items(), key=lambda x: x[1])
            logger.info(f"🎯 Émotion détectée: {best_emotion[0]} (score: {best_emotion[1]})")
            return best_emotion[0]
        
        # Fallback par défaut
        return "Présence"

# Instance globale
flowme_states = None

async def load_nocodb_states_with_fallback():
    """Charge les états depuis NocoDB avec système de secours local robuste"""
    global flowme_states
    
    logger.info("🔍 === CHARGEMENT ÉTATS FLOWME ===")
    
    # Tentative de chargement depuis NocoDB
    if NOCODB_API_KEY and NOCODB_STATES_TABLE_ID:
        try:
            logger.info("🌐 Tentative de connexion à NocoDB...")
            
            headers = {
                "accept": "application/json; charset=utf-8",
                "xc-token": NOCODB_API_KEY
            }
            
            url = f"{NOCODB_URL}/api/v2/tables/{NOCODB_STATES_TABLE_ID}/records"
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, headers=headers)
                
                if response.status_code == 200:
                    data = response.json()
                    records = data.get("list", []) if isinstance(data, dict) else data
                    
                    if records and len(records) > 0:
                        logger.info(f"📡 NocoDB connecté - {len(records)} enregistrements trouvés")
                        
                        # Conversion des données NocoDB
                        nocodb_states = {}
                        for record in records:
                            if isinstance(record, dict):
                                name = record.get("Nom_État")
                                if name:
                                    nocodb_states[name] = {
                                        "description": (record.get("Tension_Dominante") or 
                                                      record.get("Conseil_Flowme") or 
                                                      record.get("Famille_Symbolique") or ""),
                                        "color": record.get("Couleur", "#808080"),
                                        "emoji": record.get("Emoji", "😐"),
                                        "keywords": [name.lower()]  # Mot-clé basique
                                    }
                        
                        if nocodb_states:
                            flowme_states = FlowMeStatesDetection(nocodb_states, "NocoDB")
                            logger.info(f"✅ {len(nocodb_states)} états chargés depuis NocoDB")
                            return
                
                logger.warning(f"⚠️ NocoDB non disponible (HTTP {response.status_code})")
                
        except Exception as e:
            logger.warning(f"⚠️ Erreur connexion NocoDB: {e}")
    
    # Fallback vers les états locaux
    logger.info("🏠 Activation du système de secours local")
    flowme_states = FlowMeStatesDetection(LOCAL_FALLBACK_STATES, "Local Fallback")
    logger.info(f"✅ {len(LOCAL_FALLBACK_STATES)} états locaux chargés")

async def save_to_nocodb_secure(user_message: str, ai_response: str, detected_state: str, user_id: str = "anonymous"):
    """Sauvegarde sécurisée dans NocoDB avec gestion d'erreurs robuste"""
    if not NOCODB_API_KEY or not NOCODB_REACTIONS_TABLE_ID:
        logger.warning("⚠️ Sauvegarde NocoDB désactivée - Configuration manquante")
        return False
    
    try:
        headers = {
            "accept": "application/json",
            "Content-Type": "application/json; charset=utf-8",
            "xc-token": NOCODB_API_KEY
        }
        
        url = f"{NOCODB_URL}/api/v2/tables/{NOCODB_REACTIONS_TABLE_ID}/records"
        
        # Données sécurisées et limitées
        payload = {
            "etat_nom": detected_state[:100],
            "tension_dominante": ai_response[:1000],
            "famille_symbolique": user_message[:500],
            "posture_adaptative": f"User: {user_id} | Source: {flowme_states.source if flowme_states else 'Unknown'}",
            "session_id": user_id[:50],
            "timestamp": datetime.now().isoformat()
        }
        
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            
            if response.status_code in [200, 201]:
                logger.info(f"✅ Interaction sauvegardée (État: {detected_state})")
                return True
            else:
                logger.warning(f"⚠️ Erreur sauvegarde NocoDB: HTTP {response.status_code}")
                return False
                
    except Exception as e:
        logger.warning(f"⚠️ Sauvegarde NocoDB échouée: {e}")
        return False

async def generate_mistral_response_secure(message: str, detected_state: str) -> str:
    """Génération sécurisée de réponse avec Mistral AI"""
    try:
        if not MISTRAL_API_KEY:
            return f"Je comprends que vous ressentez de la {detected_state.lower()}. Comment puis-je vous accompagner dans ce moment ?"
        
        state_info = flowme_states.states.get(detected_state, {})
        state_description = state_info.get("description", detected_state)
        
        # Prompt sécurisé et contextualisé
        system_prompt = f"""Tu es FlowMe, un compagnon IA empathique spécialisé dans le bien-être émotionnel.

L'utilisateur semble ressentir: {detected_state} ({state_description})

Réponds de manière:
- Empathique et bienveillante
- Adaptée à l'état émotionnel détecté  
- Encourageante et constructive
- En français naturel et chaleureux
- Concise (maximum 150 mots)
- Respectueuse et professionnelle

Si le message contient des propos préoccupants, réponds avec bienveillance tout en encourageant à chercher de l'aide professionnelle si nécessaire."""

        headers = {
            "Authorization": f"Bearer {MISTRAL_API_KEY}",
            "Content-Type": "application/json; charset=utf-8"
        }
        
        payload = {
            "model": "mistral-small-latest",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message[:500]}  # Limitation sécurisée
            ],
            "temperature": 0.7,
            "max_tokens": 200,
            "top_p": 0.9
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
                    ai_response = result["choices"][0]["message"]["content"].strip()
                    logger.info(f"✅ Réponse Mistral générée ({len(ai_response)} chars)")
                    return ai_response
                except (KeyError, json.JSONDecodeError):
                    logger.warning("⚠️ Réponse Mistral mal formatée")
            else:
                logger.warning(f"⚠️ Erreur Mistral API: {response.status_code}")
        
    except Exception as e:
        logger.warning(f"⚠️ Erreur génération Mistral: {e}")
    
    # Fallback empathique sécurisé
    fallback_responses = {
        "Joie": "C'est merveilleux de ressentir cette joie ! Profitez pleinement de ce moment positif.",
        "Tristesse": "Je comprends cette tristesse. Prenez le temps dont vous avez besoin, je suis là pour vous écouter.",
        "Colère": "Cette colère semble intense. Respirez profondément et parlons de ce qui vous préoccupe.",
        "Peur": "Cette inquiétude est compréhensible. Explorons ensemble ce qui pourrait vous apaiser.",
        "Présence": "Je sens votre présence attentive. Comment puis-je vous accompagner aujourd'hui ?"
    }
    
    return fallback_responses.get(detected_state, 
        f"Je perçois votre état de {detected_state.lower()}. Parlons de ce que vous ressentez en ce moment.")

@app.on_event("startup")
async def startup_event():
    """Initialisation sécurisée au démarrage"""
    try:
        logger.info(f"🚀 Démarrage FlowMe v3 - Environnement: {ENVIRONMENT}")
        
        await load_nocodb_states_with_fallback()
        
        # Vérification des services
        services_status = {
            "Mistral": "✓ Configuré" if MISTRAL_API_KEY else "✗ Manquant",
            "NocoDB": "✓ Configuré" if NOCODB_API_KEY else "✗ Mode local uniquement",
            "GitHub": "✓ Token configuré" if GITHUB_TOKEN else "✗ Token manquant"
        }
        
        for service, status in services_status.items():
            logger.info(f"🔧 {service}: {status}")
        
        logger.info(f"📊 États disponibles: {len(flowme_states.states)} (Source: {flowme_states.source})")
        logger.info("✅ FlowMe v3 initialisé avec succès")
        
    except Exception as e:
        logger.error(f"💥 Erreur critique au démarrage: {e}")
        raise

@app.get("/", response_class=HTMLResponse)
async def home():
    """Interface FlowMe v3 sécurisée"""
    states_json = json.dumps({
        name: {
            "description": info["description"],
            "color": info["color"], 
            "emoji": info["emoji"]
        }
        for name, info in flowme_states.states.items()
    })
    
    states_count = len(flowme_states.states)
    source_info = flowme_states.source
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <meta name="description" content="FlowMe v3 - Votre compagnon IA pour un bien-être émotionnel optimal">
        <title>FlowMe v3 - Compagnon Émotionnel IA</title>
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
            
            .status-info {{
                background: #f8f9fa;
                border-left: 4px solid #667eea;
                padding: 15px;
                margin-bottom: 20px;
                border-radius: 0 8px 8px 0;
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
                <h1>FlowMe v3</h1>
                <p class="subtitle">Votre compagnon IA pour un bien-être émotionnel optimal</p>
            </div>
            
            <div class="status-info">
                <strong>🔧 État du système :</strong> {states_count} états chargés depuis {source_info}
                {"<br><small>🏠 Mode de secours local actif - Fonctionnement garanti</small>" if source_info == "Local Fallback" else ""}
            </div>
            
            <div class="chat-container" id="chatContainer">
                <div class="ai-message">
                    <strong>FlowMe:</strong> Bonjour ! Je suis FlowMe, votre compagnon IA empathique. 
                    Comment vous sentez-vous aujourd'hui ? Partagez vos émotions avec moi, je suis là pour vous écouter et vous accompagner. 💙
                </div>
            </div>
            
            <div class="typing" id="typing">FlowMe réfléchit...</div>
            
            <div class="input-container">
                <input type="text" id="userInput" placeholder="Exprimez vos émotions ici..." maxlength="500" autocomplete="off">
                <button id="sendButton" onclick="sendMessage()">Envoyer</button>
            </div>
            
            <div class="stats">
                <p><strong>📊 États émotionnels :</strong> {states_count} ({source_info})</p>
            </div>
            
            <div class="states-grid" id="statesGrid">
                <!-- Les états seront générés dynamiquement -->
            </div>
        </div>
        
        <div class="version">FlowMe v3.0 - Sécurisé</div>
        
        <script>
            const states = {states_json};
            let isProcessing = false;
            
            // Génération sécurisée des cartes d'états
            function generateStatesGrid() {{
                const grid = document.getElementById('statesGrid');
                grid.innerHTML = '';
                
                Object.entries(states).forEach(([name, info]) => {{
                    const card = document.createElement('div');
                    card.className = 'state-card';
                    card.style.borderColor = info.color || '#f0f0f0';
                    card.innerHTML = `
                        <div class="state-emoji">${{info.emoji || '😐'}}</div>
                        <div class="state-name">${{name}}</div>
                        <div class="state-description">${{info.description || ''}}</div>
                    `;
                    card.onclick = () => {{
                        const input = document.getElementById('userInput');
                        input.value = `Je me sens ${{name.toLowerCase()}}`;
                        input.focus();
                    }};
                    grid.appendChild(card);
                }});
            }}
            
            // Envoi sécurisé de message
            async function sendMessage() {{
                if (isProcessing) return;
                
                const input = document.getElementById('userInput');
                const message = input.value.trim();
                
                if (!message || message.length < 2) return;
                
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
                            'Content-Type': 'application/json; charset=utf-8'
                        }},
                        body: JSON.stringify({{ message: message }})
                    }});
                    
                    if (response.ok) {{
                        const data = await response.json();
                        
                        if (data.response) {{
                            addMessage(data.response, 'ai', data.detected_state);
                        }} else {{
                            addMessage('Désolé, une erreur est survenue. Pouvez-vous réessayer ?', 'ai');
                        }}
                    }} else {{
                        addMessage('Erreur de connexion. Vérifiez votre connexion internet.', 'ai');
                    }}
                }} catch (error) {{
                    console.error('Erreur:', error);
                    addMessage('Erreur de connexion. Veuillez réessayer.', 'ai');
                }} finally {{
                    isProcessing = false;
                    document.getElementById('sendButton').disabled = false;
                    document.getElementById('typing').classList.remove('show');
                }}
            }}
            
            // Ajout sécurisé de message dans le chat
            function addMessage(text, sender, detectedState = null) {{
                const container = document.getElementById('chatContainer');
                const messageDiv = document.createElement('div');
                messageDiv.className = `message ${{sender}}-message`;
                
                // Échappement XSS basique
                const safeText = text.replace(/</g, '&lt;').replace(/>/g, '&gt;');
                let content = `<strong>${{sender === 'user' ? 'Vous' : 'FlowMe'}}:</strong> ${{safeText}}`;
                
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
            
            // Événements sécurisés
            document.getElementById('userInput').addEventListener('keypress', function(e) {{
                if (e.key === 'Enter' && !e.shiftKey) {{
                    e.preventDefault();
                    sendMessage();
                }}
            }});
            
            // Initialisation sécurisée
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
    """Endpoint principal de chat sécurisé"""
    try:
        # Validation des données d'entrée
        if not chat_message.message or len(chat_message.message.strip()) < 2:
            raise HTTPException(status_code=400, detail="Message trop court")
        
        if len(chat_message.message) > 1000:
            raise HTTPException(status_code=400, detail="Message trop long")
        
        if not flowme_states:
            raise HTTPException(status_code=503, detail="Service FlowMe non disponible")
        
        # Nettoyage du message
        clean_message = chat_message.message.strip()[:500]
        user_id = chat_message.user_id[:50] if chat_message.user_id else "anonymous"
        
        # Détection de l'état émotionnel
        detected_state = flowme_states.detect_emotion(clean_message)
        
        # Génération de la réponse
        ai_response = await generate_mistral_response_secure(clean_message, detected_state)
        
        # Sauvegarde asynchrone (non bloquante)
        await save_to_nocodb_secure(clean_message, ai_response, detected_state, user_id)
        
        return JSONResponse({
            "response": ai_response,
            "detected_state": detected_state,
            "state_info": {
                "description": flowme_states.states.get(detected_state, {}).get("description", ""),
                "color": flowme_states.states.get(detected_state, {}).get("color", "#808080"),
                "emoji": flowme_states.states.get(detected_state, {}).get("emoji", "😐")
            },
            "source": flowme_states.source,
            "timestamp": datetime.now().isoformat()
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"💥 Erreur chat endpoint: {e}")
        return JSONResponse({
            "response": "Je rencontre une difficulté technique temporaire. Pouvez-vous réessayer dans un moment ?",
            "detected_state": "Présence",
            "error": "Service temporairement indisponible",
            "source": "Fallback"
        }, status_code=500)

@app.get("/health")
async def health_check():
    """Vérification de santé sécurisée du service"""
    try:
        health_data = {
            "status": "healthy",
            "version": "3.0.0",
            "timestamp": datetime.now().isoformat(),
            "environment": ENVIRONMENT,
            "states": {
                "count": len(flowme_states.states) if flowme_states else 0,
                "source": flowme_states.source if flowme_states else "unknown"
            },
            "services": {
                "mistral": bool(MISTRAL_API_KEY),
                "nocodb": bool(NOCODB_API_KEY),
                "github": bool(GITHUB_TOKEN)
            }
        }
        
        # Informations sensibles masquées en production
        if ENVIRONMENT != "production":
            health_data["debug"] = {
                "nocodb_url": NOCODB_URL,
                "states_table": NOCODB_STATES_TABLE_ID,
                "reactions_table": NOCODB_REACTIONS_TABLE_ID
            }
        
        return JSONResponse(health_data)
        
    except Exception as e:
        logger.error(f"💥 Erreur health check: {e}")
        return JSONResponse({
            "status": "error",
            "message": "Service health check failed"
        }, status_code=500)

@app.get("/api/states")
async def get_states():
    """API pour récupérer les états disponibles"""
    try:
        if not flowme_states:
            raise HTTPException(status_code=503, detail="États non disponibles")
        
        return JSONResponse({
            "states": {
                name: {
                    "description": info["description"],
                    "color": info["color"],
                    "emoji": info["emoji"]
                }
                for name, info in flowme_states.states.items()
            },
            "count": len(flowme_states.states),
            "source": flowme_states.source,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"💥 Erreur API states: {e}")
        raise HTTPException(status_code=500, detail="Erreur récupération états")

# Middleware de sécurité
@app.middleware("http")
async def security_middleware(request: Request, call_next):
    """Middleware de sécurité pour les requêtes"""
    # Headers de sécurité
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    
    if ENVIRONMENT == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    
    return response

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=port,
        log_level="info" if ENVIRONMENT != "production" else "warning"
    )
                }});
