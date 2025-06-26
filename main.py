import os
import asyncio
import json
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import uvicorn
import httpx
import logging

# Configuration des logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration depuis les variables d'environnement
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
NOCODB_URL = os.getenv("NOCODB_URL", "https://app.nocodb.com")
NOCODB_API_KEY = os.getenv("NOCODB_API_KEY")
NOCODB_STATES_TABLE_ID = os.getenv("NOCODB_STATES_TABLE_ID")
NOCODB_REACTIONS_TABLE_ID = os.getenv("NOCODB_REACTIONS_TABLE_ID")

# ==========================================
# MODULE FLOWME DETECTOR INTÉGRÉ
# ==========================================

class FlowMeStateDetector:
    def __init__(self, nocodb_url: str, nocodb_api_key: str, mistral_api_key: str, states_table_id: str = None, reactions_table_id: str = None):
        self.nocodb_url = nocodb_url
        self.nocodb_api_key = nocodb_api_key
        self.mistral_api_key = mistral_api_key
        self.states_table_id = states_table_id
        self.reactions_table_id = reactions_table_id
        self.flowme_states = {}
        self.mistral_client = httpx.AsyncClient()
        
    async def initialize(self):
        """Charge les états FlowMe (NocoDB ou par défaut)"""
        try:
            if self.nocodb_api_key and self.states_table_id:
                headers = {"xc-token": self.nocodb_api_key}
                response = await self.mistral_client.get(
                    f"{self.nocodb_url}/api/v1/db/data/noco/{self.states_table_id}", 
                    headers=headers
                )
                
                if response.status_code == 200:
                    states_data = response.json()
                    self.flowme_states = {
                        state["ID_État"]: state for state in states_data.get("list", [])
                    }
                    logger.info(f"✅ {len(self.flowme_states)} états FlowMe chargés depuis NocoDB")
                else:
                    logger.warning(f"❌ Échec chargement NocoDB (HTTP {response.status_code}), utilisation états par défaut")
                    self._load_default_states()
            else:
                logger.warning("⚠️ NOCODB_API_KEY ou STATES_TABLE_ID manquants, utilisation états par défaut")
                self._load_default_states()
                
        except Exception as e:
            logger.error(f"Erreur chargement états: {e}")
            self._load_default_states()
    
    def _load_default_states(self):
        """États FlowMe par défaut (basés sur tes CSV)"""
        self.flowme_states = {
            1: {
                "ID_État": 1,
                "Nom_État": "Présence",
                "Famille_Symbolique": "Écoute subtile",
                "Tension_Dominante": "Latente, intérieure",
                "Mot_Clé": "Perception",
                "Conseil_Flowme": "Quand tout semble brumeux, c'est dans le silence que la clarté peut émerger"
            },
            2: {
                "ID_État": 2,
                "Nom_État": "Éveil",
                "Famille_Symbolique": "Conscience primordiale",
                "Tension_Dominante": "Émergente",
                "Mot_Clé": "Conscience",
                "Conseil_Flowme": "Laisse les impressions se déposer avant de les catégoriser"
            },
            3: {
                "ID_État": 3,
                "Nom_État": "Curiosité",
                "Famille_Symbolique": "Exploration",
                "Tension_Dominante": "Dynamique",
                "Mot_Clé": "Découverte",
                "Conseil_Flowme": "L'inconnu n'est pas un vide à combler mais un espace à explorer"
            },
            4: {
                "ID_État": 4,
                "Nom_État": "Joie",
                "Famille_Symbolique": "Réveil & accord",
                "Tension_Dominante": "Expansive",
                "Mot_Clé": "Épanouissement",
                "Conseil_Flowme": "Savoure ce moment, il nourrit ton élan pour demain"
            },
            5: {
                "ID_État": 5,
                "Nom_État": "Tristesse",
                "Famille_Symbolique": "Recul & germination",
                "Tension_Dominante": "Introspective",
                "Mot_Clé": "Mélancolie",
                "Conseil_Flowme": "La tristesse creuse en toi l'espace nécessaire à la joie future"
            },
            6: {
                "ID_État": 6,
                "Nom_État": "Colère",
                "Famille_Symbolique": "Montée & excès",
                "Tension_Dominante": "Explosive",
                "Mot_Clé": "Révolte",
                "Conseil_Flowme": "Cette énergie puissante cherche à transformer quelque chose d'important"
            },
            7: {
                "ID_État": 7,
                "Nom_État": "Peur",
                "Famille_Symbolique": "Fracture & basculement",
                "Tension_Dominante": "Contractée",
                "Mot_Clé": "Inquiétude",
                "Conseil_Flowme": "La peur te signale ce qui compte vraiment pour toi"
            },
            8: {
                "ID_État": 8,
                "Nom_État": "Amour",
                "Famille_Symbolique": "Réveil & accord",
                "Tension_Dominante": "Rayonnante",
                "Mot_Clé": "Connexion",
                "Conseil_Flowme": "L'amour que tu donnes revient toujours, transformé et amplifié"
            },
            9: {
                "ID_État": 9,
                "Nom_État": "Solitude",
                "Famille_Symbolique": "Recul & germination",
                "Tension_Dominante": "Repliée",
                "Mot_Clé": "Isolement",
                "Conseil_Flowme": "La solitude peut être un refuge pour retrouver ta propre essence"
            },
            10: {
                "ID_État": 10,
                "Nom_État": "Confusion",
                "Famille_Symbolique": "Faux équilibre",
                "Tension_Dominante": "Dispersée",
                "Mot_Clé": "Questionnement",
                "Conseil_Flowme": "La confusion précède souvent une nouvelle clarté plus profonde"
            }
        }
    
    async def analyze_emotional_state(self, message: str) -> Tuple[Dict, str]:
        """Analyse l'état émotionnel et génère une réponse empathique"""
        try:
            # 1. Détection de l'état émotionnel
            detected_state, confidence = await self._detect_state(message)
            
            # 2. Génération de la réponse empathique
            empathic_response = await self._generate_empathic_response(
                message, detected_state, confidence
            )
            
            # 3. Sauvegarde dans NocoDB (optionnel)
            await self._save_to_nocodb(message, detected_state, confidence, empathic_response)
            
            return detected_state, empathic_response
            
        except Exception as e:
            logger.error(f"Erreur lors de l'analyse: {e}")
            return self._get_default_state(), "Je suis là pour t'écouter. Peux-tu me dire ce que tu ressens en ce moment ?"
    
    async def _detect_state(self, message: str) -> Tuple[Dict, float]:
        """Détecte l'état émotionnel via Mistral"""
        
        # Analyse simple par mots-clés si pas de Mistral
        if not self.mistral_api_key:
            return self._detect_by_keywords(message)
        
        detection_prompt = f"""
        Analyse ce message et identifie l'état émotionnel principal parmi : Présence, Éveil, Curiosité, Joie, Tristesse, Colère, Peur, Amour, Solitude, Confusion
        
        Message : "{message}"
        
        Réponds STRICTEMENT ce format JSON sans aucun autre texte :
        {{"etat": "nom_etat", "confiance": 0.8}}
        """
        
        try:
            headers = {
                "Authorization": f"Bearer {self.mistral_api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": "mistral-small-latest",
                "messages": [{"role": "user", "content": detection_prompt}],
                "max_tokens": 100,
                "temperature": 0.3
            }
            
            response = await self.mistral_client.post(
                "https://api.mistral.ai/v1/chat/completions",
                headers=headers,
                json=payload
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                
                try:
                    parsed = json.loads(content)
                    state_name = parsed.get("etat", "Présence")
                    confidence = float(parsed.get("confiance", 0.5))
                    
                    detected_state = self._find_state_by_name(state_name)
                    return detected_state, confidence
                    
                except json.JSONDecodeError:
                    logger.warning("Réponse Mistral non-JSON")
                    
        except Exception as e:
            logger.error(f"Erreur Mistral: {e}")
            
        return self._detect_by_keywords(message)
    
    def _detect_by_keywords(self, message: str) -> Tuple[Dict, float]:
        """Détection simple par mots-clés"""
        message_lower = message.lower()
        
        # Mots-clés pour chaque état
        keywords = {
            "Joie": ["joie", "heureux", "content", "bonheur", "sourire", "génial", "super"],
            "Tristesse": ["triste", "pleurer", "mélancolie", "déprimé", "nostalgie", "chagrin"],
            "Colère": ["colère", "énervé", "furieux", "rage", "frustré", "irrité"],
            "Peur": ["peur", "anxieux", "inquiet", "stress", "angoisse", "effrayé"],
            "Amour": ["amour", "aimer", "tendresse", "affection", "câlin", "cœur"],
            "Solitude": ["seul", "isolé", "abandonné", "solitude", "vide"],
            "Confusion": ["confus", "perdu", "ne sais pas", "bizarre", "étrange"],
            "Curiosité": ["pourquoi", "comment", "découvrir", "explorer", "intéressant"]
        }
        
        for state_name, words in keywords.items():
            for word in words:
                if word in message_lower:
                    state = self._find_state_by_name(state_name)
                    return state, 0.7
        
        return self._get_default_state(), 0.5
    
    async def _generate_empathic_response(self, message: str, state: Dict, confidence: float) -> str:
        """Génère une réponse empathique"""
        
        state_name = state.get("Nom_État", "Présence")
        conseil = state.get("Conseil_Flowme", "")
        
        if not self.mistral_api_key:
            return f"Je sens que tu traverses un moment de {state_name.lower()}. {conseil}"
        
        empathy_prompt = f"""
        Tu es FlowMe, une IA empathique et bienveillante.
        
        L'utilisateur a écrit : "{message}"
        État détecté : {state_name}
        Conseil FlowMe : {conseil}
        
        Génère une réponse empathique (100 mots max) qui :
        - Reconnaît l'émotion sans jugement
        - Offre un soutien adapté
        - Intègre subtilement le conseil
        - Reste naturelle et chaleureuse
        """
        
        try:
            headers = {
                "Authorization": f"Bearer {self.mistral_api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": "mistral-small-latest",
                "messages": [{"role": "user", "content": empathy_prompt}],
                "max_tokens": 150,
                "temperature": 0.7
            }
            
            response = await self.mistral_client.post(
                "https://api.mistral.ai/v1/chat/completions",
                headers=headers,
                json=payload
            )
            
            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]["content"].strip()
                
        except Exception as e:
            logger.error(f"Erreur génération réponse: {e}")
            
        return f"Je perçois que tu traverses un moment de {state_name.lower()}. {conseil}"
    
    async def _save_to_nocodb(self, message: str, state: Dict, confidence: float, response: str):
        """Sauvegarde optionnelle dans NocoDB"""
        if not self.nocodb_api_key or not self.reactions_table_id:
            return
            
        try:
            headers = {"xc-token": self.nocodb_api_key}
            data = {
                "etat_id_flowme": state.get("ID_État"),
                "tension_dominante": state.get("Tension_Dominante"),
                "famille_symbolique": state.get("Famille_Symbolique"),
                "timestamp": datetime.utcnow().isoformat(),
                "etat_nom": state.get("Nom_État"),
                "pattern_detecte": message[:100],
                "score_bien_etre": confidence,
                "recommandations": response
            }
            
            response_save = await self.mistral_client.post(
                f"{self.nocodb_url}/api/v1/db/data/noco/{self.reactions_table_id}",
                headers=headers,
                json=data
            )
            
            if response_save.status_code == 200:
                logger.info("✅ Interaction sauvegardée dans NocoDB")
            else:
                logger.warning(f"❌ Échec sauvegarde NocoDB: {response_save.status_code}")
                
        except Exception as e:
            logger.error(f"Erreur sauvegarde NocoDB: {e}")
    
    def _find_state_by_name(self, name: str) -> Dict:
        """Trouve un état par son nom"""
        for state in self.flowme_states.values():
            if state.get("Nom_État", "").lower() == name.lower():
                return state
        return self._get_default_state()
    
    def _get_default_state(self) -> Dict:
        """Retourne l'état par défaut"""
        return list(self.flowme_states.values())[0] if self.flowme_states else {
            "ID_État": 1,
            "Nom_État": "Présence",
            "Famille_Symbolique": "Écoute subtile",
            "Conseil_Flowme": "Je suis là pour t'écouter"
        }

