"""
Service NocoDB Optimisé pour FlowMe v3
Adapté aux structures de tables existantes
"""

import os
import asyncio
import aiohttp
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)

class NocoDBService:
    def __init__(self):
        self.base_url = os.getenv('NOCODB_URL', 'https://app.nocodb.com')
        self.api_key = os.getenv('NOCODB_API_KEY')
        self.reactions_table_id = os.getenv('NOCODB_REACTIONS_TABLE_ID')
        self.states_table_id = os.getenv('NOCODB_STATES_TABLE_ID')  # Table des 64 états
        
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
        Sauvegarde une interaction dans la table Reactions_Mistral
        Adapté à votre structure existante
        """
        if not self._is_configured():
            logger.info("NocoDB non configuré - interaction non sauvegardée")
            return False
        
        try:
            # Construction de l'enregistrement selon votre structure
            record = {
                "etat_id_flowme": str(detected_state.get('state_id', '')),
                "etat_nom": detected_state.get('state_name', ''),
                "tension_dominante": detected_state.get('tension', ''),
                "famille_symbolique": detected_state.get('famille', ''),
                "session_id": session_id,
                "timestamp": datetime.utcnow().isoformat(),
                "pattern_detecte": detected_state.get('pattern', 'Détection FlowMe v3'),
                "score_bien_etre": detected_state.get('well_being_score', 5.0),
                "posture_adaptative": detected_state.get('advice', ''),
                "recommandations": ai_response[:500] if ai_response else '',  # Limite taille
                "evolution_tendance": user_feedback or 'En cours d\'évaluation'
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
                        record_id = result.get('Id') or result.get('id', 'N/A')
                        logger.info(f"Interaction sauvegardée: {record_id}")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(f"Erreur NocoDB {response.status}: {error_text}")
                        return False
                        
        except Exception as e:
            logger.error(f"Erreur sauvegarde NocoDB: {e}")
            return False
    
    async def get_state_details(self, state_id: int) -> Dict[str, Any]:
        """
        Récupère les détails d'un état depuis la table flowmeAI Default View
        """
        if not self._is_configured() or not self.states_table_id:
            return {}
        
        try:
            url = f"{self.base_url}/api/v1/db/data/v1/{self.states_table_id}"
            params = {
                "where": f"(ID_État,eq,{state_id})",
                "limit": 1
            }
            
            headers = {
                "xc-token": self.api_key,
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        states = data.get('list', [])
                        if states:
                            state = states[0]
                            return {
                                'id': state.get('ID_État'),
                                'nom': state.get('Nom_État'),
                                'famille': state.get('Famille_Symbolique'),
                                'tension': state.get('Tension_Dominante'),
                                'mot_cle': state.get('Mot_Clé'),
                                'declencheurs': state.get('Déclencheurs'),
                                'posture': state.get('Posture_Adaptative'),
                                'compatibles': state.get('États_Compatibles'),
                                'sequentiels': state.get('États_Séquenciels'),
                                'conseil': state.get('Conseil_Flowme')
                            }
                    return {}
                    
        except Exception as e:
            logger.error(f"Erreur récupération état {state_id}: {e}")
            return {}
    
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
                        conversations = []
                        
                        for record in data.get('list', []):
                            conversations.append({
                                'timestamp': record.get('timestamp'),
                                'etat_nom': record.get('etat_nom'),
                                'etat_id': record.get('etat_id_flowme'),
                                'recommandations': record.get('recommandations'),
                                'score_bien_etre': record.get('score_bien_etre'),
                                'session_id': record.get('session_id')
                            })
                        
                        return conversations
                    else:
                        logger.error(f"Erreur récupération historique: {response.status}")
                        return []
                        
        except Exception as e:
            logger.error(f"Erreur historique NocoDB: {e}")
            return []
    
    async def get_analytics(self, days: int = 7) -> Dict[str, Any]:
        """
        Analytics basées sur vos données existantes
        """
        if not self._is_configured():
            return {}
        
        try:
            # Récupération des données récentes
            from_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
            
            url = f"{self.base_url}/api/v1/db/data/v1/{self.reactions_table_id}"
            params = {
                "where": f"(timestamp,gte,{from_date})",
                "limit": 1000  # Limite raisonnable
            }
            
            headers = {
                "xc-token": self.api_key,
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        records = data.get('list', [])
                        
                        # Calculs d'analytics
                        total_interactions = len(records)
                        
                        # États les plus fréquents
                        state_counts = {}
                        scores = []
                        sessions = set()
                        
                        for record in records:
                            # Compter les états
                            etat = record.get('etat_nom')
                            if etat and etat not in ['test_detection', 'test_nom', 'direct_test']:  # Exclure les tests
                                state_counts[etat] = state_counts.get(etat, 0) + 1
                            
                            # Collecter scores de bien-être
                            score = record.get('score_bien_etre')
                            if score is not None and isinstance(score, (int, float)):
                                scores.append(score)
                            
                            # Compter sessions uniques
                            session_id = record.get('session_id')
                            if session_id:
                                sessions.add(session_id)
                        
                        # Top 5 des états
                        top_states = sorted(state_counts.items(), key=lambda x: x[1], reverse=True)[:5]
                        
                        # Score moyen de bien-être
                        avg_score = sum(scores) / len(scores) if scores else 0
                        
                        return {
                            "period_days": days,
                            "total_interactions": total_interactions,
                            "unique_sessions": len(sessions),
                            "top_states": [{"state": state, "count": count} for state, count in top_states],
                            "average_wellbeing_score": round(avg_score, 2),
                            "wellbeing_scores_count": len(scores),
                            "generated_at": datetime.utcnow().isoformat()
                        }
                    else:
                        return {}
                        
        except Exception as e:
            logger.error(f"Erreur analytics NocoDB: {e}")
            return {}
    
    async def clean_test_data(self) -> bool:
        """
        Nettoie les données de test (optionnel)
        """
        if not self._is_configured():
            return False
        
        try:
            # Identification des données de test
            test_patterns = ['test_detection', 'test_nom', 'direct_test']
            
            url = f"{self.base_url}/api/v1/db/data/v1/{self.reactions_table_id}"
            headers = {
                "xc-token": self.api_key,
                "Content-Type": "application/json"
            }
            
            # Construction de la condition WHERE pour les tests
            where_conditions = []
            for pattern in test_patterns:
                where_conditions.append(f"(etat_nom,eq,{pattern})")
            
            where_clause = "(" + ",or,".join(where_conditions) + ")"
            
            params = {"where": where_clause}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        test_records = data.get('list', [])
                        
                        logger.info(f"Trouvé {len(test_records)} enregistrements de test à nettoyer")
                        
                        # Suppression des enregistrements de test
                        deleted_count = 0
                        for record in test_records:
                            record_id = record.get('Id') or record.get('id')
                            if record_id:
                                delete_url = f"{url}/{record_id}"
                                async with session.delete(delete_url, headers=headers) as del_response:
                                    if del_response.status == 200:
                                        deleted_count += 1
                        
                        logger.info(f"Supprimé {deleted_count} enregistrements de test")
                        return deleted_count > 0
                        
            return False
                        
        except Exception as e:
            logger.error(f"Erreur nettoyage test data: {e}")
            return False
    
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
            # Test de connexion sur la table des réactions
            url = f"{self.base_url}/api/v1/db/data/v1/{self.reactions_table_id}"
            headers = {"xc-token": self.api_key}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params={"limit": 1}, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        total_records = len(data.get('list', []))
                        
                        return {
                            "status": "healthy",
                            "message": "Connexion NocoDB OK",
                            "configured": True,
                            "reactions_table_accessible": True,
                            "total_interactions": total_records,
                            "states_table_configured": bool(self.states_table_id)
                        }
                    else:
                        return {
                            "status": "error",
                            "message": f"Erreur connexion: {response.status}",
                            "configured": True,
                            "reactions_table_accessible": False
                        }
                        
        except Exception as e:
            return {
                "status": "error", 
                "message": f"Erreur health check: {str(e)}",
                "configured": True,
                "reactions_table_accessible": False
            }

# Instance globale
nocodb_service = NocoDBService()
