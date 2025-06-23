from typing import Optional, Dict
import re

def detect_flowme_state_improved(message: str, context: Optional[Dict] = None) -> int:
    """
    Détecte l'état de conscience FlowMe basé sur le message et le contexte.
    Version améliorée avec gestion des contradictions et hiérarchisation.
    
    Args:
        message (str): Message à analyser
        context (Optional[Dict]): Contexte additionnel (optionnel)
    
    Returns:
        int: Numéro de l'état détecté (1-64)
    """
    if not message or not isinstance(message, str):
        return 1  # État par défaut
    
    # Nettoyer et normaliser le message
    message_clean = message.lower().strip()
    words = re.findall(r'\b\w+\b', message_clean)
    
    if not words:
        return 1
    
    # Dictionnaire des mots-clés pour chaque état (version étendue)
    state_keywords = {
        # États de Violence/Conflit (priorité haute)
        32: ["despotisme", "carnage", "violence", "guerre", "haine", "destruction", "massacre", 
             "tyrannie", "oppression", "brutalité", "sauvagerie", "barbarie"],
        
        14: ["colère", "rage", "fureur", "révolte", "indignation", "combat", "lutte", 
             "résistance", "protestation"],
        
        # États d'Inclusion/Intégration (pour contradictions)
        58: ["paradoxe", "contradiction", "ensemble", "inclusion", "intégration", "unité",
             "synthèse", "réconciliation"],
        
        # États Positifs/Harmonieux
        8: ["résonance", "harmonie", "écoute", "subtil", "connexion", "accord", "paix"],
        
        1: ["émerveillement", "surprise", "découverte", "nouveauté", "étonnement"],
        
        16: ["amour", "affection", "tendresse", "compassion", "bienveillance", "cœur"],
        
        22: ["joie", "bonheur", "gaieté", "euphorie", "allégresse", "félicité"],
        
        # États Neutres/Réflectifs  
        40: ["réflexion", "pensée", "analyse", "méditation", "contemplation"],
        
        # Mots de liaison faibles (ne déclenchent pas automatiquement un état)
        "weak": ["bien", "bon", "très", "assez", "plutôt", "vraiment", "tout", "ça", "cela"]
    }
    
    # Scores pour chaque état
    state_scores = {}
    detected_words = {"strong": [], "weak": []}
    
    # Analyser chaque mot
    for word in words:
        word_found = False
        
        # Vérifier les mots forts (états spécifiques)
        for state_id, keywords in state_keywords.items():
            if isinstance(state_id, int) and word in keywords:
                if state_id not in state_scores:
                    state_scores[state_id] = 0
                state_scores[state_id] += 1
                detected_words["strong"].append((word, state_id))
                word_found = True
                break
        
        # Vérifier les mots faibles
        if not word_found and word in state_keywords.get("weak", []):
            detected_words["weak"].append(word)
    
    # Logique de décision améliorée
    if state_scores:
        # Détecter les contradictions (mots de violence + mots d'amour)
        has_violence = any(state_id in [32, 14] for state_id in state_scores.keys())
        has_love = any(state_id in [16, 8, 22] for state_id in state_scores.keys())
        
        if has_violence and has_love:
            # Contradiction détectée → État d'Inclusion
            return 58
        
        # Prioriser les états avec les scores les plus élevés
        max_score = max(state_scores.values())
        best_states = [state_id for state_id, score in state_scores.items() if score == max_score]
        
        # En cas d'égalité, prioriser les états de violence/conflit
        priority_order = [32, 14, 58, 16, 22, 8, 1, 40]
        for priority_state in priority_order:
            if priority_state in best_states:
                return priority_state
        
        # Retourner le premier état trouvé
        return best_states[0]
    
    # Aucun mot-clé fort trouvé
    if detected_words["weak"]:
        # Mots faibles seulement → État neutre de réflexion
        return 40
    
    # Aucun mot reconnu → État d'émerveillement par défaut
    return 1


def get_state_description(state_id: int) -> str:
    """
    Retourne la description d'un état FlowMe.
    
    Args:
        state_id (int): Numéro de l'état (1-64)
    
    Returns:
        str: Description de l'état
    """
    descriptions = {
        1: "Émerveillement - Ouverture à la nouveauté",
        8: "Résonance - Écoute subtile et harmonie", 
        14: "Colère Constructive - Transformation de l'énergie",
        16: "Amour - Connexion du cœur",
        22: "Joie - Célébration de la vie",
        32: "Expression Libre - Besoin d'exprimer des choses fortes",
        40: "Réflexion - Analyse et contemplation",
        58: "Inclusion - Intégration des contradictions"
    }
    
    return descriptions.get(state_id, f"État {state_id} - Description non disponible")


