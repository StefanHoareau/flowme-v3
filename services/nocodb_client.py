"""
Client NocoDB pour FlowMe v3
Persistance des conversations et métadonnées des états
"""

import httpx
import os
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime, timezone
import uuid

logger = logging.getLogger(__name__)

class NocoDBClient:
    """Client pour l'API NocoDB avec gestion FlowMe"""
    
    def __init__(self):
        self.base_url = os.getenv('NOCODB_URL', 'https://app.nocodb.com')
        self.api_key = os.getenv('NOCODB_API_KEY')
        self.workspace = os.getenv('NOCODB_WORKSPACE', 'flowme')
        self.reactions_table_id = os.getenv('NOCODB_REACTIONS_TABLE_ID')
        self.states_table = os.getenv('NOCODB_STATES_TABLE', 'États')
        
        if not self.api_key:
            raise ValueError("NOCODB_API_KEY non configuré dans l'environnement")
        
        self.headers = {
            "xc-token": self.api_key,
            "Content-Type": "application/json"
        }
        
        # URLs API construites
        self.api_base = f"{self.base_url}/api/v1/db/data/v1/{self.workspace}"
        self.reactions_url = f"{self.api_base}/Reactions_Mistral"
        self.states_url = f"{self.api_base}/{self.states_table}"
    
    async def save_reaction(
        self,
        session_id: str,
        user_message: str,
        detected_state: int,
        state_name: str,
        mistral_reply: str,
        context: Optional[Dict] = None
    ) -> bool:
        """
        Sauvegarde une interaction FlowMe dans NocoDB
        
        Args:
            session_id: Identifiant de session
            user_message: Message utilisateur
            detected_state: État détecté (1-64)
            state_name: Nom de l'état
            mistral_reply: Réponse de Mistral
            context: Contexte additionnel
        
        Returns:
            bool: Succès de la sauvegarde
        """
        try:
            payload = {
                "session_id": session_id,
                "user_message": user_message,
                "detected_state": detected_state,
                "state_name": state_name,
                "mistral_reply": mistral_reply,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "context": json.dumps(context) if context else None,
                "message_length": len(user_message),
                "reply_length": len(mistral_reply)
            }
            
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    self.reactions_url,
                    headers=self.headers,
                    json=payload
                )
                response.raise_for_status()
                
                logger.info(f"Réaction sauvegardée - Session: {session_id}, État: {detected_state}")
                return True
                
        except httpx.HTTPStatusError as e:
            logger.error(f"Erreur HTTP NocoDB: {e.response.status_code} - {e.response.text}")
            return False
        
        except Exception as e:
            logger.error(f"Erreur sauvegarde NocoDB: {str(e)}")
            return False
    
    async def get_state_brief(self, state_id: int) -> Optional[str]:
        """
        Récupère la définition concise d'un état depuis NocoDB
        
        Args:
            state_id: Numéro de l'état (1-64)
        
        Returns:
            Optional[str]: Description courte de l'état
        """
        try:
            url = f"{self.states_url}/{state_id}"
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, headers=self.headers)
                response.raise_for_status()
                
                data = response.json()
                brief = data.get("brief", f"État {state_id}")
                
                logger.debug(f"Brief récupéré pour état {state_id}: {brief}")
                return brief
                
        except httpx.HTTPStatusError as e:
            logger.warning(f"État {state_id} non trouvé dans NocoDB: {e.response.status_code}")
            return None
        
        except Exception as e:
            logger.error(f"Erreur récupération état {state_id}: {str(e)}")
            return None
    
    async def get_all_states_briefs(self) -> Dict[int, str]:
        """
        Récupère toutes les définitions d'états depuis NocoDB
        
        Returns:
            Dict[int, str]: Mapping état_id -> description
        """
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.get(
                    f"{self.states_url}?limit=64&sort=id",
                    headers=self.headers
                )
                response.raise_for_status()
                
                data = response.json()
                states = {}
                
                for item in data.get("list", []):
                    state_id = item.get("id")
                    brief = item.get("brief", f"État {state_id}")
                    if state_id:
                        states[int(state_id)] = brief
                
                logger.info(f"Récupéré {len(states)} définitions d'états depuis NocoDB")
                return states
                
        except Exception as e:
            logger.error(f"Erreur récupération des états: {str(e)}")
            return {}
    
    async def get_session_history(
        self, 
        session_id: str, 
        limit: int = 10
    ) -> List[Dict]:
        """
        Récupère l'historique d'une session
        
        Args:
            session_id: Identifiant de session
            limit: Nombre maximum de messages
        
        Returns:
            List[Dict]: Historique des interactions
        """
        try:
            params = {
                "where": f"session_id,eq,{session_id}",
                "sort": "-timestamp",
                "limit": limit
            }
            
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    self.reactions_url,
                    headers=self.headers,
                    params=params
                )
                response.raise_for_status()
                
                data = response.json()
                history = data.get("list", [])
                
                logger.debug(f"Récupéré {len(history)} messages pour session {session_id}")
                return history
                
        except Exception as e:
            logger.error(f"Erreur récupération historique {session_id}: {str(e)}")
            return []
    
    async def get_analytics_summary(self, days: int = 7) -> Dict:
        """
        Récupère un résumé analytique des interactions
        
        Args:
            days: Nombre de jours à analyser
        
        Returns:
            Dict: Statistiques d'usage
        """
        try:
            # Date limite
            cutoff_date = datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            cutoff_date = cutoff_date.replace(days=-days)
            
            params = {
                "where": f"timestamp,gte,{cutoff_date.isoformat()}",
                "limit": 1000
            }
            
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.get(
                    self.reactions_url,
                    headers=self.headers,
                    params=params
                )
                response.raise_for_status()
                
                data = response.json()
                interactions = data.get("list", [])
                
                # Analyse des données
                total_interactions = len(interactions)
                unique_sessions = len(set(item.get("session_id") for item in interactions))
                
                # États les plus fréquents
                state_counts = {}
                for item in interactions:
                    state = item.get("detected_state")
                    if state:
                        state_counts[state] = state_counts.get(state, 0) + 1
                
                top_states = sorted(
                    state_counts.items(), 
                    key=lambda x: x[1], 
                    reverse=True
                )[:5]
                
                summary = {
                    "period_days": days,
                    "total_interactions": total_interactions,
                    "unique_sessions": unique_sessions,
                    "top_states": top_states,
                    "avg_interactions_per_session": round(
                        total_interactions / max(unique_sessions, 1), 2
                    )
                }
                
                logger.info(f"Analytique généré: {total_interactions} interactions sur {days} jours")
                return summary
                
        except Exception as e:
            logger.error(f"Erreur génération analytique: {str(e)}")
            return {}
    
    async def health_check(self) -> bool:
        """Vérifie la connectivité NocoDB"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.states_url}?limit=1",
                    headers=self.headers
                )
                return response.status_code == 200
                
        except Exception:
            return False


# Instance globale
nocodb_client = NocoDBClient()
