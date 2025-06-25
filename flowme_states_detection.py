# flowme_states_detection.py - Version corrigée avec suggest_transition

import re
import random
from typing import Dict, List, Tuple, Optional

# Configuration des 96 états de conscience Stefan Hoareau
FLOWME_STATES = {
    1: {
        "name": "Présence",
        "description": "État de conscience pure, d'attention au moment présent",
        "keywords": ["maintenant", "présent", "ici", "moment", "attention", "conscience"],
        "energy_level": "neutral",
        "category": "awareness"
    },
    16: {
        "name": "Amour",
        "description": "Capacité d'aimer sans condition, ouverture du cœur",
        "keywords": ["amour", "aimer", "cœur", "tendresse", "affection", "bienveillance"],
        "energy_level": "high",
        "category": "heart"
    },
    32: {
        "name": "Joie",
        "description": "Bonheur spontané, légèreté de l'être",
        "keywords": ["joie", "bonheur", "rire", "sourire", "plaisir", "gaieté"],
        "energy_level": "high",
        "category": "emotion"
    },
    48: {
        "name": "Paix",
        "description": "Tranquillité intérieure, sérénité profonde",
        "keywords": ["paix", "calme", "sérénité", "tranquillité", "repos", "silence"],
        "energy_level": "low",
        "category": "stillness"
    },
    64: {
        "name": "Unité",
        "description": "Sentiment d'union avec le tout, non-dualité",
        "keywords": ["unité", "tout", "ensemble", "connexion", "fusion", "totalité"],
        "energy_level": "transcendent",
        "category": "unity"
    },
    # États émotionnels négatifs
    8: {
        "name": "Tristesse",
        "description": "Mélancolie, peine intérieure",
        "keywords": ["triste", "tristesse", "peine", "chagrin", "mélancolie", "pleure"],
        "energy_level": "low",
        "category": "emotion"
    },
    24: {
        "name": "Colère",
        "description": "Irritation, frustration, rage",
        "keywords": ["colère", "rage", "frustration", "irrité", "énervé", "furieux"],
        "energy_level": "high",
        "category": "emotion"
    },
    40: {
        "name": "Peur",
        "description": "Anxiété, inquiétude, appréhension",
        "keywords": ["peur", "anxiété", "stress", "inquiet", "angoisse", "crainte"],
        "energy_level": "high",
        "category": "emotion"
    },
    # États mentaux
    4: {
        "name": "Confusion",
        "description": "Désorientation mentale, manque de clarté",
        "keywords": ["confus", "perdu", "désorienté", "flou", "incompréhensible"],
        "energy_level": "neutral",
        "category": "mental"
    },
    12: {
        "name": "Clarté",
        "description": "Compréhension claire, lucidité",
        "keywords": ["clair", "comprendre", "lucide", "évident", "précis"],
        "energy_level": "neutral",
        "category": "mental"
    }
}

def detect_primary_state(message: str, user_context: Dict = None) -> Dict:
    """
    Détecte l'état de conscience primaire basé sur le message de l'utilisateur
    """
    message_lower = message.lower()
    
    # Scores pour chaque état
    state_scores = {}
    
    for state_id, state_info in FLOWME_STATES.items():
        score = 0
        
        # Analyse des mots-clés
        for keyword in state_info["keywords"]:
            if keyword in message_lower:
                score += 2
                
        # Analyse du contexte émotionnel
        if state_info["category"] == "emotion":
            if any(word in message_lower for word in ["ressens", "émotion", "sentiment"]):
                score += 1
                
        # Analyse de l'énergie du message
        if state_info["energy_level"] == "high" and any(word in message_lower for word in ["!", "très", "beaucoup"]):
            score += 1
        elif state_info["energy_level"] == "low" and any(word in message_lower for word in ["peu", "doucement", "calme"]):
            score += 1
            
        if score > 0:
            state_scores[state_id] = score
    
    # Retourne l'état avec le score le plus élevé, ou l'état de Présence par défaut
    if state_scores:
        primary_state_id = max(state_scores, key=state_scores.get)
        confidence = min(state_scores[primary_state_id] * 0.2, 1.0)
    else:
        primary_state_id = 1  # État de Présence par défaut
        confidence = 0.3
    
    return {
        "state_id": primary_state_id,
        "state_name": FLOWME_STATES[primary_state_id]["name"],
        "description": FLOWME_STATES[primary_state_id]["description"],
        "confidence": confidence,
        "category": FLOWME_STATES[primary_state_id]["category"],
        "energy_level": FLOWME_STATES[primary_state_id]["energy_level"]
    }

