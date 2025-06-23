"""
FlowMe v3 - API FastAPI Production
Intégration Mistral AI + NocoDB + Détection d'États
"""

import os
import logging
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

# Import des modules FlowMe
try:
    from core.flowme_core import flowme_core
    from services.nocodb_client import nocodb_client
    from core.mistral_client import mistral_client
    logger.info("Modules FlowMe chargés avec succès")
except ImportError as e:
    logger.error(f"Erreur import modules FlowMe: {e}")
    raise

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
                <body>
                    <h1>🌊 FlowMe v3</h1>
                    <p>IA empathique - 64 états de conscience</p>
                    <p>Interface en cours de chargement...</p>
                </body>
            </html>
            """,
            status_code=200
        )

@app.post("/chat", response_model=MessageResponse)
async def chat(request: MessageRequest, background_tasks: BackgroundTasks):
    """
    Endpoint principal de conversation FlowMe
    
    Processus :
    1. Détection d'état de conscience
    2. Génération réponse Mistral
    3. Sauvegarde NocoDB (async)
    4. Retour réponse enrichie
    """
    try:
        if not request.message or not request.message.strip():
            raise HTTPException(status_code=400, detail="Message vide")
        
        logger.info(f"Nouveau message reçu - Session: {request.session_id}")
        
        # Génération réponse FlowMe complète
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
        
        logger.info(f"Réponse générée - État: {response['detected_state']['id']}")
        return JSONResponse(content=response)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur endpoint chat: {str(e)}")
        raise HTTPException(status_code=500, detail="Erreur serveur interne")

@app.get("/states/{state_id}")
async def get_state_info(state_id: int):
    """Récupère les informations détaillées d'un état"""
    try:
        if not 1 <= state_id <= 64:
            raise HTTPException(status_code=400, detail="État invalide (1-64)")
        
        # Tentative récupération depuis NocoDB
        brief = await nocodb_client.get_state_brief(state_id)
        
        # Fallback vers les données locales
        from flowme_states_detection import (
            get_state_description, get_state_advice, 
            get_state_color, get_state_icon
        )
        
        state_info = {
            "id": state_id,
            "name": get_state_description(state_id),
            "brief": brief or get_state_description(state_id),
            "advice": get_state_advice(state_id),
            "color": get_state_color(state_id),
            "icon": get_state_icon(state_id),
            "source": "nocodb" if brief else "local"
        }
        
        return JSONResponse(content=state_info)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur récupération état {state_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Erreur serveur")

@app.get("/session/{session_id}/summary")
async def get_session_summary(session_id: str):
    """Récupère le résumé d'une session"""
    try:
        summary = await flowme_core.get_session_summary(session_id)
        return JSONResponse(content=summary)
        
    except Exception as e:
        logger.error(f"Erreur résumé session {session_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Erreur serveur")

@app.get("/analytics")
async def get_analytics(days: int = 7):
    """Récupère les analytiques d'usage"""
    try:
        if not 1 <= days <= 30:
            raise HTTPException(status_code=400, detail="Période invalide (1-30 jours)")
        
        analytics = await nocodb_client.get_analytics_summary(days)
        return JSONResponse(content=analytics)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur analytiques: {str(e)}")
        raise HTTPException(status_code=500, detail="Erreur serveur")

@app.get("/health")
async def health_check():
    """Vérification de santé complète du système"""
    try:
        health_status = await flowme_core.health_check()
        
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
                "timestamp": "error"
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
        "components": {
            "detection": "flowme_states_detection.py",
            "llm": "Mistral AI",
            "database": "NocoDB",
            "framework": "FastAPI"
        },
        "features": [
            "Détection d'états de conscience",
            "Réponses empathiques IA",
            "Persistance conversations",
            "Analytiques d'usage"
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
            "error_type": type(exc).__name__
        }
    )

# Événements de démarrage/arrêt
@app.on_event("startup")
async def startup_event():
    """Initialisation au démarrage"""
    logger.info("🌊 FlowMe v3 - Démarrage en cours...")
    
    # Vérification des composants
    try:
        health = await flowme_core.health_check()
        
        if health["overall_status"]:
            logger.info("✅ Tous les composants sont opérationnels")
        else:
            logger.warning("⚠️ Certains composants ne sont pas disponibles")
            logger.warning(f"Status: {health}")
        
        logger.info("🚀 FlowMe v3 démarré avec succès")
        
    except Exception as e:
        logger.error(f"❌ Erreur lors du démarrage: {str(e)}")

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
