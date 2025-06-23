"""
Service Mistral AI pour FlowMe v3
Génère des réponses empathiques basées sur les 64 états de conscience
"""

import os
import asyncio
import aiohttp
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class MistralService:
    def __init__(self):
        self.api_key = os.getenv('MISTRAL_API_KEY')
        self.base_url = "https://api.mistral.ai/v1/chat/completions"
        self.model = "mistral-small-latest"  # Modèle optimal pour l'empathie
        
        if not self.api_key:
            logger.warning("MISTRAL_API_KEY non configurée - mode dégradé activé")
    
    async def generate_empathic_response(
        self, 
        user_message: str, 
        detected_state: Dict[str, Any],
        conversation_context: list = None
    ) -> str:
        """
        Génère une réponse empathique basée sur l'état détecté
        """
        if not self.api_key:
            return self._get_fallback_response(detected_state)
        
        try:
            # Construction du prompt empathique Stefan Hoareau
            system_prompt = self._build_system_prompt(detected_state)
            messages = self._build_messages(system_prompt, user_message, conversation_context)
            
            # Appel API Mistral
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
                
                payload = {
                    "model": self.model,
                    "messages": messages,
                    "temperature": 0.7,  # Créativité empathique
                    "max_tokens": 300,   # Réponses concises
                    "top_p": 0.9
                }
                
                async with session.post(self.base_url, json=payload, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data['choices'][0]['message']['content'].strip()
                    else:
                        logger.error(f"Erreur API Mistral: {response.status}")
                        return self._get_fallback_response(detected_state)
                        
        except Exception as e:
            logger.error(f"Erreur service Mistral: {e}")
            return self._get_fallback_response(detected_state)
    
    def _build_system_prompt(self, detected_state: Dict[str, Any]) -> str:
        """
        Construit le prompt système basé sur l'état détecté
        """
        state_id = detected_state.get('state_id', 1)
        state_name = detected_state.get('state_name', 'Émerveillement')
        advice = detected_state.get('advice', '')
        
        return f"""Tu es un coach empathique spécialisé dans les 64 états de conscience selon Stefan Hoareau.

L'utilisateur exprime actuellement l'État {state_id}: {state_name}.

Conseils contextuels: {advice}

DIRECTIVES IMPORTANTES:
- Réponds avec empathie et bienveillance
- Évite tout jugement ou critique
- Utilise un ton chaleureux et compréhensif
- Propose des perspectives constructives
- Reste dans l'état émotionnel détecté
- Maximum 2-3 phrases courtes
- Utilise "tu" pour créer la proximité

Objectif: Accompagner l'utilisateur avec sagesse et compassion selon l'approche Stefan Hoareau."""

    def _build_messages(self, system_prompt: str, user_message: str, context: list = None) -> list:
        """
        Construit la liste des messages pour l'API
        """
        messages = [{"role": "system", "content": system_prompt}]
        
        # Ajouter le contexte de conversation si disponible
        if context:
            messages.extend(context[-4:])  # Garder seulement les 4 derniers échanges
        
        messages.append({"role": "user", "content": user_message})
        return messages
    
    def _get_fallback_response(self, detected_state: Dict[str, Any]) -> str:
        """
        Réponses de secours si Mistral n'est pas disponible
        """
        state_id = detected_state.get('state_id', 1)
        
        fallbacks = {
            1: "Je sens une belle ouverture dans tes mots. Cette curiosité est précieuse, cultive-la !",
            8: "Ton message résonne avec beaucoup de douceur. Cette harmonie intérieure est un cadeau.",
            16: "L'amour que tu exprimes illumine l'instant. Laisse cette énergie te guider.",
            22: "Ta compassion touche profondément. C'est cette bienveillance qui change le monde.",
            32: "Je perçois une intensité forte. Peut-être qu'une pause t'aiderait à retrouver ton centre ?",
            40: "Cette réflexion montre ta profondeur. Prends le temps d'honorer cette contemplation.",
            58: "Tu intègres des aspects complexes avec sagesse. Cette nuance est une force."
        }
        
        return fallbacks.get(state_id, "Je t'entends et je respecte ce que tu traverses. Tu n'es pas seul(e).")

# Instance globale
mistral_service = MistralService()