def suggest_transition(current_state_id: int, target_emotion: str = None) -> Dict:
    """
    Suggère une transition d'état basée sur l'état actuel et l'émotion cible
    """
    current_state = FLOWME_STATES.get(current_state_id, FLOWME_STATES[1])
    
    # Transitions recommandées basées sur l'état actuel
    transitions = {
        8: [1, 16, 48],    # Tristesse -> Présence, Amour, Paix
        24: [48, 1, 16],   # Colère -> Paix, Présence, Amour
        40: [1, 48, 12],   # Peur -> Présence, Paix, Clarté
        4: [12, 1, 16],    # Confusion -> Clarté, Présence, Amour
        1: [16, 32, 48],   # Présence -> Amour, Joie, Paix
        16: [32, 64, 48],  # Amour -> Joie, Unité, Paix
        32: [16, 64, 48],  # Joie -> Amour, Unité, Paix
        48: [1, 16, 64],   # Paix -> Présence, Amour, Unité
        12: [16, 32, 1],   # Clarté -> Amour, Joie, Présence
        64: [16, 32, 48]   # Unité -> Amour, Joie, Paix
    }
    
    # Obtenir les transitions possibles
    possible_transitions = transitions.get(current_state_id, [1, 16, 48])
    
    # Sélectionner une transition appropriée
    if target_emotion:
        # Chercher un état correspondant à l'émotion cible
        target_state_id = None
        for state_id, state_info in FLOWME_STATES.items():
            if target_emotion.lower() in [kw.lower() for kw in state_info["keywords"]]:
                target_state_id = state_id
                break
        
        if target_state_id and target_state_id in possible_transitions:
            suggested_state_id = target_state_id
        else:
            suggested_state_id = possible_transitions[0]
    else:
        # Sélection intelligente basée sur l'état actuel
        if current_state["energy_level"] == "high" and current_state["category"] == "emotion":
            # Pour les émotions intenses, suggérer la paix ou la présence
            suggested_state_id = next((s for s in possible_transitions if FLOWME_STATES[s]["energy_level"] in ["low", "neutral"]), possible_transitions[0])
        else:
            # Progression naturelle vers des états plus élevés
            suggested_state_id = possible_transitions[0]
    
    suggested_state = FLOWME_STATES[suggested_state_id]
    
    return {
        "current_state": {
            "id": current_state_id,
            "name": current_state["name"],
            "description": current_state["description"]
        },
        "suggested_state": {
            "id": suggested_state_id,
            "name": suggested_state["name"],
            "description": suggested_state["description"]
        },
        "transition_method": _get_transition_method(current_state_id, suggested_state_id),
        "estimated_duration": _estimate_transition_duration(current_state_id, suggested_state_id)
    }

def _get_transition_method(from_state: int, to_state: int) -> str:
    """
    Retourne une méthode de transition recommandée
    """
    methods = {
        (8, 1): "Respiration consciente et observation des sensations présentes",
        (8, 16): "Pratique de l'auto-compassion et de la bienveillance envers soi",
        (8, 48): "Méditation de pleine conscience et acceptation de l'émotion",
        (24, 48): "Respiration profonde et relaxation musculaire progressive",
        (24, 1): "Ancrage dans le moment présent par les sens",
        (40, 1): "Techniques de grounding et de recentrage",
        (40, 12): "Questionnement bienveillant et rationalisation",
        (4, 12): "Pause réflexive et structuration de la pensée",
        (1, 16): "Ouverture du cœur par la gratitude",
        (16, 32): "Expression créative et partage de joie",
        (32, 64): "Méditation sur l'interconnexion de toutes choses"
    }
    
    return methods.get((from_state, to_state), "Méditation de pleine conscience et respiration consciente")

