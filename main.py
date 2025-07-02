import os
import json
import httpx
import logging
import time
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional
import uvicorn
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from dataclasses import dataclass, asdict

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========== SYSTÈME DE MONITORING ==========
@dataclass
class ConversationMetrics:
    session_id: str
    user_id: str
    start_time: datetime
    end_time: Optional[datetime]
    message_count: int
    emotions_detected: list
    average_response_time: float

@dataclass
class SystemHealthMetrics:
    timestamp: datetime
    nocodb_status: bool
    mistral_status: bool
    response_times: Dict[str, float]
    error_count: int
    active_sessions: int

class FlowMeAnalytics:
    def __init__(self):
        self.conversations: Dict[str, ConversationMetrics] = {}
        self.health_history = []
        self.emotion_stats = Counter()
        self.error_log = []
        self.system_start_time = datetime.now()
        
    def start_conversation(self, session_id: str, user_id: str = "anonymous"):
        self.conversations[session_id] = ConversationMetrics(
            session_id=session_id,
            user_id=user_id,
            start_time=datetime.now(),
            end_time=None,
            message_count=0,
            emotions_detected=[],
            average_response_time=0.0
        )
        
    def log_message(self, session_id: str, emotion: str, response_time: float):
        if session_id in self.conversations:
            conv = self.conversations[session_id]
            conv.message_count += 1
            conv.emotions_detected.append(emotion)
            
            current_avg = conv.average_response_time
            conv.average_response_time = (current_avg * (conv.message_count - 1) + response_time) / conv.message_count
            
            self.emotion_stats[emotion] += 1
    
    def log_system_health(self, nocodb_status: bool, mistral_status: bool, 
                         response_times: Dict[str, float], error_count: int):
        health = SystemHealthMetrics(
            timestamp=datetime.now(),
            nocodb_status=nocodb_status,
            mistral_status=mistral_status,
            response_times=response_times,
            error_count=error_count,
            active_sessions=len([c for c in self.conversations.values() if c.end_time is None])
        )
        
        self.health_history.append(health)
        
        # Garder seulement les 24 dernières heures
        cutoff = datetime.now() - timedelta(hours=24)
        self.health_history = [h for h in self.health_history if h.timestamp > cutoff]
    
    def log_error(self, error_type: str, error_message: str, session_id: str = None):
        self.error_log.append({
            'timestamp': datetime.now(),
            'type': error_type,
            'message': error_message,
            'session_id': session_id
        })
        
        if len(self.error_log) > 100:
            self.error_log = self.error_log[-100:]
    
    def get_analytics_summary(self) -> Dict[str, Any]:
        now = datetime.now()
        uptime = (now - self.system_start_time).total_seconds()
        
        # Calculer l'uptime système
        system_uptime = 100.0
        if self.health_history:
            total_checks = len(self.health_history)
            successful = sum(1 for h in self.health_history if h.nocodb_status and h.mistral_status)
            system_uptime = (successful / total_checks) * 100 if total_checks > 0 else 100.0
        
        # Temps de réponse moyen
        avg_response_time = 0.0
        if self.conversations:
            response_times = [c.average_response_time for c in self.conversations.values() if c.average_response_time > 0]
            avg_response_time = sum(response_times) / len(response_times) if response_times else 0.0
        
        return {
            "uptime_seconds": uptime,
            "total_conversations": len(self.conversations),
            "active_conversations": len([c for c in self.conversations.values() if c.end_time is None]),
            "total_messages": sum(c.message_count for c in self.conversations.values()),
            "system_uptime_percent": round(system_uptime, 2),
            "average_response_time": round(avg_response_time, 2),
            "top_emotions": dict(self.emotion_stats.most_common(5)),
            "recent_errors": len([e for e in self.error_log if e['timestamp'] > now - timedelta(hours=1)])
        }

# ========== APPLICATION PRINCIPALE ==========

app = FastAPI(title="FlowMe v3", version="3.0.0")