# ==========================================
# APPLICATION FASTAPI
# ==========================================

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
    
    try:
        # Initialisation du détecteur FlowMe
        flowme_detector = FlowMeStateDetector(
            nocodb_url=NOCODB_URL,
            nocodb_api_key=NOCODB_API_KEY,
            mistral_api_key=MISTRAL_API_KEY,
            states_table_id=NOCODB_STATES_TABLE_ID,
            reactions_table_id=NOCODB_REACTIONS_TABLE_ID
        )
        
        await flowme_detector.initialize()
        
        logger.info("✅ Module flowme_states_detection intégré avec succès")
        logger.info("🚀 Démarrage de FlowMe v3")
        logger.info(f"✅ Mistral API: {'✓ Configuré' if MISTRAL_API_KEY else '❌ Manquante'}")
        logger.info(f"✅ NocoDB: {'✓ Configuré' if NOCODB_API_KEY else '⚠️ Mode dégradé'}")
        logger.info(f"🔧 States Table ID: {NOCODB_STATES_TABLE_ID or 'MANQUANT'}")
        logger.info(f"🔧 Reactions Table ID: {NOCODB_REACTIONS_TABLE_ID or 'MANQUANT'}")
        logger.info(f"📊 États disponibles: {len(flowme_detector.flowme_states)}")
        
    except Exception as e:
        logger.error(f"❌ Erreur d'initialisation: {e}")
        # Continue même en cas d'erreur pour permettre les tests
        if not flowme_detector:
            flowme_detector = FlowMeStateDetector("", "", MISTRAL_API_KEY or "", "", "")
            await flowme_detector.initialize()