def _estimate_transition_duration(from_state: int, to_state: int) -> str:
    """
    Estime la durée nécessaire pour la transition
    """
    current_energy = FLOWME_STATES[from_state]["energy_level"]
    target_energy = FLOWME_STATES[to_state]["energy_level"]
    
    if current_energy == "high" and target_energy in ["low", "neutral"]:
        return "15-30 minutes"
    elif current_energy == "low" and target_energy == "high":
        return "30-45 minutes"
    elif current_energy == target_energy:
        return "10-20 minutes"
    else:
        return "20-30 minutes"

def analyze_emotional_pattern(message_history: List[str]) -> Dict:
    """
    Analyse les patterns émotionnels sur plusieurs messages
    """
    if not message_history:
        return {"pattern": "insufficient_data", "recommendation": "Continue à partager pour une meilleure analyse"}
    
    states_detected = []
    for message in message_history[-5:]:  # Analyser les 5 derniers messages
        state = detect_primary_state(message)
        states_detected.append(state)
    
    # Analyser la tendance
    energy_levels = [s["energy_level"] for s in states_detected]
    categories = [s["category"] for s in states_detected]
    
    pattern_analysis = {
        "recent_states": states_detected,
        "dominant_energy": max(set(energy_levels), key=energy_levels.count),
        "dominant_category": max(set(categories), key=categories.count),
        "stability": len(set([s["state_id"] for s in states_detected])) <= 2,
        "progression": _analyze_progression(states_detected)
    }
    
    return pattern_analysis

def _analyze_progression(states: List[Dict]) -> str:
    """
    Analyse la progression émotionnelle
    """
    if len(states) < 2:
        return "insufficient_data"
    
    state_ids = [s["state_id"] for s in states]
    
    # Vérifier si il y a amélioration (états vers plus positifs)
    positive_states = [16, 32, 48, 64, 12]  # Amour, Joie, Paix, Unité, Clarté
    negative_states = [8, 24, 40, 4]        # Tristesse, Colère, Peur, Confusion
    
    recent_positives = sum(1 for s in state_ids[-3:] if s in positive_states)
    recent_negatives = sum(1 for s in state_ids[-3:] if s in negative_states)
    
    if recent_positives > recent_negatives:
        return "positive_trend"
    elif recent_negatives > recent_positives:
        return "challenging_period"
    else:
        return "stable_mixed"

# Fonction utilitaire pour l'API
def get_all_states() -> Dict:
    """
    Retourne tous les états disponibles
    """
    return FLOWME_STATES

def get_state_by_id(state_id: int) -> Optional[Dict]:
    """
    Retourne un état spécifique par son ID
    """
    return FLOWME_STATES.get(state_id)

def search_states_by_keyword(keyword: str) -> List[Dict]:
    """
    Recherche des états par mot-clé
    """
    results = []
    keyword_lower = keyword.lower()
    
    for state_id, state_info in FLOWME_STATES.items():
        if (keyword_lower in state_info["name"].lower() or 
            keyword_lower in state_info["description"].lower() or
            any(keyword_lower in kw.lower() for kw in state_info["keywords"])):
            
            results.append({
                "id": state_id,
                "name": state_info["name"],
                "description": state_info["description"],
                "category": state_info["category"],
                "energy_level": state_info["energy_level"]
            })
    
    return results

# Configuration pour l'export
__all__ = [
    'detect_primary_state',
    'suggest_transition',
    'analyze_emotional_pattern',
    'get_all_states',
    'get_state_by_id',
    'search_states_by_keyword',
    'FLOWME_STATES'
]
