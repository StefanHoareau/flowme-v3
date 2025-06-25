# main.py - FlowMe v3 avec module intégré (solution temporaire)

import os
import asyncio
import json
import traceback
from datetime import datetime
from typing import Dict, List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field
import httpx

# ============ MODULE FLOWME STATES INTÉGRÉ ============
# Configuration des états de conscience Stefan Hoareau
FLOWME_STATES = {
    1: {
        "name": "Présence",
        "description": "État de conscience pure, d'attention au moment présent",
        "keywords": ["maintenant", "présent", "ici", "moment", "attention", "conscience"],
        "energy_level": "neutral",
        "category": "awareness"
    },
    16: {
        "name": "Amour",
        "description": "Capacité d'aimer sans condition, ouverture du cœur",
        "keywords": ["amour", "aimer", "cœur", "tendresse", "affection", "bienveillance"],
        "energy_level": "high",
        "category": "heart"
    },
    32: {
        "name": "Joie",
        "description": "Bonheur spontané, légèreté de l'être",
        "keywords": ["joie", "bonheur", "rire", "sourire", "plaisir", "gaieté"],
        "energy_level": "high",
        "category": "emotion"
    },
    48: {
        "name": "Paix",
        "description": "Tranquillité intérieure, sérénité profonde",
        "keywords": ["paix", "calme", "sérénité", "tranquillité", "repos", "silence"],
        "energy_level": "low",
        "category": "stillness"
    },
    64: {
        "name": "Unité",
        "description": "Sentiment d'union avec le tout, non-dualité",
        "keywords": ["unité", "tout", "ensemble", "connexion", "fusion", "totalité"],
        "energy_level": "transcendent",
        "category": "unity"
    },
    8: {
        "name": "Tristesse",
        "description": "Mélancolie, peine intérieure",
        "keywords": ["triste", "tristesse", "peine", "chagrin", "mélancolie", "pleure"],
        "energy_level": "low",
        "category": "emotion"
    },
    24: {
        "name": "Colère",
        "description": "Irritation, frustration, rage",
        "keywords": ["colère", "rage", "frustration", "irrité", "énervé", "furieux"],
        "energy_level": "high",
        "category": "emotion"
    },
    40: {
        "name": "Peur",
        "description": "Anxiété, inquiétude, appréhension",
        "keywords": ["peur", "anxiété", "stress", "inquiet", "angoisse", "crainte"],
        "energy_level": "high",
        "category": "emotion"
    },
    4: {
        "name": "Confusion",
        "description": "Désorientation mentale, manque de clarté",
        "keywords": ["confus", "perdu", "désorienté", "flou", "incompréhensible"],
        "energy_level": "neutral",
        "category": "mental"
    },
    12: {
        "name": "Clarté",
        "description": "Compréhension claire, lucidité",
        "keywords": ["clair", "comprendre", "lucide", "évident", "précis"],
        "energy_level": "neutral",
        "category": "mental"
    }
}

def detect_primary_state(message: str, user_context: Dict = None) -> Dict:
    """Détecte l'état de conscience primaire basé sur le message de l'utilisateur"""
    message_lower = message.lower()
    state_scores = {}
    
    for state_id, state_info in FLOWME_STATES.items():
        score = 0
        for keyword in state_info["keywords"]:
            if keyword in message_lower:
                score += 2
        
        if state_info["category"] == "emotion":
            if any(word in message_lower for word in ["ressens", "émotion", "sentiment"]):
                score += 1
        
        if state_info["energy_level"] == "high" and any(word in message_lower for word in ["!", "très", "beaucoup"]):
            score += 1
        elif state_info["energy_level"] == "low" and any(word in message_lower for word in ["peu", "doucement", "calme"]):
            score += 1
            
        if score > 0:
            state_scores[state_id] = score
    
    if state_scores:
        primary_state_id = max(state_scores, key=state_scores.get)
        confidence = min(state_scores[primary_state_id] * 0.2, 1.0)
    else:
        primary_state_id = 1
        confidence = 0.3
    
    return {
        "state_id": primary_state_id,
        "state_name": FLOWME_STATES[primary_state_id]["name"],
        "description": FLOWME_STATES[primary_state_id]["description"],
        "confidence": confidence,
        "category": FLOWME_STATES[primary_state_id]["category"],
        "energy_level": FLOWME_STATES[primary_state_id]["energy_level"]
    }

