import os
import asyncio
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import uvicorn
import logging

# Import du module FlowMe intégré
from flowme_detector import create_flowme_detector, FlowMeStateDetector

# Configuration des logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration depuis les variables d'environnement
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
NOCODB_URL = os.getenv("NOCODB_URL", "https://app.nocodb.com")
NOCODB_API_KEY = os.getenv("NOCODB_API_KEY")

# Initialisation FastAPI
app = FastAPI(title="FlowMe v3", version="3.0.0")

# Variable globale pour le détecteur FlowMe
flowme_detector: FlowMeStateDetector = None

# Modèles Pydantic
class MessageRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str
    state_detected: str
    confidence: float
    timestamp: str

@app.on_event("startup")
async def startup_event():
    """Initialisation au démarrage"""
    global flowme_detector
    
    # Vérification des variables d'environnement
    if not MISTRAL_API_KEY:
        logger.error("❌ MISTRAL_API_KEY manquante")
        raise Exception("Configuration Mistral manquante")
    
    if not NOCODB_API_KEY:
        logger.warning("⚠️ NOCODB_API_KEY manquante - mode dégradé")
    
    try:
        # Initialisation du détecteur FlowMe
        flowme_detector = await create_flowme_detector(
            nocodb_url=NOCODB_URL,
            nocodb_api_key=NOCODB_API_KEY,
            mistral_api_key=MISTRAL_API_KEY
        )
        
        logger.info("✅ Module flowme_states_detection intégré avec succès")
        logger.info("🚀 Démarrage de FlowMe v3")
        logger.info(f"✅ Mistral API: {'✓ Configuré' if MISTRAL_API_KEY else '❌ Manquante'}")
        logger.info(f"✅ NocoDB: {'✓ Configuré' if NOCODB_API_KEY else '⚠️ Mode dégradé'}")
        logger.info(f"📊 États disponibles: {len(flowme_detector.flowme_states)}")
        
    except Exception as e:
        logger.error(f"❌ Erreur d'initialisation: {e}")
        raise

@app.get("/")
async def serve_homepage():
    """Sert la page d'accueil FlowMe v3"""
    try:
        with open("static/flowme_64_interface.html", "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content)
    except FileNotFoundError:
        # HTML de base si le fichier n'existe pas
        html_content = """
        <!DOCTYPE html>
        <html lang="fr">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>FlowMe v3</title>
            <style>
                body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
                .container { background: #f5f5f5; padding: 20px; border-radius: 10px; }
                .message-input { width: 100%; padding: 10px; margin: 10px 0; border-radius: 5px; border: 1px solid #ddd; }
                .send-button { background: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; }
                .response { background: white; padding: 15px; margin: 10px 0; border-radius: 5px; border-left: 4px solid #007bff; }
                .state-info { color: #666; font-size: 0.9em; margin-top: 5px; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>FlowMe v3 - Accompagnement Émotionnel</h1>
                <div id="chat-container">
                    <textarea id="message-input" class="message-input" placeholder="Exprime-toi librement..." rows="3"></textarea>
                    <button onclick="sendMessage()" class="send-button">Envoyer</button>
                    <div id="responses"></div>
                </div>
            </div>
            
            <script>
                async function sendMessage() {
                    const input = document.getElementById('message-input');
                    const message = input.value.trim();
                    if (!message) return;
                    
                    const responsesDiv = document.getElementById('responses');
                    
                    try {
                        const response = await fetch('/chat', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({message: message})
                        });
                        
                        const data = await response.json();
                        
                        const responseDiv = document.createElement('div');
                        responseDiv.className = 'response';
                        responseDiv.innerHTML = `
                            <p><strong>Toi:</strong> ${message}</p>
                            <p><strong>FlowMe:</strong> ${data.response}</p>
                            <div class="state-info">État détecté: ${data.state_detected} (${Math.round(data.confidence * 100)}% confiance)</div>
                        `;
                        
                        responsesDiv.appendChild(responseDiv);
                        input.value = '';
                        
                    } catch (error) {
                        console.error('Erreur:', error);
                        alert('Erreur de communication avec FlowMe');
                    }
                }
                
                // Envoi avec Entrée
                document.getElementById('message-input').addEventListener('keypress', function(e) {
                    if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        sendMessage();
                    }
                });
            </script>
        </body>
        </html>
        """
        return HTMLResponse(content=html_content)

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: MessageRequest):
    """Endpoint principal pour les conversations"""
    if not flowme_detector:
        raise HTTPException(status_code=500, detail="FlowMe non initialisé")
    
    try:
        # Analyse émotionnelle et génération de réponse
        detected_state, empathic_response = await flowme_detector.analyze_emotional_state(
            request.message
        )
        
        # Préparation de la réponse
        response = ChatResponse(
            response=empathic_response,
            state_detected=detected_state.get("Nom_État", "Présence"),
            confidence=0.8,  # Sera dynamique avec les améliorations futures
            timestamp=datetime.utcnow().isoformat()
        )
        
        logger.info(f"💬 Message traité - État: {response.state_detected}")
        return response
        
    except Exception as e:
        logger.error(f"Erreur dans /chat: {e}")
        raise HTTPException(status_code=500, detail="Erreur de traitement")

@app.get("/health")
async def health_check():
    """Endpoint de santé pour vérifier le statut"""
    return {
        "status": "healthy",
        "version": "3.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "mistral_configured": bool(MISTRAL_API_KEY),
        "nocodb_configured": bool(NOCODB_API_KEY),
        "states_loaded": len(flowme_detector.flowme_states) if flowme_detector else 0
    }

@app.get("/states")
async def get_states():
    """Retourne la liste des états FlowMe disponibles"""
    if not flowme_detector:
        return {"error": "FlowMe non initialisé"}
    
    states = []
    for state in flowme_detector.flowme_states.values():
        states.append({
            "id": state.get("ID_État"),
            "nom": state.get("Nom_État"),
            "famille": state.get("Famille_Symbolique"),
            "conseil": state.get("Conseil_Flowme")
        })
    
    return {"states": states, "total": len(states)}

# Servir les fichiers statiques si le dossier existe
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
except Exception:
    logger.warning("⚠️ Dossier static non trouvé")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    
    # ⚠️ IMPORTANT: Ne pas utiliser app.run() pour FastAPI
    # Render doit utiliser: uvicorn main:app --host 0.0.0.0 --port $PORT
    
    print("🚀 Pour démarrer FlowMe v3:")
    print(f"   uvicorn main:app --host 0.0.0.0 --port {port}")
    print("   Ou configurez Render avec cette Start Command")