@app.get("/")
async def serve_homepage():
    """Page d'accueil FlowMe v3"""
    html_content = """
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>FlowMe v3 - Accompagnement Émotionnel</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { 
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 20px;
            }
            .container { 
                max-width: 800px; 
                margin: 0 auto; 
                background: rgba(255, 255, 255, 0.95);
                border-radius: 20px;
                padding: 30px;
                box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            }
            h1 { 
                text-align: center; 
                color: #4a5568; 
                margin-bottom: 30px;
                font-size: 2.5em;
                font-weight: 300;
            }
            .subtitle {
                text-align: center;
                color: #666;
                margin-bottom: 40px;
                font-size: 1.1em;
            }
            .message-input { 
                width: 100%; 
                padding: 15px; 
                margin: 20px 0; 
                border-radius: 15px; 
                border: 2px solid #e2e8f0;
                font-size: 16px;
                resize: vertical;
                min-height: 80px;
                transition: border-color 0.3s;
            }
            .message-input:focus {
                outline: none;
                border-color: #667eea;
            }
            .send-button { 
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white; 
                padding: 15px 30px; 
                border: none; 
                border-radius: 15px; 
                cursor: pointer;
                font-size: 16px;
                font-weight: 600;
                transition: transform 0.2s;
                width: 100%;
            }
            .send-button:hover {
                transform: translateY(-2px);
            }
            .response { 
                background: white; 
                padding: 20px; 
                margin: 20px 0; 
                border-radius: 15px; 
                border-left: 5px solid #667eea;
                box-shadow: 0 4px 12px rgba(0,0,0,0.1);
            }
            .user-message {
                background: #f7fafc;
                border-left-color: #48bb78;
            }
            .flowme-message {
                background: #edf2f7;
                border-left-color: #667eea;
            }
            .state-info { 
                color: #666; 
                font-size: 0.9em; 
                margin-top: 10px;
                font-style: italic;
            }
            .loading {
                display: none;
                text-align: center;
                color: #667eea;
                margin: 20px 0;
            }
            .spinner {
                border: 3px solid #f3f3f3;
                border-top: 3px solid #667eea;
                border-radius: 50%;
                width: 30px;
                height: 30px;
                animation: spin 1s linear infinite;
                margin: 0 auto 10px;
            }
            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>FlowMe v3</h1>
            <p class="subtitle">Ton compagnon d'écoute empathique, alimenté par l'IA</p>
            
            <div id="chat-container">
                <textarea id="message-input" class="message-input" 
                         placeholder="Exprime-toi librement... Je suis là pour t'écouter 💙" 
                         rows="3"></textarea>
                <button onclick="sendMessage()" class="send-button">Partager mes ressentis</button>
                
                <div class="loading" id="loading">
                    <div class="spinner"></div>
                    FlowMe analyse tes émotions...
                </div>
                
                <div id="responses"></div>
            </div>
        </div>
        
        <script>
            async function sendMessage() {
                const input = document.getElementById('message-input');
                const message = input.value.trim();
                if (!message) return;
                
                const responsesDiv = document.getElementById('responses');
                const loading = document.getElementById('loading');
                
                // Affiche le message utilisateur
                const userDiv = document.createElement('div');
                userDiv.className = 'response user-message';
                userDiv.innerHTML = `<p><strong>Toi :</strong> ${message}</p>`;
                responsesDiv.appendChild(userDiv);
                
                // Affiche le loader
                loading.style.display = 'block';
                input.value = '';
                
                try {
                    const response = await fetch('/chat', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({message: message})
                    });
                    
                    const data = await response.json();
                    
                    const flowmeDiv = document.createElement('div');
                    flowmeDiv.className = 'response flowme-message';
                    flowmeDiv.innerHTML = `
                        <p><strong>FlowMe :</strong> ${data.response}</p>
                        <div class="state-info">État perçu : ${data.state_detected} (${Math.round(data.confidence * 100)}% de confiance)</div>
                    `;
                    
                    responsesDiv.appendChild(flowmeDiv);
                    
                    // Scroll vers le bas
                    flowmeDiv.scrollIntoView({ behavior: 'smooth' });
                    
                } catch (error) {
                    console.error('Erreur:', error);
                    const errorDiv = document.createElement('div');
                    errorDiv.className = 'response';
                    errorDiv.innerHTML = '<p><strong>Erreur :</strong> Impossible de communiquer avec FlowMe. Réessaie dans un moment.</p>';
                    responsesDiv.appendChild(errorDiv);
                } finally {
                    loading.style.display = 'none';
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
        
        response = ChatResponse(
            response=empathic_response,
            state_detected=detected_state.get("Nom_État", "Présence"),
            confidence=0.8,
            timestamp=datetime.utcnow().isoformat()
        )
        
        logger.info(f"💬 État détecté: {response.state_detected}")
        return response
        
    except Exception as e:
        logger.error(f"Erreur dans /chat: {e}")
        raise HTTPException(status_code=500, detail="Erreur de traitement")

@app.get("/health")
async def health_check():
    """Vérification de santé"""
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
    """Liste des états FlowMe"""
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

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print("🚀 FlowMe v3 prêt à démarrer")
    print(f"   Port: {port}")
    print("   Start Command: uvicorn main:app --host 0.0.0.0 --port $PORT")
