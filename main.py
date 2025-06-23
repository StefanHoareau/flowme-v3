"""
FlowMe v3 - API Production avec Mistral AI + NocoDB
IA Empathique basée sur 64 États de Conscience (Stefan Hoareau)
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

# Import des services
from flowme_states_detection import detect_consciousness_state, get_state_advice
from services.mistral_service import mistral_service
from services.nocodb_service import nocodb_service

# Configuration logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration FastAPI
app = FastAPI(
    title="FlowMe v3 - Production",
    description="IA Empathique avec Mistral AI + NocoDB",
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

# Variables globales pour le cache de session
session_contexts = {}

@app.get("/", response_class=HTMLResponse)
async def get_interface():
    """Interface utilisateur moderne"""
    html_content = """
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>FlowMe v3 - IA Empathique Production</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
            }
            
            .container {
                background: rgba(255, 255, 255, 0.95);
                border-radius: 20px;
                padding: 30px;
                box-shadow: 0 20px 40px rgba(0,0,0,0.1);
                width: 100%;
                max-width: 500px;
                backdrop-filter: blur(10px);
            }
            
            .header {
                text-align: center;
                margin-bottom: 30px;
            }
            
            .logo {
                font-size: 2.5rem;
                margin-bottom: 10px;
            }
            
            .title {
                font-size: 1.8rem;
                color: #4a5568;
                margin-bottom: 5px;
                font-weight: 600;
            }
            
            .subtitle {
                color: #718096;
                font-size: 0.9rem;
                margin-bottom: 10px;
            }
            
            .status {
                display: inline-block;
                padding: 4px 12px;
                background: linear-gradient(45deg, #48bb78, #38a169);
                color: white;
                border-radius: 20px;
                font-size: 0.8rem;
                font-weight: 500;
            }
            
            .chat-container {
                margin-bottom: 20px;
                max-height: 300px;
                overflow-y: auto;
                padding: 15px;
                background: #f7fafc;
                border-radius: 10px;
                border: 1px solid #e2e8f0;
            }
            
            .message {
                margin-bottom: 15px;
                padding: 12px;
                border-radius: 10px;
                line-height: 1.5;
            }
            
            .user-message {
                background: linear-gradient(45deg, #667eea, #764ba2);
                color: white;
                margin-left: 20px;
            }
            
            .ai-message {
                background: #e6fffa;
                color: #234e52;
                margin-right: 20px;
                border-left: 4px solid #38b2ac;
            }
            
            .state-info {
                font-size: 0.8rem;
                color: #4a5568;
                margin-top: 5px;
                font-style: italic;
            }
            
            .input-container {
                display: flex;
                gap: 10px;
                margin-bottom: 15px;
            }
            
            .message-input {
                flex: 1;
                padding: 15px;
                border: 2px solid #e2e8f0;
                border-radius: 10px;
                font-size: 1rem;
                transition: border-color 0.3s;
            }
            
            .message-input:focus {
                outline: none;
                border-color: #667eea;
            }
            
            .send-button {
                padding: 15px 25px;
                background: linear-gradient(45deg, #667eea, #764ba2);
                color: white;
                border: none;
                border-radius: 10px;
                cursor: pointer;
                font-weight: 600;
                transition: transform 0.2s;
            }
            
            .send-button:hover {
                transform: translateY(-2px);
            }
            
            .send-button:disabled {
                opacity: 0.6;
                cursor: not-allowed;
                transform: none;
            }
            
            .session-info {
                text-align: center;
                font-size: 0.8rem;
                color: #718096;
                margin-top: 10px;
            }
            
            .loading {
                text-align: center;
                color: #667eea;
                font-style: italic;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="logo">🌊</div>
                <h1 class="title">FlowMe v3</h1>
                <p class="subtitle">IA Empathique basée sur 64 États de Conscience</p>
                <span class="status">🚀 MODE PRODUCTION</span>
            </div>
            
            <div class="chat-container" id="chat-container">
                <div class="message ai-message">
                    Bonjour ! Je suis FlowMe v3 en mode production avec Mistral AI. 
                    Partagez ce que vous ressentez, je vous accompagne avec empathie. ✨
                    <div class="state-info">💫 Prêt à détecter vos états de conscience</div>
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
            
            function generateSessionId() {
                return 'sess_' + Math.random().toString(36).substr(2, 9) + '_' + Date.now().toString(36);
            }
            
            function addMessage(content, isUser = false, stateInfo = null) {
                const messageDiv = document.createElement('div');
                messageDiv.className = `message ${isUser ? 'user-message' : 'ai-message'}`;
                
                let html = content;
                if (stateInfo && !isUser) {
                    html += `<div class="state-info">🎯 ${stateInfo}</div>`;
                }
                
                messageDiv.innerHTML = html;
                chatContainer.appendChild(messageDiv);
                chatContainer.scrollTop = chatContainer.scrollHeight;
            }
            
            function showLoading() {
                const loadingDiv = document.createElement('div');
                loadingDiv.className = 'message ai-message loading';
                loadingDiv.id = 'loading-message';
                loadingDiv.innerHTML = '🧠 Analyse de votre état de conscience...';
                chatContainer.appendChild(loadingDiv);
                chatContainer.scrollTop = chatContainer.scrollHeight;
            }
            
            function removeLoading() {
                const loading = document.getElementById('loading-message');
                if (loading) loading.remove();
            }
            
            async function sendMessage() {
                const message = messageInput.value.trim();
                if (!message) return;
                
                // Afficher le message utilisateur
                addMessage(message, true);
                messageInput.value = '';
                sendButton.disabled = true;
                
                // Afficher le loading
                showLoading();
                
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
                    removeLoading();
                    
                    if (data.error) {
                        addMessage(`❌ Erreur: ${data.error}`, false);
                    } else {
                        const stateInfo = `État ${data.detected_state.state_id}: ${data.detected_state.state_name}`;
                        addMessage(data.response, false, stateInfo);
                    }
                } catch (error) {
                    removeLoading();
                    addMessage('❌ Erreur de connexion. Veuillez réessayer.', false);
                    console.error('Erreur:', error);
                } finally {
                    sendButton.disabled = false;
                    messageInput.focus();
                }
            }
            
            // Event listeners
            sendButton.addEventListener('click', sendMessage);
            messageInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') sendMessage();
            });
            
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
    """
    try:
        # Génération session si nécessaire
        session_id = message.session_id or str(uuid.uuid4())
        user_message = message.message.strip()
        
        if not user_message:
            raise HTTPException(status_code=400, detail="Message vide")
        
        logger.info(f"[{session_id[:8]}] Message reçu: {user_message[:50]}...")
        
        # 1. Détection de l'état de conscience
        detected_state = detect_consciousness_state(user_message)
        state_advice = get_state_advice(detected_state['state_id'])
        
        # Enrichissement des données d'état
        detected_state.update({
            'advice': state_advice,
            'source': 'mistral' if mistral_service.api_key else 'local'
        })
        
        logger.info(f"[{session_id[:8]}] État détecté: {detected_state['state_id']} - {detected_state['state_name']}")
        
        # 2. Récupération du contexte de conversation
        conversation_context = await nocodb_service.get_conversation_history(
            session_id, limit=4
        )
        
        # Conversion pour Mistral
        mistral_context = []
        for record in reversed(conversation_context):  # Plus ancien vers plus récent
            mistral_context.extend([
                {"role": "user", "content": record.get('user_message', '')},
                {"role": "assistant", "content": record.get('ai_response', '')}
            ])
        
        # 3. Génération de la réponse avec Mistral AI
        ai_response = await mistral_service.generate_empathic_response(
            user_message, 
            detected_state,
            mistral_context
        )
        
        logger.info(f"[{session_id[:8]}] Réponse générée: {ai_response[:50]}...")
        
        # 4. Sauvegarde dans NocoDB
        save_success = await nocodb_service.save_reaction(
            session_id=session_id,
            user_message=user_message,
            detected_state=detected_state,
            ai_response=ai_response
        )
        
        if save_success:
            logger.info(f"[{session_id[:8]}] Interaction sauvegardée")
        else:
            logger.warning(f"[{session_id[:8]}] Échec sauvegarde NocoDB")
        
        # 5. Mise à jour du cache de session
        if session_id not in session_contexts:
            session_contexts[session_id] = []
        
        session_contexts[session_id].append({
            'timestamp': datetime.utcnow().isoformat(),
            'user_message': user_message,
            'detected_state': detected_state,
            'ai_response': ai_response
        })
        
        # Limiter le cache à 10 interactions
        if len(session_contexts[session_id]) > 10:
            session_contexts[session_id] = session_contexts[session_id][-10:]
        
        # Réponse finale
        return JSONResponse({
            "success": True,
            "response": ai_response,
            "detected_state": {
                "state_id": detected_state['state_id'],
                "state_name": detected_state['state_name'],
                "confidence": detected_state.get('confidence', 0.0),
                "advice": state_advice
            },
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat(),
            "services_status": {
                "mistral_available": bool(mistral_service.api_key),
                "nocodb_saved": save_success
            }
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur chat endpoint: {e}")
        
        # Réponse de secours en cas d'erreur
        fallback_state = detect_consciousness_state(user_message)
        fallback_response = get_state_advice(fallback_state['state_id']) or \
                          "Je vous entends et je respecte ce que vous traversez. Vous n'êtes pas seul(e)."
        
        return JSONResponse({
            "success": False,
            "response": fallback_response,
            "detected_state": {
                "state_id": fallback_state['state_id'],
                "state_name": fallback_state['state_name'],
                "confidence": fallback_state.get('confidence', 0.0),
                "advice": "Mode dégradé activé"
            },
            "session_id": session_id,
            "error": "Erreur interne - mode dégradé activé",
            "services_status": {
                "mistral_available": False,
                "nocodb_saved": False
            }
        })

@app.post("/feedback")
async def feedback_endpoint(feedback: FeedbackMessage):
    """
    Endpoint pour recevoir les retours utilisateur
    """
    try:
        success = await nocodb_service.update_feedback(
            feedback.record_id, 
            feedback.feedback
        )
        
        if success:
            logger.info(f"Feedback reçu pour {feedback.record_id}: {feedback.feedback}")
            return {"success": True, "message": "Feedback enregistré"}
        else:
            return {"success": False, "message": "Erreur sauvegarde feedback"}
            
    except Exception as e:
        logger.error(f"Erreur feedback: {e}")
        return {"success": False, "message": "Erreur interne"}

@app.get("/health")
async def health_check():
    """
    Endpoint de santé avec statut des services
    """
    try:
        # Test Mistral
        mistral_status = {
            "configured": bool(mistral_service.api_key),
            "model": mistral_service.model if mistral_service.api_key else None
        }
        
        # Test NocoDB
        nocodb_status = await nocodb_service.health_check()
        
        # Statut global
        all_healthy = (
            mistral_status["configured"] and 
            nocodb_status.get("status") == "healthy"
        )
        
        return {
            "status": "healthy" if all_healthy else "degraded",
            "timestamp": datetime.utcnow().isoformat(),
            "version": "3.0.0",
            "mode": "production" if all_healthy else "degraded",
            "services": {
                "mistral": mistral_status,
                "nocodb": nocodb_status,
                "state_detection": {"status": "operational"}
            },
            "features": {
                "ai_responses": mistral_status["configured"],
                "conversation_persistence": nocodb_status.get("configured", False),
                "state_detection": True,
                "fallback_responses": True
            }
        }
        
    except Exception as e:
        logger.error(f"Erreur health check: {e}")
        return {
            "status": "error",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }

@app.get("/analytics")
async def analytics_endpoint(days: int = 7):
    """
    Endpoint d'analytics (nécessite NocoDB)
    """
    try:
        if not nocodb_service._is_configured():
            return {
                "error": "Analytics nécessite NocoDB configuré",
                "available": False
            }
        
        analytics = await nocodb_service.get_analytics(days)
        
        return {
            "success": True,
            "analytics": analytics,
            "generated_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Erreur analytics: {e}")
        return {
            "success": False,
            "error": str(e)
        }

@app.get("/states")
async def states_info():
    """
    Endpoint d'information sur les 64 états de conscience
    """
    return {
        "total_states": 64,
        "architecture": "Stefan Hoareau",
        "detection_method": "Pattern matching + sentiment analysis",
        "examples": {
            1: "Émerveillement - Ouverture à la nouveauté",
            8: "Résonance - Harmonie et connexion",
            16: "Amour - Expression de l'affection",
            22: "Compassion - Empathie profonde",
            32: "Carnage - Intensité destructrice",
            40: "Réflexion - Analyse et contemplation",
            58: "Inclusion - Intégration des contradictions"
        },
        "documentation": "Basé sur les travaux de Stefan Hoareau"
    }

# Gestion des erreurs globales
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return JSONResponse(
        status_code=404,
        content={
            "error": "Endpoint non trouvé",
            "available_endpoints": [
                "/", "/chat", "/health", "/analytics", "/states", "/feedback"
            ]
        }
    )

@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    logger.error(f"Erreur interne: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Erreur interne du serveur",
            "message": "Mode dégradé activé automatiquement"
        }
    )

# Événements de démarrage
@app.on_event("startup")
async def startup_event():
    logger.info("🚀 FlowMe v3 Production - Démarrage")
    logger.info(f"Mistral configuré: {bool(mistral_service.api_key)}")
    logger.info(f"NocoDB configuré: {nocodb_service._is_configured()}")
    
    # Test initial des services
    health = await health_check()
    logger.info(f"État des services: {health['status']}")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("🛑 FlowMe v3 Production - Arrêt")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