def get_state_advice(state_id: int) -> str:
    """
    Retourne des conseils personnalisés pour un état FlowMe donné.
    
    Args:
        state_id (int): Numéro de l'état (1-64)
    
    Returns:
        str: Conseils adaptés à l'état
    """
    advice = {
        1: "🌟 Cultivez cette ouverture ! Posez des questions, explorez de nouvelles perspectives.",
        8: "🎵 Restez à l'écoute de cette harmonie. Prenez le temps de savourer cette connexion subtile.",
        14: "⚡ Canalisez cette énergie constructivement. Votre colère peut devenir une force de changement positif.",
        16: "💝 Laissez cette bienveillance rayonner. Partagez cette chaleur avec votre entourage.",
        22: "✨ Célébrez cette joie ! Elle est contagieuse et peut illuminer la journée des autres.",
        32: "🎭 Exprimez-vous librement et authentiquement. Vos mots forts ont leur place.",
        40: "🤔 Prenez le temps de cette réflexion profonde. Vos insights peuvent être précieux.",
        58: "🌈 Embrassez cette complexité ! Les contradictions font partie de la richesse humaine."
    }
    
    return advice.get(state_id, f"🌊 État {state_id} - Restez présent à cette expérience unique.")


def get_state_color(state_id: int) -> str:
    """
    Retourne la couleur associée à un état FlowMe.
    
    Args:
        state_id (int): Numéro de l'état (1-64)
    
    Returns:
        str: Code couleur hexadécimal
    """
    colors = {
        1: "#FFD700",   # Or - Émerveillement
        8: "#87CEEB",   # Bleu ciel - Résonance
        14: "#FF6347",  # Rouge tomate - Colère constructive
        16: "#FF69B4",  # Rose - Amour
        22: "#FFA500",  # Orange - Joie
        32: "#9370DB",  # Violet - Expression libre
        40: "#708090",  # Gris ardoise - Réflexion
        58: "#20B2AA"   # Turquoise - Inclusion
    }
    
    return colors.get(state_id, "#4169E1")  # Bleu royal par défaut


def get_state_icon(state_id: int) -> str:
    """
    Retourne l'icône associée à un état FlowMe.
    
    Args:
        state_id (int): Numéro de l'état (1-64)
    
    Returns:
        str: Émoji représentant l'état
    """
    icons = {
        1: "🌟",   # Émerveillement
        8: "🎵",   # Résonance
        14: "⚡",  # Colère constructive
        16: "💝",  # Amour
        22: "✨",  # Joie
        32: "🎭",  # Expression libre
        40: "🤔",  # Réflexion
        58: "🌈"   # Inclusion
    }
    
    return icons.get(state_id, "🌊")  # Vague par défaut


def analyze_message_context(message: str) -> Dict:
    """
    Analyse le contexte émotionnel d'un message.
    
    Args:
        message (str): Message à analyser
    
    Returns:
        Dict: Analyse contextuelle
    """
    message_clean = message.lower()
    
    analysis = {
        "has_violence": any(word in message_clean for word in 
                          ["despotisme", "carnage", "violence", "guerre", "haine"]),
        "has_love": any(word in message_clean for word in 
                       ["amour", "compassion", "tendresse", "cœur"]),
        "has_contradiction": False,
        "dominant_emotion": "neutre",
        "intensity": "faible"
    }
    
    analysis["has_contradiction"] = analysis["has_violence"] and analysis["has_love"]
    
    # Déterminer l'émotion dominante
    if analysis["has_contradiction"]:
        analysis["dominant_emotion"] = "contradiction"
        analysis["intensity"] = "forte"
    elif analysis["has_violence"]:
        analysis["dominant_emotion"] = "violence"
        analysis["intensity"] = "forte"
    elif analysis["has_love"]:
        analysis["dominant_emotion"] = "amour"
        analysis["intensity"] = "moyenne"
    
    return analysis


# Fonction de compatibilité avec l'ancienne version
def detect_flowme_state(message: str) -> int:
    """
    Version simplifiée pour compatibilité.
    """
    return detect_flowme_state_improved(message)
