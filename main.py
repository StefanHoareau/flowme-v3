import os
import json
import httpx
import logging
import time
import psutil  # Pour les métriques système
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
    user_satisfaction: Optional[int]

@dataclass
class SystemHealthMetrics:
    timestamp: datetime
    nocodb_status: bool
    mistral_status: bool
    response_times: Dict[str, float]
    error_count: int
    active_sessions: int
    memory_usage: float
    cpu_usage: float

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
            average_response_time=0.0,
            user_satisfaction=None
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
        try:
            memory_usage = psutil.virtual_memory().percent
            cpu_usage = psutil.cpu_percent()
        except:
            memory_usage = 0.0
            cpu_usage = 0.0
            
        health = SystemHealthMetrics(
            timestamp=datetime.now(),
            nocodb_status=nocodb_status,
            mistral_status=mistral_status,
            response_times=response_times,
            error_count=error_count,
            active_sessions=len([c for c in self.conversations.values() if c.end_time is None]),
            memory_usage=memory_usage,
            cpu_usage=cpu_usage
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
            "recent_errors": len([e for e in self.error_log if e['timestamp'] > now - timedelta(hours=1)]),
            "memory_usage": self.health_history[-1].memory_usage if self.health_history else 0,
            "cpu_usage": self.health_history[-1].cpu_usage if self.health_history else 0
        }

# ========== APPLICATION PRINCIPALE ==========

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

# Instances globales
flowme_states = None
analytics = FlowMeAnalytics()

# Ajout de l'analytics à l'app state
app.state.analytics = analytics

async def load_nocodb_states():
    global flowme_states
    
    logger.info("🔍 Chargement des états FlowMe...")
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
                            nocodb_status = True
                            logger.info(f"✅ {len(nocodb_states)} états chargés depuis NocoDB")
                            return nocodb_status
                
                logger.warning("⚠️ NocoDB non disponible")
        except Exception as e:
            logger.warning(f"⚠️ Erreur NocoDB: {e}")
            analytics.log_error("nocodb_connection", str(e))
    
    # Fallback local
    flowme_states = FlowMeStatesDetection(LOCAL_FALLBACK_STATES, "Local")
    logger.info("🏠 États locaux chargés")
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
        state_info = flowme_states.states.get(detected_state, {})
        state_description = state_info.get("description", detected_state)
        
        system_prompt = f"""Tu es FlowMe, un compagnion IA empathique.

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
    
    logger.info("🚀 FlowMe v3 démarré avec monitoring")

@app.get("/", response_class=HTMLResponse)
async def home():
    # Votre HTML existant ici...
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
    start_time = time.time()
    session_id = chat_message.user_id or "anonymous"
    
    try:
        if not flowme_states:
            raise HTTPException(status_code=503, detail="Service non disponible")
        
        # Démarrer la conversation si nouvelle
        if session_id not in analytics.conversations:
            analytics.start_conversation(session_id, chat_message.user_id)
        
        clean_message = chat_message.message.strip()[:500]
        
        detected_state = flowme_states.detect_emotion(clean_message)
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
            "response_time": round(response_time, 2)
        })
        
    except Exception as e:
        analytics.log_error("chat_error", str(e), session_id)
        logger.error(f"Erreur chat: {e}")
        return JSONResponse({
            "response": "Je rencontre une difficulté technique. Pouvez-vous réessayer ?",
            "detected_state": "Présence",
            "error": "Service indisponible"
        }, status_code=500)

# ========== NOUVEAUX ENDPOINTS MONITORING ==========

@app.get("/analytics")
async def get_analytics():
    """Dashboard d'analytics complet"""
    return JSONResponse(analytics.get_analytics_summary())

@app.get("/health")
async def health_check():
    """Health check avec métriques système"""
    summary = analytics.get_analytics_summary()
    
    return JSONResponse({
        "status": "healthy",
        "version": "3.0.0",
        "states_count": len(flowme_states.states) if flowme_states else 0,
        "source": flowme_states.source if flowme_states else "none",
        "timestamp": datetime.now().isoformat(),
        "uptime_seconds": summary["uptime_seconds"],
        "system_uptime_percent": summary["system_uptime_percent"],
        "active_conversations": summary["active_conversations"],
        "memory_usage": summary["memory_usage"],
        "cpu_usage": summary["cpu_usage"],
        "average_response_time": summary["average_response_time"]
    })

@app.get("/analytics/emotions")
async def emotion_analytics():
    """Statistiques sur les émotions détectées"""
    return JSONResponse({
        "emotion_distribution": dict(analytics.emotion_stats),
        "top_emotions": dict(analytics.emotion_stats.most_common(10)),
        "total_emotions_detected": sum(analytics.emotion_stats.values())
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

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