def suggest_transition(current_state_id: int, target_emotion: str = None) -> Dict:
    """Suggère une transition d'état basée sur l'état actuel"""
    current_state = FLOWME_STATES.get(current_state_id, FLOWME_STATES[1])
    
    transitions = {
        8: [1, 16, 48],    # Tristesse -> Présence, Amour, Paix
        24: [48, 1, 16],   # Colère -> Paix, Présence, Amour
        40: [1, 48, 12],   # Peur -> Présence, Paix, Clarté
        4: [12, 1, 16],    # Confusion -> Clarté, Présence, Amour
        1: [16, 32, 48],   # Présence -> Amour, Joie, Paix
        16: [32, 64, 48],  # Amour -> Joie, Unité, Paix
        32: [16, 64, 48],  # Joie -> Amour, Unité, Paix
        48: [1, 16, 64],   # Paix -> Présence, Amour, Unité
        12: [16, 32, 1],   # Clarté -> Amour, Joie, Présence
        64: [16, 32, 48]   # Unité -> Amour, Joie, Paix
    }
    
    possible_transitions = transitions.get(current_state_id, [1, 16, 48])
    suggested_state_id = possible_transitions[0]
    suggested_state = FLOWME_STATES[suggested_state_id]
    
    methods = {
        (8, 1): "Respiration consciente et observation des sensations présentes",
        (8, 16): "Pratique de l'auto-compassion et de la bienveillance envers soi",
        (24, 48): "Respiration profonde et relaxation musculaire progressive",
        (40, 1): "Techniques de grounding et de recentrage",
        (4, 12): "Pause réflexive et structuration de la pensée"
    }
    
    return {
        "current_state": {
            "id": current_state_id,
            "name": current_state["name"],
            "description": current_state["description"]
        },
        "suggested_state": {
            "id": suggested_state_id,
            "name": suggested_state["name"],
            "description": suggested_state["description"]
        },
        "transition_method": methods.get((current_state_id, suggested_state_id), "Méditation de pleine conscience"),
        "estimated_duration": "15-30 minutes"
    }

def analyze_emotional_pattern(message_history: List[str]) -> Dict:
    """Analyse les patterns émotionnels"""
    return {"pattern": "stable", "recommendation": "Continue à partager tes émotions"}

def get_all_states() -> Dict:
    """Retourne tous les états disponibles"""
    return FLOWME_STATES

print("✅ Module flowme_states_detection intégré avec succès")

# ============ CONFIGURATION ============
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
NOCODB_API_TOKEN = os.getenv("NOCODB_API_TOKEN") or os.getenv("NOCODB_API_KEY")
NOCODB_BASE_URL = os.getenv("NOCODB_BASE_URL") or os.getenv("NOCODB_URL", "https://app.nocodb.com")
NOCODB_REACTIONS_TABLE_ID = os.getenv("NOCODB_REACTIONS_TABLE_ID")

# Modèles Pydantic
class ChatMessage(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)
    user_id: Optional[str] = Field(default="anonymous")
    session_id: Optional[str] = Field(default=None)

class ChatResponse(BaseModel):
    response: str
    detected_state: Dict
    suggested_transition: Optional[Dict] = None
    timestamp: str
    session_id: str

class StateDetectionResponse(BaseModel):
    state_id: int
    state_name: str
    description: str
    confidence: float
    category: str
    energy_level: str