# Variables d'environnement
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
NOCODB_URL = os.getenv("NOCODB_URL", "https://app.nocodb.com")
NOCODB_API_KEY = os.getenv("NOCODB_API_KEY")
NOCODB_STATES_TABLE_ID = os.getenv("NOCODB_STATES_TABLE_ID", "mpcze1flcb4x64x")
NOCODB_REACTIONS_TABLE_ID = os.getenv("NOCODB_REACTIONS_TABLE_ID", "m8lwhj640ohzg7m")

# États par défaut - VERSION SIMPLIFIÉE pour fallback seulement
LOCAL_FALLBACK_STATES = {
    "Joie": {"description": "Sentiment de bonheur et de satisfaction", "color": "#FFD700", "emoji": "😊"},
    "Tristesse": {"description": "Sentiment de mélancolie ou de peine", "color": "#4682B4", "emoji": "😢"},
    "Colère": {"description": "Sentiment d'irritation ou de frustration", "color": "#DC143C", "emoji": "😠"},
    "Peur": {"description": "Sentiment d'anxiété ou d'appréhension", "color": "#800080", "emoji": "😨"},
    "Amour": {"description": "Sentiment d'affection profonde", "color": "#FF69B4", "emoji": "❤️"},
    "Présence": {"description": "État de pleine conscience et d'attention", "color": "#32CD32", "emoji": "🧘"}
}

class ChatMessage(BaseModel):
    message: str
    user_id: Optional[str] = "anonymous"

class EnhancedFlowMeStatesDetection:
    def __init__(self, states_data: Dict[str, Any], source: str = "local"):
        self.states = states_data
        self.source = source
        # Stockage des données complètes NocoDB pour Mistral
        self.nocodb_full_data = {}
        logger.info(f"✅ FlowMe initialisé - {len(states_data)} états - Source: {source}")
    
    def set_nocodb_data(self, nocodb_data: Dict[str, Any]):
        """Stocke les données complètes NocoDB pour Mistral"""
        self.nocodb_full_data = nocodb_data
        logger.info(f"📊 Données NocoDB complètes chargées pour Mistral: {len(nocodb_data)} états")
    
    def detect_emotion(self, text: str) -> str:
        """Détection d'émotion améliorée avec scoring"""
        text_lower = text.lower()
        
        # Mots-clés étendus pour chaque émotion
        emotion_keywords = {
            "Joie": {
                "primary": ["heureux", "content", "joyeux", "rayonnant", "épanoui"],
                "secondary": ["super", "génial", "parfait", "excellent", "formidable"],
                "context": ["sourire", "rire", "célébrer", "victoire", "succès"]
            },
            "Tristesse": {
                "primary": ["triste", "malheureux", "déprimé", "abattu", "mélancolique"],
                "secondary": ["sombre", "morose", "désespéré", "découragé"],
                "context": ["pleurer", "larmes", "chagrin", "peine", "deuil"]
            },
            "Colère": {
                "primary": ["énervé", "furieux", "irrité", "fâché", "exaspéré"],
                "secondary": ["agacé", "contrarié", "remonté", "ulcéré"],
                "context": ["rage", "violence", "injustice", "révolte", "frustration"]
            },
            "Peur": {
                "primary": ["peur", "anxieux", "stressé", "inquiet", "terrorisé"],
                "secondary": ["nerveux", "angoissé", "préoccupé", "troublé"],
                "context": ["panique", "phobique", "danger", "menace", "insécurité"]
            },
            "Amour": {
                "primary": ["amour", "aimer", "adorer", "chérir", "passion"],
                "secondary": ["affection", "tendresse", "attachement", "dévotion"],
                "context": ["cœur", "romantique", "câlin", "bisou", "famille"]
            },
            "Espoir": {
                "primary": ["espoir", "optimiste", "confiant", "positif", "encourageant"],
                "secondary": ["perspective", "avenir", "amélioration", "projet"],
                "context": ["rêver", "aspirer", "croire", "motivation", "ambition"]
            },
            "Présence": {
                "primary": ["présent", "ici", "maintenant", "conscience", "attentif"],
                "secondary": ["moment", "instant", "focus", "concentration"],
                "context": ["méditation", "pleine conscience", "être", "existence"]
            },
            "Nostalgie": {
                "primary": ["nostalgie", "passé", "souvenir", "autrefois", "jadis"],
                "secondary": ["regret", "mélancolie", "hier", "avant"],
                "context": ["enfance", "jeunesse", "époque", "temps", "mémoire"]
            },
            "Curiosité": {
                "primary": ["curieux", "intéressé", "découvrir", "explorer", "questionner"],
                "secondary": ["apprendre", "comprendre", "savoir", "étudier"],
                "context": ["pourquoi", "comment", "recherche", "investigation"]
            },
            "Sérénité": {
                "primary": ["serein", "calme", "paisible", "tranquille", "apaisé"],
                "secondary": ["zen", "relaxé", "détendu", "équilibré"],
                "context": ["paix", "harmonie", "quiétude", "repos", "silence"]
            }
        }
        
        emotion_scores = {}
        
        # Analyser chaque émotion avec scoring pondéré
        for emotion, categories in emotion_keywords.items():
            score = 0
            
            # Mots primaires (score 3)
            for word in categories.get("primary", []):
                if word in text_lower:
                    score += 3
            
            # Mots secondaires (score 2)
            for word in categories.get("secondary", []):
                if word in text_lower:
                    score += 2
            
            # Mots contextuels (score 1)
            for word in categories.get("context", []):
                if word in text_lower:
                    score += 1
            
            if score > 0:
                emotion_scores[emotion] = score
        
        # Retourner l'émotion avec le score le plus élevé
        if emotion_scores:
            detected = max(emotion_scores, key=emotion_scores.get)
            # Vérifier si l'émotion existe dans nos données
            if detected in self.states:
                return detected
        
        return "Présence"  # Défaut
    
    def get_state_for_mistral(self, detected_state: str) -> Dict[str, Any]:
        """Récupère les données complètes d'un état pour Mistral"""
        if self.source == "NocoDB" and detected_state in self.nocodb_full_data:
            return self.nocodb_full_data[detected_state]
        elif detected_state in self.states:
            return self.states[detected_state]
        else:
            return self.states.get("Présence", {})

