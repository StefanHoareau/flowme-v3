"""
FlowMe v3 - Détection des États de Conscience
Version enrichie basée sur les 96 états de votre base NocoDB
"""

import re
import logging
from typing import Dict, Any, List, Tuple
from textblob import TextBlob

logger = logging.getLogger(__name__)

# Mapping des 96 états basé sur votre analyse CSV
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
    16: {"name": "Admiration", "famille": "Contemplation", "tension": "Admirative"},
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
    31: {"name": "Discipline", "famille": "Discipline mentale", "tension": "Perceptive, mouvante"},
    32: {"name": "Carnage", "famille": "Observation pure", "tension": "Expansive, paisible"},
    58: {"name": "Inclusion", "famille": "Intégration", "tension": "Intégrative, vivante"}
}

# Patterns de détection enrichis basés sur les familles symboliques
DETECTION_PATTERNS = {
    # États d'ouverture et exploration
    1: ["présent", "ici maintenant", "attention", "écoute", "ressens"],
    2: ["réveil", "éveil", "conscience", "réalise", "prendre conscience"],
    3: ["curieux", "curiosité", "explore", "découvrir", "intéressant"],
    4: ["étonne", "surpris", "wow", "incroyable", "étonnant"],
    5: ["analyse", "comprend", "logique", "raisonne", "structure"],
    
    # États de résonance et harmonie
    6: ["synthèse", "tout ensemble", "unifie", "globalité", "ensemble"],
    7: ["intuition", "ressent", "pressent", "devine", "instinct"],
    8: ["résonance", "harmonie", "accord", "vibration", "connexion"],
    9: ["question", "pourquoi", "comment", "interroge", "me demande"],
    
    # États de protection et retenue
    10: ["prudent", "attention", "méfie", "careful", "precaution"],
    11: ["retenue", "modère", "calme", "posé", "mesuré"],
    12: ["accueille", "ouvre", "reçoit", "bienvenue", "accepte"],
    13: ["élan", "envie", "motiv", "pousse", "force"],
    
    # États de clarté et discernement
    14: ["lucide", "clair", "évident", "transparent", "voit bien"],
    15: ["distingue", "différence", "sépare", "choisit", "discrimine"],
    16: ["admire", "beau", "magnifique", "merveilleux", "sublime"],
    17: ["investigue", "cherche", "fouille", "explore", "examine"],
    18: ["équilibre", "balance", "stable", "harmonieux", "centré"],
    
    # États d'attente et transformation
    19: ["attend", "patience", "temporise", "moment", "timing"],
    20: ["ouvert", "réceptif", "disponible", "accessible", "perméable"],
    21: ["adapte", "change", "transforme", "flexible", "évolue"],
    22: ["compassion", "empathie", "compréhension", "bienveillance", "amour"],
    23: ["précis", "exact", "juste", "rigoureux", "minutieux"],
    
    # États de trouble et vigilance
    24: ["sidéré", "choqué", "paralysé", "figé", "abasourdi"],
    25: ["confus", "perdu", "mélange", "flou", "désorienté"],
    26: ["vigilant", "surveille", "garde", "protège", "veille"],
    27: ["persévère", "continue", "tient bon", "endure", "résiste"],
    28: ["empathie", "ressent pour", "compatit", "partage", "comprend"],
    
    # États élevés et détachement
    29: ["élève", "monte", "transcende", "dépasse", "sublime"],
    30: {"détache", "lâche prise", "distance", "recul", "objectif"},
    31: ["discipline", "contrôle", "maîtrise", "rigueur", "méthode"],
    
    # États extrêmes
    32: ["carnage", "destruction", "violence", "rage", "fureur", "tuer", "détruit"],
    58: ["inclut", "intègre", "contradiction", "paradoxe", "complexe", "nuance"]
}

# Patterns émotionnels pour le sentiment
EMOTIONAL_PATTERNS = {
    "positive": ["heureux", "joie", "content", "ravi", "épanoui", "bien", "
