# flowme_states_detection.py

def detect_flowme_state(user_input: str, states: list) -> dict:
    """
    Détection naïve de l’état Flowme à partir du texte utilisateur
    """
    user_text = user_input.lower()
    for state in states:
        if "Nom_État" in state and state["Nom_État"].lower() in user_text:
            return state
    # Fallback : retourne le premier état si aucun match
    return states[0] if states else {}