# Instances globales
flowme_states = None
analytics = FlowMeAnalytics()

async def load_nocodb_states():
    global flowme_states
    
    logger.info("🔍 Chargement des états FlowMe depuis NocoDB...")
    nocodb_status = False
    
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
                        nocodb_full_data = {}  # Données complètes pour Mistral
                        
                        for record in records:
                            if isinstance(record, dict):
                                name = record.get("Nom_État")
                                if name:
                                    # Données de base pour la détection
                                    nocodb_states[name] = {
                                        "description": record.get("Tension_Dominante", ""),
                                        "color": record.get("Couleur", "#808080"),
                                        "emoji": record.get("Emoji", "😐")
                                    }
                                    
                                    # Données COMPLÈTES pour Mistral
                                    nocodb_full_data[name] = {
                                        "nom": name,
                                        "tension_dominante": record.get("Tension_Dominante", ""),
                                        "famille_symbolique": record.get("Famille_Symbolique", ""),
                                        "mouvement_energetique": record.get("Mouvement_Energétique", ""),
                                        "qualites_specifiques": record.get("Qualités_Spécifiques", ""),
                                        "pratiques_associees": record.get("Pratiques_Associées", ""),
                                        "sagesse_traditionnelle": record.get("Sagesse_Traditionnelle", ""),
                                        "applications_therapeutiques": record.get("Applications_Thérapeutiques", ""),
                                        "couleur": record.get("Couleur", "#808080"),
                                        "emoji": record.get("Emoji", "😐"),
                                        "raw_record": record  # Données brutes complètes
                                    }
                        
                        if nocodb_states:
                            flowme_states = EnhancedFlowMeStatesDetection(nocodb_states, "NocoDB")
                            # IMPORTANT: Passer les données complètes à FlowMe
                            flowme_states.set_nocodb_data(nocodb_full_data)
                            nocodb_status = True
                            logger.info(f"✅ {len(nocodb_states)} états chargés depuis NocoDB avec données complètes")
                            return nocodb_status
                
                logger.warning("⚠️ NocoDB non disponible - aucun record trouvé")
        except Exception as e:
            logger.warning(f"⚠️ Erreur NocoDB: {e}")
            analytics.log_error("nocodb_connection", str(e))
    
    # Fallback local
    flowme_states = EnhancedFlowMeStatesDetection(LOCAL_FALLBACK_STATES, "Local")
    logger.info("🏠 États locaux chargés (fallback)")
    return nocodb_status

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
    except Exception as e:
        analytics.log_error("nocodb_save", str(e))
        return False

