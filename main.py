"""
FlowMe v3 - API Production avec Mistral AI + NocoDB
IA Empathique basée sur 96 États de Conscience (Stefan Hoareau)
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import uuid
import logging
from datetime import datetime
from typing import Optional, Dict, Any
import os

# Import des modules selon votre architecture
try:
    from services.mistral_service import mistral_service
    from services.nocodb_service import nocodb_service
except ImportError:
    # Fallback si structure différente
    try:
        from core.mistral_client import mistral_service
        from core.flowme_core import nocodb_service
    except ImportError:
        logger = logging.getLogger(__name__)
        logger.warning("Modules services non trouvés - mode dégradé")
        mistral_service = None
        nocodb_service = None

from flowme_states_detection import detect_consciousness_state, get_state_advice

# Configuration logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration FastAPI
app = FastAPI(
    title="FlowMe v3 - Production",
    description="IA Empathique avec Mistral AI + NocoDB - 96 États de Conscience",
    version="3.0.0"
)

# Modèles Pydantic
class ChatMessage(BaseModel):
    message: str
    session_id: Optional[str] = None

class FeedbackMessage(BaseModel):
    session_id: str
    record_id: str
    feedback: str

# Cache de session en mémoire
session_contexts = {}

@app.get("/", response_class=HTMLResponse)
async def get_interface():
    """Interface utilisateur moderne - Version Production"""
    
    # Détection du mode (production si services disponibles)
    is_production = mistral_service is not None and nocodb_service is not None
    mode_badge = "🚀 MODE PRODUCTION" if is_production else "⚡ MODE DÉGRADÉ"
    mode_color = "#48bb78" if is_production else "#ed8936"
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>FlowMe v3 - IA Empathique Production</title>
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
            
            .logo {{
                font-size: 2.5rem;
                margin-bottom: 10px;
            }}
            
            .title {{
                font-size: 1.8rem;
                color: #4a5568;
                margin-bottom: 5px;
                font-weight: 600;
            }}
            
            .subtitle {{
                color: #718096;
                font-size: 0.9rem;
                margin-bottom: 10px;
            }}
            
            .status {{
                display: inline-block;
                padding: 4px 12px;
                background: linear-gradient(45deg, {mode_color}, {mode_color});
                color: white;
                border-radius: 20px;
                font-size: 0.8rem;
                font-weight: 500;
            }}
            
            .features {{
                display: flex;
                justify-content: center;
                gap: 15px;
                margin: 15px 0;
                font-size: 0.7rem;
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
            
            .send-button:hover {{
                transform: translateY(-2px);
            }}
            
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
                <p class="subtitle">IA Empathique - 96 États de Conscience Stefan Hoareau</p>
                <span class="status">{mode_badge}</span>
                
                <div class="features">
                    <div class="feature">
                        <span>🧠</span> Mistral AI {'✅' if is_production else '⚠️'}
                    </div>
                    <div class="feature">
                        <span>💾</span> NocoDB {'✅' if is_production else '⚠️'}
                    </div>
                    <div class="feature">
                        <span>🎯</span> 96 États ✅
                    </div>
                </div>
            </div>
            
            <div class="chat-container" id="chat-container">
                <div class="message ai-message">
                    Bonjour ! Je suis FlowMe v3 {'en mode production avec Mistral AI' if is_production else 'en mode dégradé'}. 
                    Partagez ce que vous ressentez, je détecte votre état de conscience parmi les 96 états Stefan Hoareau et vous accompagne avec empathie. ✨
                    <div class="state-info">💫 Prêt à analyser vos émotions et états intérieurs</div>
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
            // Variables globales
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
                loadingDiv.innerHTML = '🧠 Analyse de votre état de conscience parmi les 96 états...';
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
                
                // Afficher le message utilisateur
                addMessage(message, true);
                messageInput.value = '';
                sendButton.disabled = true;
                
                // Afficher le loading
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
                        const stateInfo = `État ${{data.detected_state.state_id}}: ${{data.detected_state.state_name}} (${{data.detected_state.famille || 'Analyse'}})`;
                        addMessage(data.response, false, stateInfo);
                    }}
                }} catch (error) {{
                    removeLoading();
                    addMessage('❌ Erreur de connexion. Veuillez réessayer.', false);
                    console.error('Erreur:', error);
                }} finally {{
                    sendButton.disabled = false;
                    messageInput.focus();
                }}
            }}
            
            // Event listeners
            sendButton.addEventListener('click', sendMessage);
            messageInput.addEventListener('keypress', (e) => {{
                if (e.key === 'Enter') sendMessage();
            }});
            
            // Focus initial
            messageInput.focus();
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.post("/chat")
async def chat_endpoint(message: ChatMessage):
    """
    Endpoint principal de chat avec Mistral AI + NocoDB
    S'adapte à votre architecture existante
    """
    try:
        # Génération session si nécessaire
        session_id = message.session_id or str(uuid.uuid4())
        user_message = message.message.strip()
        
        if not user_message:
            raise HTTPException(status_code=400, detail="Message vide")
        
        logger.info(f"[{session_id[:8]}] Message reçu: {user_message[:50]}...")
        
        # 1. Détection de l'état de conscience (toujours disponible)
        detected_state = detect_consciousness_state(user_message)
        state_advice = get_state_advice(detected_state['state_id'])
        
        # Enrichissement des données d'état
        detected_state.update({
            'advice': state_advice,
            'source': 'mistral' if mistral_service and hasattr(mistral_service, 'api_key') else 'local'
        })
        
        logger.info(f"[{session_id[:8]}] État détecté: {detected_state['state_id']} - {detected_state['state_name']}")
        
        # 2. Génération de la réponse
        if mistral_service and hasattr(mistral_service, 'generate_empathic_response'):
            # Mode production avec Mistral AI
            try:
                # Récupération du contexte si NocoDB disponible
                conversation_context = []
                if nocodb_service and hasattr(nocodb_service, 'get_conversation_history'):
                    history = await nocodb_service.get_conversation_history(session_id, limit=4)
                    for record in reversed(history):
                        conversation_context.extend([
                            {"role": "user", "content": record.get('user_message', '')},
                            {"role": "assistant", "content": record.get('ai_response', '')}
                        ])
                
                ai_response = await mistral_service.generate_empathic_response(
                    user_message, 
                    detected_state,
                    conversation_context
                )
                
                logger.info(f"[{session_id[:8]}] Réponse Mistral générée")
                
            except Exception as e:
                logger.error(f"Erreur Mistral: {e}")
                ai_response = get_state_advice(detected_state['state_id']) or \
                             "Je vous entends et je respecte ce que vous traversez. Vous n'êtes pas seul(e)."
        else:
            # Mode dégradé avec réponses locales
            ai_response = get_state_advice(detected_state['state_id']) or \
                         "Je comprends votre état. Prenez le temps d'accueillir ce que vous ressentez."
        
        # 3. Sauvegarde dans NocoDB si disponible
        save_success = False
        if nocodb_service and hasattr(nocodb_service, 'save_reaction'):
            try:
                save_success = await nocodb_service.save_reaction(
                    session_id=session_id,
                    user_message=user_message,
                    detected_state=detected_state,
                    ai_response=ai_response
                )
                
                if save_success:
                    logger.info(f"[{session_id[:8]}] Interaction sauvegardée NocoDB")
                    
            except Exception as e:
                logger.error(f"Erreur sauvegarde NocoDB: {e}")
        
        # 4. Mise à jour du cache de session local
        if session_id not in session_contexts:
            session_contexts[session_id] = []
        
        session_contexts[session_id].append({
            'timestamp': datetime.utcnow().isoformat(),
            'user_message': user_message,
            'detected_state': detected_state,
            'ai_response': ai_response
        })
        
        # Limiter le cache
        if len(session_contexts[session_id]) > 10:
            session_contexts[session_id] = session_contexts[session_id][-10:]
        
        # 5. Réponse finale
        return JSONResponse({
            "success": True,
            "response": ai_response,
            "detected_state": {
                "state_id": detected_state['state_id'],
                "state_name": detected_state['state_name'],
                "famille": detected_state.get('famille', ''),
                "tension": detected_state.get('tension', ''),
                "confidence": detected_state.get('confidence', 0.0),
                "well_being_score": detected_state.get('well_being_score', 5.0),
                "advice": state_advice
            },
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat(),
            "services_status": {
                "mistral_available": mistral_service is not None,
                "nocodb_saved": save_success,
                "detection_engine": "flowme_v3_96_states"
            }
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur chat endpoint: {e}")
        
        # Réponse de secours
        try:
            fallback_state = detect_consciousness_state(user_message)
            fallback_response = get_state_advice(fallback_state['state_id']) or \
                              "Je vous entends et je respecte ce que vous traversez."
            
            return JSONResponse({
                "success": False,
                "response": fallback_response,
                "detected_state": {
                    "state_id": fallback_state['state_id'],
                    "state_name": fallback_state['state_name'],
                    "famille": fallback_state.get('famille', ''),
                    "confidence": 0.5,
                    "advice": "Mode de secours activé"
                },
                "session_id": session_id,
                "error": "Mode de secours - détection locale uniquement",
                "services_status": {
                    "mistral_available": False,
                    "nocodb_saved": False,
                    "detection_engine": "local_fallback"
                }
            })
        except:
            return JSONResponse({
                "success": False,
                "response": "Je rencontre une difficulté technique mais je reste à votre écoute.",
                "error": "Erreur système"
            })

@app.get("/health")
async def health_check():
    """
    Endpoint de santé adapté à votre architecture
    """
    try:
        services_status = {}
        
        # Test Mistral
        mistral_available = mistral_service is not None
        if mistral_available and hasattr(mistral_service, 'api_key'):
            services_status["mistral"] = {
                "configured": bool(mistral_service.api_key),
                "status": "available"
            }
        else:
            services_status["mistral"] = {
                "configured": False,
                "status": "not_configured"
            }
        
        # Test NocoDB
        if nocodb_service and hasattr(nocodb_service, 'health_check'):
            nocodb_status = await nocodb_service.health_check()
            services_status["nocodb"] = nocodb_status
        else:
            services_status["nocodb"] = {
                "configured": False,
                "status": "not_configured"
            }
        
        # Détection d'états (toujours disponible)
        services_status["state_detection"] = {
            "status": "operational",
            "states_count": 96,
            "engine": "stefan_hoareau_v3"
        }
        
        # Statut global
        production_ready = (
            services_status["mistral"].get("configured", False) and
            services_status["nocodb"].get("status") == "healthy"
        )
        
        return {
            "status": "healthy" if production_ready else "degraded",
            "mode": "production" if production_ready else "degraded",
            "timestamp": datetime.utcnow().isoformat(),
            "version": "3.0.0",
            "architecture": "stefan_hoareau_96_states",
            "services": services_status,
            "capabilities": {
                "ai_responses": services_status["mistral"].get("configured", False),
                "conversation_persistence": services_status["nocodb"].get("configured", False),
                "state_detection": True,
                "fallback_mode": True,
                "session_management": True
            }
        }
        
    except Exception as e:
        logger.error(f"Erreur health check: {e}")
        return {
            "status": "error",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }

@app.get("/states")
async def states_info():
    """
    Information sur les 96 états de conscience
    """
    return {
        "total_states": 96,
        "architecture": "Stefan Hoareau - Version Complète",
        "detection_method": "Pattern matching + Sentiment analysis + Familles symboliques",
        "categories": {
            "ecoute_subtile": "États de présence et attention",
            "exploration": "États de curiosité et découverte", 
            "resonance_empathique": "États de connexion émotionnelle",
            "discernement": "États d'analyse et clarté",
            "transformation": "États d'adaptation et changement"
        },
        "examples": {
            1: {"name": "Présence", "famille": "Écoute subtile"},
            8: {"name": "Résonance", "famille": "Vibration harmonique"},
            22: {"name": "Compassion", "famille": "Alignement interne"},
            32: {"name": "Carnage", "famille": "Observation pure"},
            58: {"name": "Inclusion", "famille": "Intégration"}
        },
        "data_source": "Base NocoDB avec 217 interactions réelles"
    }

# Gestion des erreurs
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return JSONResponse(
        status_code=404,
        content={
            "error": "Endpoint non trouvé",
            "available_endpoints": ["/", "/chat", "/health", "/states"]
        }
    )

# Événements de démarrage
@app.on_event("startup")
async def startup_event():
    logger.info("🚀 FlowMe v3 Production - Démarrage")
    logger.info(f"Mistral service: {'✅' if mistral_service else '❌'}")
    logger.info(f"NocoDB service: {'✅' if nocodb_service else '❌'}")
    logger.info("Détection 96 états: ✅")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
