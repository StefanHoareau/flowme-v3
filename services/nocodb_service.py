"""
Service NocoDB pour FlowMe v3
Gestion de la persistance des conversations et réactions
"""

import os
import asyncio
import aiohttp
import json
from datetime import datetime
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)

class NocoDBService:
    def __init__(self):
        self.base_url = os.getenv('NOCODB_URL', 'https://app.nocodb.com')
        self.api_key = os.getenv('NOCODB_API_KEY')
        self.reactions_table_id = os.getenv('NOCODB_REACTIONS_TABLE_ID')
        
        if not all([self.api_key, self.reactions_table_id]):
            logger.warning("Configuration NocoDB incomplète - mode dégradé activé")
    
    async def save_reaction(
        self,
        session_id: str,
        user_message: str,
        detected_state: Dict[str, Any],
        ai_response: str,
        user_feedback: Optional[str] = None
    ) -> bool:
        """
        Sauvegarde une interaction utilisateur dans NocoDB
        """
        if not self._is_configured():
            logger.info("NocoDB non configuré - interaction non sauvegardée")
            return False
        
        try:
            # Construction de l'enregistrement
            record = {
                "session_id": session_id,
                "timestamp": datetime.utcnow().isoformat(),
                "user_message": user_message[:1000],  # Limite de taille
                "detected_state_id": detected_state.get('state_id'),
                "detected_state_name": detected_state.get('state_name'),
                "state_confidence": detected_state.get('confidence', 0.0),
                "ai_response": ai_response[:2000],
                "user_feedback": user_feedback,
                "metadata": json.dumps({
                    "state_advice": detected_state.get('advice', ''),
                    "state_scores": detected_state.get('scores', {}),
                    "response_source": detected_state.get('source', 'mistral')
                })
            }
            
            # Appel API NocoDB
            url = f"{self.base_url}/api/v1/db/data/v1/{self.reactions_table_id}"
            headers = {
                "xc-token": self.api_key,
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=record, headers=headers) as response:
                    if response.status in [200, 201]:
                        result = await response.json()
                        logger.info(f"Interaction sauvegardée: {result.get('Id', 'N/A')}")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(f"Erreur NocoDB {response.status}: {error_text}")
                        return False
                        
        except Exception as e:
            logger.error(f"Erreur sauvegarde NocoDB: {e}")
            return False
    
    async def get_conversation_history(
        self, 
        session_id: str, 
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Récupère l'historique de conversation pour une session
        """
        if not self._is_configured():
            return []
        
        try:
            # Construction de la requête avec filtres
            url = f"{self.base_url}/api/v1/db/data/v1/{self.reactions_table_id}"
            params = {
                "where": f"(session_id,eq,{session_id})",
                "sort": "-timestamp",
                "limit": limit
            }
            
            headers = {
                "xc-token": self.api_key,
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get('list', [])
                    else:
                        logger.error(f"Erreur récupération historique: {response.status}")
                        return []
                        
        except Exception as e:
            logger.error(f"Erreur historique NocoDB: {e}")
            return []
    
    async def update_feedback(self, record_id: str, feedback: str) -> bool:
        """
        Met à jour le feedback utilisateur pour un enregistrement
        """
        if not self._is_configured():
            return False
        
        try:
            url = f"{self.base_url}/api/v1/db/data/v1/{self.reactions_table_id}/{record_id}"
            headers = {
                "xc-token": self.api_key,
                "Content-Type": "application/json"
            }
            
            payload = {"user_feedback": feedback}
            
            async with aiohttp.ClientSession() as session:
                async with session.patch(url, json=payload, headers=headers) as response:
                    return response.status == 200
                    
        except Exception as e:
            logger.error(f"Erreur mise à jour feedback: {e}")
            return False
    
    async def get_analytics(self, days: int = 7) -> Dict[str, Any]:
        """
        Récupère des analytics sur les états détectés
        """
        if not self._is_configured():
            return {}
        
        try:
            # Requête pour les stats des derniers jours
            from_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
            
            url = f"{self.base_url}/api/v1/db/data/v1/{self.reactions_table_id}"
            params = {
                "where": f"(timestamp,gte,{from_date})",
                "groupby": "detected_state_name",
                "aggregate": "count"
            }
            
            headers = {
                "xc-token": self.api_key,
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            "period_days": days,
                            "total_interactions": len(data.get('list', [])),
                            "state_distribution": data.get('list', []),
                            "generated_at": datetime.utcnow().isoformat()
                        }
                    else:
                        return {}
                        
        except Exception as e:
            logger.error(f"Erreur analytics NocoDB: {e}")
            return {}
    
    def _is_configured(self) -> bool:
        """
        Vérifie si NocoDB est correctement configuré
        """
        return bool(self.api_key and self.reactions_table_id)
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Vérifie la santé de la connexion NocoDB
        """
        if not self._is_configured():
            return {
                "status": "error",
                "message": "Configuration NocoDB manquante",
                "configured": False
            }
        
        try:
            # Test simple de connexion
            url = f"{self.base_url}/api/v1/db/data/v1/{self.reactions_table_id}"
            headers = {"xc-token": self.api_key}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params={"limit": 1}, headers=headers) as response:
                    if response.status == 200:
                        return {
                            "status": "healthy",
                            "message": "Connexion NocoDB OK",
                            "configured": True,
                            "table_accessible": True
                        }
                    else:
                        return {
                            "status": "error",
                            "message": f"Erreur connexion: {response.status}",
                            "configured": True,
                            "table_accessible": False
                        }
                        
        except Exception as e:
            return {
                "status": "error", 
                "message": f"Erreur health check: {str(e)}",
                "configured": True,
                "table_accessible": False
            }

# Instance globale
nocodb_service = NocoDBService()