async def generate_mistral_response(message: str, detected_state: str) -> tuple[str, bool]:
    mistral_status = False
    
    if not MISTRAL_API_KEY:
        return f"Je comprends que vous ressentez de la {detected_state.lower()}. Comment puis-je vous accompagner ?", mistral_status
    
    try:
        # RÉCUPÉRER LES DONNÉES COMPLÈTES DE L'ÉTAT depuis NocoDB
        state_data = flowme_states.get_state_for_mistral(detected_state)
        
        # Construire le prompt enrichi avec toutes les données NocoDB
        if flowme_states.source == "NocoDB" and detected_state in flowme_states.nocodb_full_data:
            full_state = flowme_states.nocodb_full_data[detected_state]
            
            system_prompt = f"""Tu es FlowMe, un compagnon IA empathique spécialisé dans l'accompagnement émotionnel.

ÉTAT DÉTECTÉ: {detected_state}

INFORMATIONS COMPLÈTES SUR L'ÉTAT:
- Tension dominante: {full_state.get('tension_dominante', '')}
- Famille symbolique: {full_state.get('famille_symbolique', '')}
- Mouvement énergétique: {full_state.get('mouvement_energetique', '')}
- Qualités spécifiques: {full_state.get('qualites_specifiques', '')}
- Pratiques associées: {full_state.get('pratiques_associees', '')}
- Sagesse traditionnelle: {full_state.get('sagesse_traditionnelle', '')}
- Applications thérapeutiques: {full_state.get('applications_therapeutiques', '')}

INSTRUCTIONS:
1. Utilise ces informations détaillées pour comprendre profondément l'état de l'utilisateur
2. Réponds de manière empathique et personnalisée basée sur ces données
3. Propose des conseils ou pratiques en lien avec les "pratiques associées" si approprié
4. Intègre la sagesse traditionnelle de manière naturelle
5. Reste bienveillant et encourageant (max 150 mots)

Message de l'utilisateur: {message}"""
        
        else:
            # Fallback pour les états locaux
            state_description = state_data.get("description", detected_state)
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
                mistral_status = True
                return result["choices"][0]["message"]["content"].strip(), mistral_status
                
    except Exception as e:
        analytics.log_error("mistral_api", str(e))
        logger.error(f"Erreur Mistral API: {e}")
    
    return f"Je comprends votre état de {detected_state.lower()}. Parlons de ce qui vous préoccupe.", mistral_status

@app.on_event("startup")
async def startup_event():
    nocodb_status = await load_nocodb_states()
    
    # Log de la santé initiale du système
    analytics.log_system_health(
        nocodb_status=nocodb_status,
        mistral_status=bool(MISTRAL_API_KEY),
        response_times={},
        error_count=0
    )
    
    logger.info("🚀 FlowMe v3 démarré avec intégration Mistral + NocoDB complète")