# Contexte d'application
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Démarrage de FlowMe v3")
    print(f"✅ Mistral API: {'✓ Configuré' if MISTRAL_API_KEY else '✗ Manquant'}")
    print(f"✅ NocoDB: {'✓ Configuré' if NOCODB_API_TOKEN else '✗ Manquant'}")
    print(f"📊 États disponibles: {len(FLOWME_STATES)}")
    print(f"🔗 NocoDB Base URL: {NOCODB_BASE_URL}")
    if NOCODB_REACTIONS_TABLE_ID:
        print(f"📋 Table ID: {NOCODB_REACTIONS_TABLE_ID}")
    yield
    print("🛑 Arrêt de FlowMe v3")

# Application FastAPI
app = FastAPI(
    title="FlowMe v3 - IA Empathique",
    description="API pour la détection d'états de conscience et l'IA empathique",
    version="3.0.0",
    lifespan=lifespan
)

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Client HTTP global
http_client = httpx.AsyncClient(timeout=30.0)

# Session storage simple
active_sessions = {}

# ============ ROUTES API ============

@app.get("/", response_class=HTMLResponse)
async def get_interface():
    """Interface utilisateur FlowMe v3"""
    html_content = """
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>FlowMe v3 - IA Empathique</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: 'Helvetica Neue', Arial, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            .container {
                background: rgba(255, 255, 255, 0.95);
                border-radius: 20px;
                padding: 2rem;
                box-shadow: 0 20px 40px rgba(0,0,0,0.1);
                max-width: 800px;
                width: 90%;
                backdrop-filter: blur(10px);
            }
            .header {
                text-align: center;
                margin-bottom: 2rem;
            }
            .header h1 {
                color: #4a5568;
                font-size: 2.5rem;
                margin-bottom: 0.5rem;
                font-weight: 300;
            }
            .status-badge {
                display: inline-block;
                background: #48bb78;
                color: white;
                padding: 0.3rem 1rem;
                border-radius: 20px;
                font-size: 0.9rem;
                font-weight: 500;
            }
            .chat-container {
                background: #f7fafc;
                border-radius: 15px;
                padding: 1.5rem;
                margin-bottom: 1.5rem;
                min-height: 400px;
                max-height: 400px;
                overflow-y: auto;
            }
            .message {
                margin-bottom: 1rem;
                padding: 1rem;
                border-radius: 10px;
                max-width: 80%;
            }
            .user-message {
                background: #667eea;
                color: white;
                margin-left: auto;
            }
            .ai-message {
                background: white;
                border: 1px solid #e2e8f0;
                color: #4a5568;
            }
            .state-info {
                font-size: 0.85rem;
                color: #718096;
                margin-top: 0.5rem;
                font-style: italic;
            }
            .input-section {
                display: flex;
                gap: 1rem;
                align-items: center;
            }
            #messageInput {
                flex: 1;
                padding: 1rem;
                border: 2px solid #e2e8f0;
                border-radius: 10px;
                font-size: 1rem;
                outline: none;
                transition: border-color 0.3s;
            }
            #messageInput:focus {
                border-color: #667eea;
            }
            #sendButton {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                padding: 1rem 2rem;
                border-radius: 10px;
                cursor: pointer;
                font-size: 1rem;
                font-weight: 500;
                transition: transform 0.2s;
            }
            #sendButton:hover {
                transform: translateY(-2px);
            }
            #sendButton:disabled {
                opacity: 0.6;
                cursor: not-allowed;
                transform: none;
            }
            .loading {
                text-align: center;
                color: #718096;
                font-style: italic;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>FlowMe v3</h1>
                <span class="status-badge" id="statusBadge">🟢 Production</span>
            </div>
            
            <div class="chat-container" id="chatContainer">
                <div class="message ai-message">
                    <div>Bonjour ! Je suis FlowMe, votre IA empathique spécialisée dans la détection d'états de conscience. Comment vous sentez-vous aujourd'hui ?</div>
                    <div class="state-info">Prêt à analyser votre état émotionnel</div>
                </div>
            </div>
            
            <div class="input-section">
                <input type="text" id="messageInput" placeholder="Partagez vos pensées ou émotions..." maxlength="1000">
                <button id="sendButton" onclick="sendMessage()">Envoyer</button>
            </div>
        </div>

        <script>
            let sessionId = 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
            
            async function sendMessage() {
                const input = document.getElementById('messageInput');
                const button = document.getElementById('sendButton');
                const container = document.getElementById('chatContainer');
                
                const message = input.value.trim();
                if (!message) return;
                
                const userDiv = document.createElement('div');
                userDiv.className = 'message user-message';
                userDiv.innerHTML = `<div>${message}</div>`;
                container.appendChild(userDiv);
                
                const loadingDiv = document.createElement('div');
                loadingDiv.className = 'loading';
                loadingDiv.textContent = 'FlowMe réfléchit...';
                container.appendChild(loadingDiv);
                
                input.value = '';
                input.disabled = true;
                button.disabled = true;
                container.scrollTop = container.scrollHeight;
                
                try {
                    const response = await fetch('/chat', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            message: message,
                            session_id: sessionId
                        })
                    });
                    
                    const data = await response.json();
                    container.removeChild(loadingDiv);
                    
                    if (response.ok) {
                        const aiDiv = document.createElement('div');
                        aiDiv.className = 'message ai-message';
                        aiDiv.innerHTML = `
                            <div>${data.response}</div>
                            <div class="state-info">
                                État détecté: ${data.detected_state.state_name} 
                                (${Math.round(data.detected_state.confidence * 100)}% confiance)
                            </div>
                        `;
                        container.appendChild(aiDiv);
                        document.getElementById('statusBadge').textContent = '🟢 Production';
                    } else {
                        const errorDiv = document.createElement('div');
                        errorDiv.className = 'message ai-message';
                        errorDiv.innerHTML = `
                            <div>Désolé, une erreur s'est produite. Veuillez réessayer.</div>
                            <div class="state-info">Mode dégradé activé</div>
                        `;
                        container.appendChild(errorDiv);
                        document.getElementById('statusBadge').textContent = '🟡 Dégradé';
                    }
                } catch (error) {
                    console.error('Erreur:', error);
                    container.removeChild(loadingDiv);
                    
                    const errorDiv = document.createElement('div');
                    errorDiv.className = 'message ai-message';
                    errorDiv.innerHTML = `
                        <div>Connexion impossible. Vérifiez votre connexion Internet.</div>
                        <div class="state-info">Erreur réseau</div>
                    `;
                    container.appendChild(errorDiv);
                    document.getElementById('statusBadge').textContent = '🔴 Hors ligne';
                }
                
                input.disabled = false;
                button.disabled = false;
                input.focus();
                container.scrollTop = container.scrollHeight;
            }
            
            document.getElementById('messageInput').addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    sendMessage();
                }
            });
            
            document.getElementById('messageInput').focus();
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(chat_message: ChatMessage):
    """Endpoint principal pour le chat avec l'IA empathique"""
    try:
        session_id = chat_message.session_id or f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Détecter l'état de conscience
        detected_state = detect_primary_state(chat_message.message)
        
        # Générer la réponse IA
        ai_response = await generate_empathic_response(
            chat_message.message, 
            detected_state,
            chat_message.user_id
        )
        
        # Suggérer une transition si nécessaire
        suggested_transition = None
        if detected_state["state_id"] in [8, 24, 40, 4]:  # États négatifs
            suggested_transition = suggest_transition(detected_state["state_id"])
        
        # Sauvegarder dans NocoDB
        await save_interaction_to_nocodb(
            user_id=chat_message.user_id,
            message=chat_message.message,
            ai_response=ai_response,
            detected_state=detected_state,
            session_id=session_id
        )
        
        # Mettre à jour la session
        if session_id not in active_sessions:
            active_sessions[session_id] = []
        active_sessions[session_id].append({
            "message": chat_message.message,
            "response": ai_response,
            "state": detected_state,
            "timestamp": datetime.now().isoformat()
        })
        
        return ChatResponse(
            response=ai_response,
            detected_state=detected_state,
            suggested_transition=suggested_transition,
            timestamp=datetime.now().isoformat(),
            session_id=session_id
        )
        
    except Exception as e:
        print(f"❌ Erreur dans chat_endpoint: {e}")
        print(f"📍 Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")

