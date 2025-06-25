"""
FlowMe v3 - Détection des États de Conscience
Version complète avec toutes les fonctions nécessaires
Basée sur les 96 états de Stefan Hoareau
"""

import re
import logging
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Mapping des états de conscience principaux
CONSCIOUSNESS_STATES = {
    1: {"name": "Présence", "famille": "Écoute subtile", "tension": "Latente, intérieure"},
    2: {"name": "Éveil", "famille": "Conscience primordiale", "tension": "Émergente"},
    3: {"name": "Curiosité", "famille": "Exploration", "tension": "Attractive"},
    4: {"name": "Étonnement", "famille": "Rupture cognitive", "tension": "Dissonante"},
    5: {"name": "Analyse", "famille": "Discernement", "tension": "Structurante"},
    6: {"name": "Synthèse", "famille": "Construction intégrative", "tension": "Unifiante"},
    7: {"name": "Intuition", "famille": "Perception holistique", "tension": "Fulgurante"},
    8: {"name": "Résonance", "famille": "Vibration harmonique", "tension": "Empathique"},
    9: {"name": "Questionnement", "famille": "Questionnement réflexif", "tension": "Suspensive"},
    10: {"name": "Prudence", "famille": "Protection primitive", "tension": "Préventive"},
    11: {"name": "Retenue", "famille": "Modération", "tension": "Restrictive"},
    12: {"name": "Accueil", "famille": "Réceptivité", "tension": "Accueillante"},
    13: {"name": "Élan", "famille": "Génération", "tension": "Expansive"},
    14: {"name": "Lucidité", "famille": "Lucidité", "tension": "Lumineuse"},
    15: {"name": "Discrimination", "famille": "Jugement affiné", "tension": "Discriminante"},
    16: {"name": "Amour", "famille": "Contemplation", "tension": "Admirative"},
    17: {"name": "Investigation", "famille": "Investigation", "tension": "Exploratoire"},
    18: {"name": "Équilibre", "famille": "Harmonisation", "tension": "Stabilisatrice"},
    19: {"name": "Attente", "famille": "Attente active", "tension": "Temporelle"},
    20: {"name": "Ouverture", "famille": "Ouverture", "tension": "Poreuse"},
    21: {"name": "Adaptation", "famille": "Transformation", "tension": "Plastique"},
    22: {"name": "Compassion", "famille": "Alignement interne", "tension": "Intégrative"},
    23: {"name": "Précision", "famille": "Exactitude", "tension": "Ciselante"},
    24: {"name": "Sidération", "famille": "Sidération", "tension": "Paralysante"},
    25: {"name": "Confusion", "famille": "Confusion constructive", "tension": "Déstabilisante"},
    26: {"name": "Vigilance", "famille": "Surveillance", "tension": "Protectrice"},
    27: {"name": "Persévérance", "famille": "Continuation", "tension": "Endurante"},
    28: {"name": "Empathie", "famille": "Résonance empathique", "tension": "Altruiste"},
    29: {"name": "Élévation", "famille": "Élévation", "tension": "Ascendante"},
    30: {"name": "Détachement", "famille": "Discernement mûri", "tension": "Détachée"},
    31: {"name": "Discipline", "famille": "Discipline mentale", "tension": "Perceptive"},
    32: {"name": "Carnage", "famille": "Observation pure", "tension": "Destructrice"},
    40: {"name": "Réflexion", "famille": "Analyse et contemplation", "tension": "Profonde"},
    58: {"name": "Inclusion", "famille": "Intégration", "tension": "Intégrative"}
}

# Patterns de détection par mots-clés
DETECTION_PATTERNS = {
    # États d'ouverture et exploration (1-10)
    1: ["présent", "ici maintenant", "attention", "écoute", "ressens", "conscient"],
    2: ["réveil", "éveil", "conscience", "réalise", "prendre conscience", "lucide"],
    3: ["curieux", "curiosité", "explore", "découvrir", "intéressant", "nouveau"],
    4: ["étonne", "surpris", "wow", "incroyable", "étonnant", "stupéfait"],
    5: ["analyse", "comprend", "logique", "raisonne", "structure", "examine"],
    6: ["synthèse", "tout ensemble", "unifie", "globalité", "ensemble", "cohérent"],
    7: ["intuition", "ressent", "pressent", "devine", "instinct", "sixième sens"],
    8: ["résonance", "harmonie", "accord", "vibration", "connexion", "unisson"],
    9: ["question", "pourquoi", "comment", "interroge", "me demande", "doute"],
    10: ["pru