@app.get("/", response_class=HTMLResponse)
async def home():
    return HTMLResponse("""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>FlowMe v3 - Enhanced</title>
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
            .analytics-link { 
                position: fixed; 
                top: 20px; 
                right: 20px; 
                background: rgba(255,255,255,0.9); 
                padding: 10px 15px; 
                border-radius: 10px; 
                text-decoration: none; 
                color: #667eea; 
                font-weight: bold;
                box-shadow: 0 4px 15px rgba(0,0,0,0.1);
            }
            .analytics-link:hover { background: #667eea; color: white; }
            .nocodb-status {
                position: fixed;
                top: 20px;
                left: 20px;
                background: rgba(40, 167, 69, 0.9);
                padding: 8px 12px;
                border-radius: 8px;
                color: white;
                font-size: 0.8em;
                font-weight: bold;
            }
            .nocodb-status.local {
                background: rgba(255, 193, 7, 0.9);
                color: #333;
            }
        </style>
    </head>
    <body>
        <div class="nocodb-status" id="nocodbStatus">🔄 Chargement...</div>
        <a href="/analytics/dashboard" class="analytics-link" target="_blank">📊 Analytics</a>
        
        <div class="container">
            <h1>🌊💙 FlowMe v3 Enhanced</h1>
            <div class="chat" id="chat">
                <div class="message ai-message">
                    <strong>FlowMe:</strong> Bonjour ! Je suis maintenant connecté à la base de données complète des états émotionnels. Comment vous sentez-vous aujourd'hui ?
                </div>
            </div>
            <div class="input-container">
                <input type="text" id="input" placeholder="Exprimez vos émotions..." maxlength="500">
                <button onclick="sendMessage()">Envoyer</button>
            </div>
            <div class="status" id="status">FlowMe v3 Enhanced - Prêt</div>
        </div>
        
        <script>
            let isProcessing = false;
            
            // Vérifier le statut NocoDB au chargement
            fetch('/health')
                .then(response => response.json())
                .then(data => {
                    const statusElement = document.getElementById('nocodbStatus');
                    if (data.source === 'NocoDB') {
                        statusElement.textContent = `🟢 NocoDB (${data.states_count} états)`;
                        statusElement.className = 'nocodb-status';
                    } else {
                        statusElement.textContent = `🟡 Local (${data.states_count} états)`;
                        statusElement.className = 'nocodb-status local';
                    }
                })
                .catch(() => {
                    document.getElementById('nocodbStatus').textContent = '🔴 Erreur';
                });
            
            async function sendMessage() {
                if (isProcessing) return;
                const input = document.getElementById('input');
                const message = input.value.trim();
                if (!message) return;
                
                isProcessing = true;
                document.getElementById('status').textContent = 'FlowMe analyse avec NocoDB...';
                
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
                        const responseTime = data.response_time ? ` (${data.response_time}s)` : '';
                        const source = data.source === 'NocoDB' ? '🟢 NocoDB' : '🟡 Local';
                        document.getElementById('status').textContent = `État: ${data.detected_state} • Source: ${source}${responseTime}`;
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
    start_time = time.time()
    session_id = chat_message.user_id or "anonymous"
    
    try:
        if not flowme_states:
            raise HTTPException(status_code=503, detail="Service non disponible")
        
        # Démarrer la conversation si nouvelle
        if session_id not in analytics.conversations:
            analytics.start_conversation(session_id, chat_message.user_id)
        
        clean_message = chat_message.message.strip()[:500]
        
        # Détection d'émotion améliorée
        detected_state = flowme_states.detect_emotion(clean_message)
        
        # Génération de réponse avec données NocoDB complètes
        ai_response, mistral_status = await generate_mistral_response(clean_message, detected_state)
        
        # Calculer le temps de réponse
        response_time = time.time() - start_time
        
        # Log des métriques
        analytics.log_message(session_id, detected_state, response_time)
        
        # Log de la santé système
        analytics.log_system_health(
            nocodb_status=flowme_states.source == "NocoDB",
            mistral_status=mistral_status,
            response_times={"chat": response_time},
            error_count=0
        )
        
        # Sauvegarde asynchrone
        await save_to_nocodb(clean_message, ai_response, detected_state, session_id)
        
        return JSONResponse({
            "response": ai_response,
            "detected_state": detected_state,
            "source": flowme_states.source,
            "timestamp": datetime.now().isoformat(),
            "response_time": round(response_time, 2),
            "nocodb_integration": flowme_states.source == "NocoDB"
        })
        
    except Exception as e:
        analytics.log_error("chat_error", str(e), session_id)
        logger.error(f"Erreur chat: {e}")
        return JSONResponse({
            "response": "Je rencontre une difficulté technique. Pouvez-vous réessayer ?",
            "detected_state": "Présence",
            "error": "Service indisponible"
        }, status_code=500)

# ========== ENDPOINTS MONITORING ==========

@app.get("/analytics")
async def get_analytics():
    """Dashboard d'analytics complet en JSON"""
    summary = analytics.get_analytics_summary()
    
    # Ajouter des métriques détaillées
    recent_conversations = []
    for conv in sorted(analytics.conversations.values(), key=lambda x: x.start_time, reverse=True)[:10]:
        recent_conversations.append({
            "session_id": conv.session_id,
            "start_time": conv.start_time.isoformat(),
            "message_count": conv.message_count,
            "emotions": conv.emotions_detected[-3:] if conv.emotions_detected else [],
            "avg_response_time": round(conv.average_response_time, 2)
        })
    
    summary["recent_conversations"] = recent_conversations
    summary["error_log"] = [
        {
            "timestamp": err["timestamp"].isoformat(),
            "type": err["type"],
            "message": err["message"][:100]
        }
        for err in analytics.error_log[-10:]
    ]
    
    # Informations sur l'intégration NocoDB
    summary["nocodb_integration"] = {
        "source": flowme_states.source if flowme_states else "none",
        "states_loaded": len(flowme_states.states) if flowme_states else 0,
        "full_data_available": len(flowme_states.nocodb_full_data) if flowme_states and hasattr(flowme_states, 'nocodb_full_data') else 0,
        "mistral_enhanced": flowme_states.source == "NocoDB" if flowme_states else False
    }
    
    return JSONResponse(summary)

@app.get("/analytics/dashboard")
async def analytics_dashboard():
    """Page HTML du dashboard analytics"""
    return HTMLResponse("""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>FlowMe Analytics Dashboard</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
            .container { max-width: 1200px; margin: 0 auto; }
            .card { background: white; border-radius: 10px; padding: 20px; margin: 15px 0; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            .metric { display: inline-block; margin: 10px 20px 10px 0; }
            .metric-value { font-size: 2em; font-weight: bold; color: #667eea; }
            .metric-label { color: #666; font-size: 0.9em; }
            .error { color: #dc3545; }
            .success { color: #28a745; }
            .warning { color: #ffc107; }
            h1, h2 { color: #333; }
            .refresh-btn { 
                background: #667eea; 
                color: white; 
                border: none; 
                padding: 10px 20px; 
                border-radius: 5px; 
                cursor: pointer; 
                margin-bottom: 20px;
            }
            .refresh-btn:hover { background: #5a6fd8; }
            .nocodb-status {
                background: linear-gradient(135deg, #667eea, #764ba2);
                color: white;
                padding: 15px;
                border-radius: 10px;
                margin-bottom: 20px;
            }
            .status-indicator {
                display: inline-block;
                width: 12px;
                height: 12px;
                border-radius: 50%;
                margin-right: 8px;
            }
            .status-online { background: #28a745; }
            .status-offline { background: #dc3545; }
            .status-local { background: #ffc107; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>📊 FlowMe v3 - Analytics Dashboard Enhanced</h1>
            <button class="refresh-btn" onclick="loadAnalytics()">🔄 Actualiser</button>
            
            <div class="card nocodb-status">
                <h2>🔗 Statut Intégration NocoDB</h2>
                <div id="nocodbIntegration">Chargement...</div>
            </div>
            
            <div class="card">
                <h2>📈 Métriques Générales</h2>
                <div id="generalMetrics">Chargement...</div>
            </div>
            
            <div class="card">
                <h2>💭 Émotions Détectées</h2>
                <div id="emotionMetrics">Chargement...</div>
            </div>
            
            <div class="card">
                <h2>💬 Conversations Récentes</h2>
                <div id="conversationMetrics">Chargement...</div>
            </div>
            
            <div class="card">
                <h2>⚠️ Erreurs Récentes</h2>
                <div id="errorMetrics">Chargement...</div>
            </div>
        </div>
        
        <script>
            async function loadAnalytics() {
                try {
                    const response = await fetch('/analytics');
                    const data = await response.json();
                    
                    // Statut NocoDB
                    const nocodb = data.nocodb_integration;
                    let statusHtml = '';
                    if (nocodb.source === 'NocoDB') {
                        statusHtml = `
                            <div><span class="status-indicator status-online"></span><strong>NocoDB Connecté</strong></div>
                            <p>✅ ${nocodb.states_loaded} états chargés depuis NocoDB</p>
                            <p>✅ ${nocodb.full_data_available} états avec données complètes pour Mistral</p>
                            <p>✅ Mistral AI utilise les données enrichies NocoDB</p>
                        `;
                    } else if (nocodb.source === 'Local') {
                        statusHtml = `
                            <div><span class="status-indicator status-local"></span><strong>Mode Local (Fallback)</strong></div>
                            <p>⚠️ ${nocodb.states_loaded} états locaux chargés</p>
                            <p>⚠️ NocoDB non disponible - Mistral utilise les données de base</p>
                        `;
                    } else {
                        statusHtml = `
                            <div><span class="status-indicator status-offline"></span><strong>Service Non Disponible</strong></div>
                            <p>❌ Aucun état chargé</p>
                        `;
                    }
                    document.getElementById('nocodbIntegration').innerHTML = statusHtml;
                    
                    // Métriques générales
                    document.getElementById('generalMetrics').innerHTML = `
                        <div class="metric">
                            <div class="metric-value">${data.total_conversations}</div>
                            <div class="metric-label">Conversations totales</div>
                        </div>
                        <div class="metric">
                            <div class="metric-value ${data.active_conversations > 0 ? 'success' : ''}">${data.active_conversations}</div>
                            <div class="metric-label">Conversations actives</div>
                        </div>
                        <div class="metric">
                            <div class="metric-value">${data.total_messages}</div>
                            <div class="metric-label">Messages totaux</div>
                        </div>
                        <div class="metric">
                            <div class="metric-value ${data.system_uptime_percent >= 95 ? 'success' : 'error'}">${data.system_uptime_percent}%</div>
                            <div class="metric-label">Uptime système</div>
                        </div>
                        <div class="metric">
                            <div class="metric-value">${data.average_response_time}s</div>
                            <div class="metric-label">Temps de réponse moyen</div>
                        </div>
                        <div class="metric">
                            <div class="metric-value">${Math.round(data.uptime_seconds / 3600)}h</div>
                            <div class="metric-label">Uptime</div>
                        </div>
                    `;
                    
                    // Émotions
                    let emotionsHtml = '';
                    for (const [emotion, count] of Object.entries(data.top_emotions)) {
                        emotionsHtml += `
                            <div class="metric">
                                <div class="metric-value">${count}</div>
                                <div class="metric-label">${emotion}</div>
                            </div>
                        `;
                    }
                    document.getElementById('emotionMetrics').innerHTML = emotionsHtml || 'Aucune émotion détectée encore';
                    
                    // Conversations récentes
                    let conversationsHtml = '<ul>';
                    data.recent_conversations.forEach(conv => {
                        conversationsHtml += `
                            <li>
                                <strong>${conv.session_id}</strong> - 
                                ${conv.message_count} messages - 
                                Émotions: ${conv.emotions.join(', ') || 'Aucune'} - 
                                Temps moyen: ${conv.avg_response_time}s
                            </li>
                        `;
                    });
                    conversationsHtml += '</ul>';
                    document.getElementById('conversationMetrics').innerHTML = conversationsHtml;
                    
                    // Erreurs récentes
                    let errorsHtml = '<ul>';
                    if (data.error_log && data.error_log.length > 0) {
                        data.error_log.forEach(err => {
                            errorsHtml += `
                                <li class="error">
                                    <strong>[${err.type}]</strong> ${err.message} 
                                    <small>(${new Date(err.timestamp).toLocaleString()})</small>
                                </li>
                            `;
                        });
                    } else {
                        errorsHtml += '<li class="success">Aucune erreur récente 🎉</li>';
                    }
                    errorsHtml += '</ul>';
                    document.getElementById('errorMetrics').innerHTML = errorsHtml;
                    
                } catch (error) {
                    console.error('Erreur de chargement des analytics:', error);
                    document.getElementById('generalMetrics').innerHTML = '<div class="error">Erreur de chargement des analytics</div>';
                }
            }
            
            // Charger les analytics au chargement de la page
            loadAnalytics();
            
            // Auto-refresh toutes les 30 secondes
            setInterval(loadAnalytics, 30000);
        </script>
    </body>
    </html>
    """)

@app.get("/health")
async def health_check():
    """Health check avec métriques système"""
    summary = analytics.get_analytics_summary()
    
    return JSONResponse({
        "status": "healthy",
        "version": "3.0.0-enhanced",
        "states_count": len(flowme_states.states) if flowme_states else 0,
        "source": flowme_states.source if flowme_states else "none",
        "timestamp": datetime.now().isoformat(),
        "uptime_seconds": summary["uptime_seconds"],
        "system_uptime_percent": summary["system_uptime_percent"],
        "active_conversations": summary["active_conversations"],
        "average_response_time": summary["average_response_time"],
        "recent_errors": summary["recent_errors"],
        "nocodb_integration": flowme_states.source == "NocoDB" if flowme_states else False,
        "full_nocodb_data": len(flowme_states.nocodb_full_data) if flowme_states and hasattr(flowme_states, 'nocodb_full_data') else 0
    })

@app.get("/analytics/emotions")
async def emotion_analytics():
    """Statistiques sur les émotions détectées"""
    return JSONResponse({
        "emotion_distribution": dict(analytics.emotion_stats),
        "top_emotions": dict(analytics.emotion_stats.most_common(10)),
        "total_emotions_detected": sum(analytics.emotion_stats.values()),
        "nocodb_states_available": list(flowme_states.states.keys()) if flowme_states else []
    })

@app.get("/analytics/conversations")
async def conversation_analytics():
    """Statistiques sur les conversations"""
    active_convs = [c for c in analytics.conversations.values() if c.end_time is None]
    completed_convs = [c for c in analytics.conversations.values() if c.end_time is not None]
    
    avg_messages = sum(c.message_count for c in analytics.conversations.values()) / len(analytics.conversations) if analytics.conversations else 0
    
    return JSONResponse({
        "total_conversations": len(analytics.conversations),
        "active_conversations": len(active_convs),
        "completed_conversations": len(completed_convs),
        "average_messages_per_conversation": round(avg_messages, 2),
        "recent_conversations": [
            {
                "session_id": c.session_id,
                "start_time": c.start_time.isoformat(),
                "message_count": c.message_count,
                "emotions": c.emotions_detected[-3:] if c.emotions_detected else []
            }
            for c in sorted(analytics.conversations.values(), key=lambda x: x.start_time, reverse=True)[:10]
        ]
    })

@app.get("/debug/nocodb")
async def debug_nocodb():
    """Endpoint de debug pour vérifier l'intégration NocoDB"""
    if not flowme_states:
        return JSONResponse({"error": "FlowMe non initialisé"})
    
    debug_info = {
        "source": flowme_states.source,
        "states_count": len(flowme_states.states),
        "states_list": list(flowme_states.states.keys()),
        "nocodb_full_data_available": hasattr(flowme_states, 'nocodb_full_data'),
        "nocodb_full_data_count": len(flowme_states.nocodb_full_data) if hasattr(flowme_states, 'nocodb_full_data') else 0
    }
    
    if hasattr(flowme_states, 'nocodb_full_data') and flowme_states.nocodb_full_data:
        # Exemple d'un état pour debug
        first_state = list(flowme_states.nocodb_full_data.keys())[0]
        debug_info["sample_nocodb_data"] = {
            "state_name": first_state,
            "data": flowme_states.nocodb_full_data[first_state]
        }
    
    return JSONResponse(debug_info)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