@app.get("/states", response_model=Dict)
async def get_states():
    """Récupère tous les états de conscience disponibles"""
    try:
        return get_all_states()
    except Exception as e:
        print(f"❌ Erreur dans get_states: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/detect-state", response_model=StateDetectionResponse)
async def detect_state_endpoint(chat_message: ChatMessage):
    """Endpoint pour détecter uniquement l'état de conscience"""
    try:
        detected_state = detect_primary_state(chat_message.message)
        return StateDetectionResponse(**detected_state)
    except Exception as e:
        print(f"❌ Erreur dans detect_state_endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Vérification de l'état de santé de l'API"""
    try:
        mistral_status = "✓" if MISTRAL_API_KEY else "✗"
        nocodb_status = "✓" if NOCODB_API_TOKEN else "✗"
        states_count = len(FLOWME_STATES)
        
        return {
            "status": "healthy",
            "version": "3.0.0",
            "components": {
                "mistral_ai": mistral_status,
                "nocodb": nocodb_status,
                "states_detection": f"✓ ({states_count} états)"
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        print(f"❌ Erreur dans health_check: {e}")
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "error": str(e)}
        )

# ============ FONCTIONS UTILITAIRES ============

async def generate_empathic_response(message: str, detected_state: Dict, user_id: str = "anonymous") -> str:
    """Génère une réponse empathique avec Mistral AI"""
    try:
        if not MISTRAL_API_KEY:
            return await generate_fallback_response(detected_state)
        
        state_name = detected_state["state_name"]
        state_description = detected_state["description"]
        confidence = detected_state["confidence"]
        
        prompt = f"""Tu es FlowMe, une IA empathique spécialisée dans les 96 états de conscience de Stefan Hoareau.

L'utilisateur vient de partager: "{message}"

J'ai détecté l'état de conscience: {state_name} ({state_description})
Niveau de confiance: {confidence:.1%}

Réponds de manière empathique et bienveillante en:
1. Reconnaissant son état émotionnel actuel
2. Validant son expérience sans jugement
3. Offrant une perspective aidante si approprié
4. Restant concis (maximum 3 phrases)

Ton ton doit être chaleureux, authentique et profondément empathique."""

        headers = {
            "Authorization": f"Bearer {MISTRAL_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "mistral-medium-latest",
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": message}
            ],
            "max_tokens": 200,
            "temperature": 0.7
        }
        
        response = await http_client.post(
            "https://api.mistral.ai/v1/chat/completions",
            headers=headers,
            json=payload
        )
        
        if response.status_code == 200:
            result = response.json()
            return result["choices"][0]["message"]["content"].strip()
        else:
            print(f"❌ Erreur Mistral API: {response.status_code} - {response.text}")
            return await generate_fallback_response(detected_state)
            
    except Exception as e:
        print(f"❌ Erreur génération réponse: {e}")
        return await generate_fallback_response(detected_state)

