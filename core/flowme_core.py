"""
FlowMe Core v3 - Logique métier intégrée
Orchestration : Détection d'état + Mistral + NocoDB
"""

import logging
import uuid
from typing import Dict, Optional, Tuple
from datetime import datetime, timezone

from flowme_states_detection import (
    detect_flowme_state_improved,
    get_state_description,
    get_state_advice,
    get_state_color,
    get_state_icon,
    analyze_message_context
)
from core.mistral_client import mistral_client
from services.nocodb_client import nocodb_client

logger = logging.getLogger(__name__)

class FlowMeCore:
    """
    Orchestrateur principal FlowMe v3
    Intègre détection d'état, génération Mistral et persistance NocoDB
    """
    
    def __init__(self):
        self.session_store = {}  # Cache temporaire des sessions
        self.states_cache = {}   # Cache des définitions d'états
        self._init_cache()
    
    async def _init_cache(self):
        """Initialise le cache des états depuis NocoDB"""
        try:
            self.states_cache = await nocodb_client.get_all_states_briefs()
            if self.states_cache:
                logger.info(f"Cache initialisé avec {len(self.states_cache)} états")
            else:
                logger.warning("Impossible de charger les états depuis NocoDB")
        except Exception as e:
            logger.error(f"Erreur initialisation cache: {str(e)}")
    
    async def generate_response(
        self, 
        user_message: str,
        session_id: Optional[str] = None,
        context: Optional[Dict] = None
    ) -> Dict:
        """
        Génère une réponse FlowMe complète
        
        Args:
            user_message: Message de l'utilisateur
            session_id: ID de session (généré si absent)
            context: Contexte additionnel
        
        Returns:
            Dict: Réponse complète avec métadonnées
        """
        # Génération session si nécessaire
        if not session_id:
            session_id = str(uuid.uuid4())
        
        try:
            # 1. Détection de l'état FlowMe
            detected_state = detect_flowme_state_improved(user_message, context)
            state_name = get_state_description(detected_state)
            
            logger.info(f"État détecté: {detected_state} - {state_name}")
            
            # 2. Analyse contextuelle
            message_context = analyze_message_context(user_message)
            
            # 3. Récupération historique session
            session_history = await nocodb_client.get_session_history(session_id, limit=3)
            conversation_context = self._build_conversation_context(session_history)
            
            # 4. Génération réponse Mistral
            enhanced_context = {
                **(context or {}),
                "conversation_history": conversation_context,
                "message_analysis": message_context,
                "session_id": session_id
            }
            
            mistral_response = await mistral_client.generate_response(
                user_message=user_message,
                detected_state=detected_state,
                state_name=state_name,
                context=enhanced_context
            )
            
            # 5. Métadonnées de l'état
            state_metadata = await self._get_state_metadata(detected_state)
            
            # 6. Construction de la réponse complète
            full_response = {
                "session_id": session_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "user_message": user_message,
                "detected_state": {
                    "id": detected_state,
                    "name": state_name,
                    "description": state_metadata.get("brief", state_name),
                    "advice": get_state_advice(detected_state),
                    "color": get_state_color(detected_state),
                    "icon": get_state_icon(detected_state)
                },
                "mistral_response": mistral_response,
                "context_analysis": message_context,
                "success": True
            }
            
            # 7. Sauvegarde asynchrone dans NocoDB
            await self._save_interaction_async(
                session_id=session_id,
                user_message=user_message,
                detected_state=detected_state,
                state_name=state_name,
                mistral_reply=mistral_response,
                context=enhanced_context
            )
            
            # 8. Mise à jour cache session
            self._update_session_cache(session_id, full_response)
            
            logger.info(f"Réponse générée avec succès - Session: {session_id}")
            return full_response
            
        except Exception as e:
            logger.error(f"Erreur génération réponse FlowMe: {str(e)}")
            return self._error_response(session_id, str(e))
    
    async def _get_state_metadata(self, state_id: int) -> Dict:
        """Récupère les métadonnées d'un état"""
        # Vérifier le cache local
        if state_id in self.states_cache:
            return {"brief": self.states_cache[state_id]}
        
        # Récupérer depuis NocoDB
        try:
            brief = await nocodb_client.get_state_brief(state_id)
            if brief:
                self.states_cache[state_id] = brief
                return {"brief": brief}
        except Exception as e:
            logger.warning(f"Impossible de récupérer l'état {state_id}: {str(e)}")
        
        # Fallback local
        return {"brief": get_state_description(state_id)}
    
    def _build_conversation_context(self, history: list) -> str:
        """Construit le contexte conversationnel depuis l'historique"""
        if not history:
            return "Première interaction"
        
        context_parts = []
        for item in history[:3]:  # 3 dernières interactions
            user_msg = item.get("user_message", "")[:100]  # Limiter la taille
            state_name = item.get("state_name", "")
            context_parts.append(f"État précédent: {state_name} - \"{user_msg}\"")
        
        return " | ".join(reversed(context_parts))
    
    async def _save_interaction_async(
        self,
        session_id: str,
        user_message: str,
        detected_state: int,
        state_name: str,
        mistral_reply: str,
        context: Dict
    ):
        """Sauvegarde asynchrone non-bloquante"""
        try:
            success = await nocodb_client.save_reaction(
                session_id=session_id,
                user_message=user_message,
                detected_state=detected_state,
                state_name=state_name,
                mistral_reply=mistral_reply,
                context=context
            )
            
            if not success:
                logger.warning(f"Échec sauvegarde NocoDB - Session: {session_id}")
                
        except Exception as e:
            logger.error(f"Erreur sauvegarde asynchrone: {str(e)}")
    
    def _update_session_cache(self, session_id: str, response: Dict):
        """Met à jour le cache des sessions"""
        if session_id not in self.session_store:
            self.session_store[session_id] = []
        
        self.session_store[session_id].append({
            "timestamp": response["timestamp"],
            "state_id": response["detected_state"]["id"],
            "state_name": response["detected_state"]["name"]
        })
        
        # Limiter à 10 dernières interactions par session
        if len(self.session_store[session_id]) > 10:
            self.session_store[session_id] = self.session_store[session_id][-10:]
    
    def _error_response(self, session_id: str, error_message: str) -> Dict:
        """Génère une réponse d'erreur standardisée"""
        return {
            "session_id": session_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "success": False,
            "error": error_message,
            "fallback_response": "Je rencontre une difficulté technique. Pouvez-vous reformuler votre message ?",
            "detected_state": {
                "id": 40,
                "name": "Réflexion",
                "description": "Pause technique",
                "advice": "Prenons un moment pour reconnecter",
                "color": "#708090",
                "icon": "🤔"
            }
        }
    
    async def get_session_summary(self, session_id: str) -> Dict:
        """Récupère un résumé de session"""
        try:
            history = await nocodb_client.get_session_history(session_id, limit=20)
            
            if not history:
                return {"session_id": session_id, "message_count": 0}
            
            # Analyse des états dans la session
            states_frequency = {}
            for item in history:
                state_id = item.get("detected_state")
                if state_id:
                    states_frequency[state_id] = states_frequency.get(state_id, 0) + 1
            
            most_frequent_state = max(states_frequency.items(), key=lambda x: x[1])[0] if states_frequency else 1
            
            return {
                "session_id": session_id,
                "message_count": len(history),
                "most_frequent_state": most_frequent_state,
                "states_distribution": states_frequency,
                "first_interaction": history[-1].get("timestamp") if history else None,
                "last_interaction": history[0].get("timestamp") if history else None
            }
            
        except Exception as e:
            logger.error(f"Erreur résumé session {session_id}: {str(e)}")
            return {"session_id": session_id, "error": str(e)}
    
    async def health_check(self) -> Dict:
        """Vérifie la santé de tous les composants"""
        mistral_ok = await mistral_client.health_check()
        nocodb_ok = await nocodb_client.health_check()
        
        return {
            "mistral_api": mistral_ok,
            "nocodb": nocodb_ok,
            "states_cache": len(self.states_cache) > 0,
            "overall_status": mistral_ok and nocodb_ok,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


# Instance globale FlowMe
flowme_core = FlowMeCore()
