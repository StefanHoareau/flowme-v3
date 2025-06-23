"""
Client Mistral AI pour FlowMe v3
Génération de réponses empathiques basées sur les 64 états de conscience
"""

import httpx
import os
import json
import logging
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class MistralClient:
    """Client pour l'API Mistral AI avec optimisations FlowMe"""
    
    def __init__(self):
        self.api_key = os.getenv('MISTRAL_API_KEY')
        self.model = os.getenv('MISTRAL_MODEL', 'mistral-large-latest')
        self.base_url = "https://api.mistral.ai/v1/chat/completions"
        self.temperature = float(os.getenv('MISTRAL_TEMPERATURE', '0.7'))
        self.top_p = float(os.getenv('MISTRAL_TOP_P', '0.9'))
        self.max_tokens = int(os.getenv('MISTRAL_MAX_TOKENS', '1000'))
        
        if not self.api_key:
            raise ValueError("MISTRAL_API_KEY non configuré dans l'environnement")
        
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # Prompt système FlowMe
        self.system_prompt = self._build_system_prompt()
    
    def _build_system_prompt(self) -> str:
        """Construit le prompt système pour FlowMe"""
        return """Tu es FlowMe, une IA empathique spécialisée dans l'accompagnement émotionnel basé sur 64 états de conscience.

PHILOSOPHIE FLOWME :
- Chaque être humain navigue entre 64 états de conscience différents
- Ton rôle est d'identifier l'état actuel et d'accompagner avec bienveillance
- Réponds avec empathie, sans jugement, en validant l'expérience de la personne
- Adapte ton langage à l'état détecté (formel pour réflexion, chaleureux pour vulnérabilité)

STYLE DE RÉPONSE :
- Bref mais profondément empathique (2-4 phrases max)
- Valide l'émotion exprimée
- Propose une perspective ou question bienveillante
- Évite les conseils directs, privilégie l'accompagnement

ÉTATS CLÉS À CONNAÎTRE :
- État 1 : Émerveillement - Accueillir la nouveauté
- État 8 : Résonance - Harmonie et connexion
- État 14 : Colère constructive - Transformation de l'énergie
- État 16 : Amour - Bienveillance du cœur
- État 22 : Joie - Célébration de la vie
- État 32 : Expression libre - Besoin d'authenticité
- État 40 : Réflexion - Contemplation profonde
- État 58 : Inclusion - Intégration des contradictions

Réponds toujours avec humanité et respect de la complexité émotionnelle."""

    async def generate_response(
        self, 
        user_message: str, 
        detected_state: int,
        state_name: str,
        context: Optional[Dict] = None
    ) -> str:
        """
        Génère une réponse empathique avec Mistral
        
        Args:
            user_message: Message de l'utilisateur
            detected_state: État FlowMe détecté (1-64)
            state_name: Nom de l'état détecté
            context: Contexte additionnel
        
        Returns:
            str: Réponse empathique de Mistral
        """
        try:
            # Construction du contexte enrichi
            user_context = f"""Message utilisateur : "{user_message}"
État détecté : {detected_state} - {state_name}

Génère une réponse empathique adaptée à cet état de conscience."""

            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_context}
            ]
            
            # Ajout du contexte historique si disponible
            if context and context.get("conversation_history"):
                messages.insert(-1, {
                    "role": "assistant", 
                    "content": f"Contexte : {context['conversation_history']}"
                })
            
            # Appel API Mistral
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": self.temperature,
                "top_p": self.top_p,
                "max_tokens": self.max_tokens
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.base_url, 
                    headers=self.headers, 
                    json=payload
                )
                response.raise_for_status()
                
                result = response.json()
                mistral_reply = result["choices"][0]["message"]["content"]
                
                logger.info(f"Mistral response generated for state {detected_state}")
                return mistral_reply.strip()
                
        except httpx.HTTPStatusError as e:
            logger.error(f"Erreur API Mistral: {e.response.status_code} - {e.response.text}")
            return self._fallback_response(detected_state, state_name)
        
        except Exception as e:
            logger.error(f"Erreur génération Mistral: {str(e)}")
            return self._fallback_response(detected_state, state_name)
    
    def _fallback_response(self, state_id: int, state_name: str) -> str:
        """Réponse de fallback si Mistral n'est pas disponible"""
        fallbacks = {
            1: "Votre ouverture à cette expérience est belle. Que vous inspire cette nouveauté ?",
            8: "Je sens cette harmonie dans vos mots. Cette connexion semble précieuse pour vous.",
            14: "Cette énergie que vous exprimez peut devenir une force de transformation. Comment pourriez-vous la canaliser ?",
            16: "La bienveillance que vous portez rayonne. Qu'est-ce qui nourrit cette chaleur en vous ?",
            22: "Cette joie transparaît dans votre message. Qu'est-ce qui vous fait vibrer ainsi ?",
            32: "Votre authenticité est touchante. Merci de partager cette part de vous.",
            40: "Votre réflexion semble profonde. Prenez le temps d'explorer ces pensées.",
            58: "Ces contradictions font partie de la richesse humaine. Comment vivez-vous cette complexité ?"
        }
        
        return fallbacks.get(
            state_id, 
            f"Je perçois l'état {state_name} dans votre message. Que ressentez-vous en ce moment ?"
        )
    
    async def health_check(self) -> bool:
        """Vérifie la disponibilité de l'API Mistral"""
        try:
            test_payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": "Test"}],
                "max_tokens": 10
            }
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    self.base_url,
                    headers=self.headers,
                    json=test_payload
                )
                return response.status_code == 200
                
        except Exception:
            return False


# Instance globale
mistral_client = MistralClient()