async def generate_fallback_response(detected_state: Dict) -> str:
    """Génère une réponse de fallback basée sur l'état détecté"""
    state_name = detected_state["state_name"]
    
    fallback_responses = {
        "Présence": "Je sens que vous êtes dans un moment de conscience et d'attention. C'est précieux de pouvoir observer ce qui se passe en vous.",
        "Amour": "Il y a quelque chose de beau dans ce que vous partagez, une ouverture du cœur qui mérite d'être honorée.",
        "Joie": "Votre joie est palpable et c'est merveilleux ! Ces moments de bonheur sont des cadeaux précieux.",
        "Paix": "Je perçois une tranquillité dans vos mots. Cette paix intérieure est un refuge précieux.",
        "Tristesse": "Je comprends cette peine que vous traversez. Vos émotions sont valides et méritent d'être accueillies avec douceur.",
        "Colère": "Cette frustration que vous ressentez est compréhensible. Parfois, la colère nous indique que quelque chose d'important a besoin d'attention.",
        "Peur": "Ces inquiétudes sont bien réelles pour vous. Il est courageux de les reconnaître et de les exprimer.",
        "Confusion": "Cette période d'incertitude peut être déstabilisante. Il est normal de se sentir perdu parfois."
    }
    
    return fallback_responses.get(state_name, 
        "Je vous entends et je comprends que vous traversez quelque chose d'important. Vos émotions sont légitimes.")

