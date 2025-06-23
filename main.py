"""
FlowMe v3 - API FastAPI Production
Intégration Mistral AI + NocoDB + Détection d'États
"""

import os
import logging
import sys
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict
import uvicorn

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import des modules FlowMe avec gestion d'erreurs
try:
    # Import conditionnel - fallback si modules manquants
    try:
        from core.flowme_core import flowme_core
        from services.nocodb_client import nocodb_client
        from core.mistral_client import mistral_client
        logger.info("✅ Modules FlowMe production chargés")
        PRODUCTION_MODE = True
    except ImportError as e:
        logger.warning(f"⚠️ Modules production non disponibles: {e}")
        logger.info("🔄 Fallback vers mode développement")
        PRODUCTION_MODE = False
        
        # Import de base pour fonctionnement minimal
        from flowme_states_detection import (
            detect_flowme_state_improved,
            get_state_description,
            get_state_advice,
            get_state_color,
            get_state_icon
        )
        
except Exception as e:
    logger.error(f"❌ Erreur critique lors du chargement: {e}")
    sys.exit(1)

# Configuration FastAPI
app = FastAPI(
    title="FlowMe v3 API",
    description="IA empathique basée sur 64 états de conscience - Architecture Stefan Hoareau",
    version="3.0.0",
    docs_url="/docs" if os.getenv("ENVIRONMENT") != "production" else None
)

# Middleware CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Modèles Pydantic
class MessageRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    context: Optional[Dict] = None

class MessageResponse(BaseModel):
    session_id: str
    timestamp: str
    user_message: str
    detected_state: Dict
    mistral_response: str
    context_analysis: Dict
    success: bool

