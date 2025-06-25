# FlowMe v3 - Module de détection d'états avec intégration NocoDB
import httpx
import json
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import asyncio
import logging

# Configuration des logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FlowMeStateDetector:
    def __init__(self, nocodb_url: str, nocodb_api_key: str, mistral_api_key: str):
        self.nocodb_url = nocodb_url
        self.nocodb_api_key = nocodb_api_key
        self.mistral_api_key = mistral_api_key
        self.flowme_states = {}
        self.mistral_client = httpx.AsyncClient()
        
    async def initialize(self):
        """Charge les états FlowMe depuis NocoDB"""
        try:
            # Remplace par ton ID de table réel
            states_table_id = "m8lwhj640ohzg7m"  # Table des états FlowMe
            
            headers = {"xc-token": self.nocodb_api_key}
            response = await self.mistral_client.get(
                f"{self.nocodb_url}/api/v1/db/data/noco/{states_table_id}", 
                headers=headers
            )
            
            if response.status_code == 200:
                states_data = response.json()
                self.flowme_states = {
                    state["ID_État"]: state for state in states_data.get("list", [])
                }
                logger.info(f"✅ {len(self.flowme_states)} états FlowMe chargés depuis NocoDB")
            else:
                logger.warning("❌ Échec du chargement des états, utilisation des états par défaut")
                self._load_default_states()
                
        except Exception as e:
            logger.error(f"Erreur lors du chargement des états: {e}")
            self._load_default_states()
    
    def _load_default_states(self):
        """États par défaut en cas d'échec de chargement NocoDB"""
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
            
            # 3. Sauvegarde dans NocoDB
            await self._save_to_nocodb(message, detected_state, confidence, empathic_response)
            
            return detected_state, empathic_response
            
        except Exception as e:
            logger.error(f"Erreur lors de l'analyse: {e}")
            return self._get_default_state(), "Je suis là pour t'écouter. Peux-tu me dire ce que tu ressens en ce moment ?"
    
    async def _detect_state(self, message: str) -> Tuple[Dict, float]:
        """Détecte l'état émotionnel via l'analyse Mistral"""
        
        # Prompt pour la détection d'état
        detection_prompt = f"""
        Analyse ce message et identifie l'état émotionnel principal parmi ces catégories FlowMe :
        
        - Présence (perception, écoute subtile)
        - Éveil (conscience, émergence)
        - Curiosité (exploration, découverte)
        - Joie (épanouissement, énergie positive)
        - Tristesse (mélancolie, introspection)
        - Colère (frustration, révolte)
        - Peur (anxiété, inquiétude)
        - Amour (connexion, bienveillance)
        - Solitude (isolement, retrait)
        - Confusion (désorientation, questionnement)
        
        Message à analyser : "{message}"
        
        Réponds uniquement avec ce format JSON :
        {{"etat": "nom_etat", "confiance": 0.85, "raison": "explication courte"}}
        """
        
        try:
            headers = {
                "Authorization": f"Bearer {self.mistral_api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": "mistral-small-latest",
                "messages": [{"role": "user", "content": detection_prompt}],
                "max_tokens": 150,
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
                
                # Parse le JSON de réponse
                try:
                    parsed = json.loads(content)
                    state_name = parsed.get("etat", "Présence")
                    confidence = float(parsed.get("confiance", 0.5))
                    
                    # Trouve l'état correspondant
                    detected_state = self._find_state_by_name(state_name)
                    return detected_state, confidence
                    
                except json.JSONDecodeError:
                    logger.warning("Réponse Mistral non-JSON, utilisation état par défaut")
                    
        except Exception as e:
            logger.error(f"Erreur détection Mistral: {e}")
            
        return self._get_default_state(), 0.5
    
    async def _generate_empathic_response(self, message: str, state: Dict, confidence: float) -> str:
        """Génère une réponse empathique basée sur l'état détecté"""
        
        state_name = state.get("Nom_État", "Présence")
        conseil = state.get("Conseil_Flowme", "")
        
        empathy_prompt = f"""
        Tu es FlowMe, une IA empathique spécialisée dans l'accompagnement émotionnel.
        
        L'utilisateur a écrit : "{message}"
        
        État émotionnel détecté : {state_name} (confiance: {confidence:.0%})
        Conseil FlowMe associé : {conseil}
        
        Génère une réponse empathique qui :
        1. Reconnaît et valide l'émotion
        2. Offre un soutien adapté
        3. Intègre subtilement le conseil FlowMe
        4. Reste naturelle et bienveillante
        
        Limite : 150 mots maximum.
        """
        
        try:
            headers = {
                "Authorization": f"Bearer {self.mistral_api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": "mistral-small-latest",
                "messages": [{"role": "user", "content": empathy_prompt}],
                "max_tokens": 200,
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
            
        # Réponse par défaut
        return f"Je perçois que tu traverses un moment de {state_name.lower()}. {conseil}"
    
    async def _save_to_nocodb(self, message: str, state: Dict, confidence: float, response: str):
        """Sauvegarde l'interaction dans NocoDB"""
        try:
            # Remplace par ton ID de table des réactions
            reactions_table_id = "reactions_table_id"  # À mettre à jour
            
            headers = {"xc-token": self.nocodb_api_key}
            data = {
                "etat_id_flowme": state.get("ID_État"),
                "tension_dominante": state.get("Tension_Dominante"),
                "famille_symbolique": state.get("Famille_Symbolique"),
                "timestamp": datetime.utcnow().isoformat(),
                "etat_nom": state.get("Nom_État"),
                "posture_adaptative": state.get("Posture_Adaptative"),
                "session_id": f"session_{datetime.now().strftime('%Y%m%d_%H%M')}",
                "pattern_detecte": message[:100],  # Tronqué pour la base
                "score_bien_etre": confidence,
                "recommandations": response,
                "evolution_tendance": "stable"
            }
            
            response = await self.mistral_client.post(
                f"{self.nocodb_url}/api/v1/db/data/noco/{reactions_table_id}",
                headers=headers,
                json=data
            )
            
            if response.status_code == 200:
                logger.info("✅ Interaction sauvegardée dans NocoDB")
            else:
                logger.warning(f"❌ Échec sauvegarde NocoDB: {response.status_code}")
                
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

# Fonction d'initialisation pour main.py
async def create_flowme_detector(nocodb_url: str, nocodb_api_key: str, mistral_api_key: str):
    """Crée et initialise le détecteur FlowMe"""
    detector = FlowMeStateDetector(nocodb_url, nocodb_api_key, mistral_api_key)
    await detector.initialize()
    return detector

# Fonction suggérée pour main.py
async def suggest_transition(message: str, detector: FlowMeStateDetector) -> Tuple[str, float]:
    """Fonction de transition suggérée (compatibilité avec l'ancien code)"""
    detected_state, response = await detector.analyze_emotional_state(message)
    state_name = detected_state.get("Nom_État", "Présence")
    
    # Retourne le format attendu par ton interface
    return f"{state_name}", 0.8  # Confiance par défaut