async def save_interaction_to_nocodb(user_id: str, message: str, ai_response: str, detected_state: Dict, session_id: str):
    """Sauvegarde l'interaction dans NocoDB"""
    try:
        if not NOCODB_API_TOKEN:
            print("⚠️ NocoDB non configuré, interaction non sauvegardée")
            return
        
        headers = {
            "xc-token": NOCODB_API_TOKEN,
            "Content-Type": "application/json"
        }
        
        interaction_data = {
            "user_id": user_id,
            "session_id": session_id,
            "user_message": message,
            "ai_response": ai_response,
            "detected_state_id": detected_state["state_id"],
            "detected_state_name": detected_state["state_name"],
            "confidence": detected_state["confidence"],
            "category": detected_state["category"],
            "energy_level": detected_state["energy_level"],
            "timestamp": datetime.now().isoformat(),
            "created_at": datetime.now().isoformat()
        }
        
        # Tentative de sauvegarde avec votre table ID spécifique
        table_endpoint = f"{NOCODB_BASE_URL}/api/v1/db/data/noco/flowme/reactions"
        if NOCODB_REACTIONS_TABLE_ID:
            table_endpoint = f"{NOCODB_BASE_URL}/api/v1/db/data/{NOCODB_REACTIONS_TABLE_ID}"
        
        response = await http_client.post(
            table_endpoint,
            headers=headers,
            json=interaction_data
        )
        
        if response.status_code in [200, 201]:
            print(f"✅ Interaction sauvegardée dans NocoDB")
        else:
            print(f"⚠️ Échec sauvegarde NocoDB: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Erreur sauvegarde NocoDB: {e}")

@app.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """Récupère l'historique d'une session"""
    try:
        if session_id in active_sessions:
            return {
                "session_id": session_id,
                "interactions": active_sessions[session_id],
                "total_messages": len(active_sessions[session_id])
            }
        else:
            raise HTTPException(status_code=404, detail="Session non trouvée")
    except Exception as e:
        print(f"❌ Erreur get_session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/analytics")
async def get_analytics():
    """Analytics simples des interactions"""
    try:
        total_sessions = len(active_sessions)
        total_interactions = sum(len(session) for session in active_sessions.values())
        
        # Analyse des états les plus fréquents
        state_frequency = {}
        for session in active_sessions.values():
            for interaction in session:
                state_name = interaction["state"]["state_name"]
                state_frequency[state_name] = state_frequency.get(state_name, 0) + 1
        
        return {
            "total_sessions": total_sessions,
            "total_interactions": total_interactions,
            "most_common_states": dict(sorted(state_frequency.items(), key=lambda x: x[1], reverse=True)[:5]),
            "active_sessions_count": len([s for s in active_sessions.values() if len(s) > 0])
        }
    except Exception as e:
        print(f"❌ Erreur analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============ GESTION DES ERREURS ============

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Gestionnaire d'erreurs HTTP personnalisé"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "message": exc.detail,
            "status_code": exc.status_code,
            "timestamp": datetime.now().isoformat()
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Gestionnaire d'erreurs générales"""
    print(f"❌ Erreur non gérée: {exc}")
    print(f"📍 Traceback: {traceback.format_exc()}")
    
    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "message": "Erreur interne du serveur",
            "timestamp": datetime.now().isoformat()
        }
    )

# ============ DÉMARRAGE ============

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