# Routes statiques
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def root():
    """Page d'accueil FlowMe"""
    try:
        with open("static/flowme_64_interface.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read(), status_code=200)
    except FileNotFoundError:
        return HTMLResponse(
            content="""
            <html>
                <head><title>FlowMe v3</title></head>
                <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
                    <h1>🌊 FlowMe v3</h1>
                    <p>IA empathique - 64 états de conscience</p>
                    <p>Interface en cours de chargement...</p>
                    <div style="margin-top: 30px;">
                        <p><strong>Mode:</strong> """ + ("Production" if PRODUCTION_MODE else "Développement") + """</p>
                        <p><a href="/docs">Documentation API</a></p>
                        <p><a href="/health">État du système</a></p>
                    </div>
                </body>
            </html>
            """,
            status_code=200
        )

@app.post("/chat", response_model=MessageResponse)
async def chat(request: MessageRequest, background_tasks: BackgroundTasks):
    """
    Endpoint principal de conversation FlowMe
    Mode production ou développement selon disponibilité des modules
    """
    try:
        if not request.message or not request.message.strip():
            raise HTTPException(status_code=400, detail="Message vide")
        
        logger.info(f"Nouveau message reçu - Session: {request.session_id}")
        
        if PRODUCTION_MODE:
            # Mode production avec Mistral + NocoDB
            response = await flowme_core.generate_response(
                user_message=request.message.strip(),
                session_id=request.session_id,
                context=request.context
            )
            
            if not response.get("success"):
                raise HTTPException(
                    status_code=500, 
                    detail=response.get("error", "Erreur interne")
                )
                
        else:
            # Mode développement - fallback local
            response = await generate_fallback_response(
                request.message.strip(),
                request.session_id
            )
        
        logger.info(f"Réponse générée - État: {response['detected_state']['id']}")
        return JSONResponse(content=response)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur endpoint chat: {str(e)}")
        raise HTTPException(status_code=500, detail="Erreur serveur interne")

async def generate_fallback_response(message: str, session_id: Optional[str]) -> Dict:
    """Génère une réponse de fallback sans Mistral"""
    import uuid
    from datetime import datetime, timezone
    
    if not session_id:
        session_id = str(uuid.uuid4())
    
    # Détection d'état locale
    detected_state = detect_flowme_state_improved(message)
    
    # Réponse locale simple
    fallback_responses = {
        1: "Votre ouverture à cette expérience est remarquable. Qu'est-ce qui vous surprend le plus ?",
        8: "Je perçois une belle harmonie dans vos mots. Cette connexion semble importante pour vous.",
        14: "Cette énergie peut devenir une force positive. Comment pourriez-vous la canaliser ?",
        16: "La bienveillance transparaît dans votre message. Qu'est-ce qui nourrit cette chaleur ?",
        22: "Cette joie rayonne ! Qu'est-ce qui vous fait vibrer ainsi ?",
        32: "Merci pour cette authenticité. Votre expression est touchante.",
        40: "Votre réflexion semble profonde. Prenez le temps d'explorer ces pensées.",
        58: "Ces nuances font partie de la richesse humaine. Comment vivez-vous cette complexité ?"
    }
    
    mistral_response = fallback_responses.get(
        detected_state,
        "Je perçois votre état actuel. Pouvez-vous me dire ce que vous ressentez ?"
    )
    
    return {
        "session_id": session_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_message": message,
        "detected_state": {
            "id": detected_state,
            "name": get_state_description(detected_state),
            "description": get_state_description(detected_state),
            "advice": get_state_advice(detected_state),
            "color": get_state_color(detected_state),
            "icon": get_state_icon(detected_state)
        },
        "mistral_response": mistral_response,
        "context_analysis": {
            "has_violence": False,
            "has_love": False,
            "has_contradiction": False,
            "dominant_emotion": "neutre",
            "intensity": "moyenne"
        },
        "success": True,
        "mode": "development"
    }

@app.get("/states/{state_id}")
async def get_state_info(state_id: int):
    """Récupère les informations d'un état"""
    try:
        if not 1 <= state_id <= 64:
            raise HTTPException(status_code=400, detail="État invalide (1-64)")
        
        if PRODUCTION_MODE:
            # Mode production avec NocoDB
            brief = await nocodb_client.get_state_brief(state_id)
        else:
            brief = None
        
        # Fallback vers données locales
        state_info = {
            "id": state_id,
            "name": get_state_description(state_id),
            "brief": brief or get_state_description(state_id),
            "advice": get_state_advice(state_id),
            "color": get_state_color(state_id),
            "icon": get_state_icon(state_id),
            "source": "nocodb" if brief else "local",
            "mode": "production" if PRODUCTION_MODE else "development"
        }
        
        return JSONResponse(content=state_info)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur récupération état {state_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Erreur serveur")

@app.get("/health")
async def health_check():
    """Vérification de santé du système"""
    try:
        if PRODUCTION_MODE:
            health_status = await flowme_core.health_check()
        else:
            health_status = {
                "mistral_api": False,
                "nocodb": False,
                "states_cache": True,
                "overall_status": True,  # Fonctionnel en mode dev
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "mode": "development"
            }
        
        status_code = 200 if health_status["overall_status"] else 503
        
        return JSONResponse(
            content=health_status,
            status_code=status_code
        )
        
    except Exception as e:
        logger.error(f"Erreur health check: {str(e)}")
        return JSONResponse(
            content={
                "overall_status": False,
                "error": str(e),
                "timestamp": "error",
                "mode": "error"
            },
            status_code=503
        )

@app.get("/version")
async def get_version():
    """Informations de version"""
    return {
        "version": "3.0.0",
        "name": "FlowMe",
        "architecture": "Stefan Hoareau - 64 États de Conscience",
        "mode": "production" if PRODUCTION_MODE else "development",
        "components": {
            "detection": "flowme_states_detection.py",
            "llm": "Mistral AI" if PRODUCTION_MODE else "Local fallback",
            "database": "NocoDB" if PRODUCTION_MODE else "Memory",
            "framework": "FastAPI"
        },
        "features": [
            "Détection d'états de conscience",
            "Réponses empathiques" + (" IA" if PRODUCTION_MODE else " locales"),
            "Interface chat moderne",
            "Mode dégradé gracieux"
        ]
    }

# Gestionnaire d'erreurs global
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Erreur non gérée: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Erreur serveur interne",
            "error_type": type(exc).__name__,
            "mode": "production" if PRODUCTION_MODE else "development"
        }
    )

# Événements de démarrage/arrêt
@app.on_event("startup")
async def startup_event():
    """Initialisation au démarrage"""
    logger.info("🌊 FlowMe v3 - Démarrage en cours...")
    
    if PRODUCTION_MODE:
        try:
            health = await flowme_core.health_check()
            if health["overall_status"]:
                logger.info("✅ Mode production - Tous composants opérationnels")
            else:
                logger.warning("⚠️ Mode production - Composants partiels")
        except Exception as e:
            logger.error(f"❌ Erreur vérification production: {str(e)}")
    else:
        logger.info("🔧 Mode développement - Fonctionnalités de base actives")
    
    logger.info("🚀 FlowMe v3 démarré avec succès")

@app.on_event("shutdown")
async def shutdown_event():
    """Nettoyage à l'arrêt"""
    logger.info("🌊 FlowMe v3 - Arrêt en cours...")

if __name__ == "__main__":
    # Configuration pour le développement local
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=os.getenv("ENVIRONMENT") != "production",
        log_level="info"
    )
