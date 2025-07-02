class EnhancedEmotionDetection:
    def __init__(self, states_data: Dict[str, Any]):
        self.states = states_data
        
        # Dictionnaire étendu avec scores pondérés
        self.emotion_keywords = {
            "Joie": {
                "primary": ["heureux", "content", "joyeux", "rayonnant", "épanoui"], # Score: 3
                "secondary": ["super", "génial", "parfait", "excellent", "formidable"], # Score: 2
                "context": ["sourire", "rire", "célébrer", "victoire", "succès"] # Score: 1
            },
            "Tristesse": {
                "primary": ["triste", "malheureux", "déprimé", "abattu", "mélancolique"],
                "secondary": ["sombre", "morose", "désespéré", "découragé"],
                "context": ["pleurer", "larmes", "chagrin", "peine", "deuil"]
            },
            "Colère": {
                "primary": ["énervé", "furieux", "irrité", "fâché", "exaspéré"],
                "secondary": ["agacé", "contrarié", "remonté", "ulcéré"],
                "context": ["rage", "violence", "injustice", "révolte", "frustration"]
            },
            "Peur": {
                "primary": ["peur", "anxieux", "stressé", "inquiet", "terrorisé"],
                "secondary": ["nerveux", "angoissé", "préoccupé", "troublé"],
                "context": ["panique", "phobique", "danger", "menace", "insécurité"]
            },
            "Amour": {
                "primary": ["amour", "aimer", "adorer", "chérir", "passion"],
                "secondary": ["affection", "tendresse", "attachement", "dévotion"],
                "context": ["cœur", "romantique", "câlin", "bisou", "famille"]
            },
            "Espoir": {
                "primary": ["espoir", "optimiste", "confiant", "positif", "encourageant"],
                "secondary": ["perspective", "avenir", "amélioration", "projet"],
                "context": ["rêver", "aspirer", "croire", "motivation", "ambition"]
            },
            "Présence": {
                "primary": ["présent", "ici", "maintenant", "conscience", "attentif"],
                "secondary": ["moment", "instant", "focus", "concentration"],
                "context": ["méditation", "pleine conscience", "être", "existence"]
            },
            "Nostalgie": {
                "primary": ["nostalgie", "passé", "souvenir", "autrefois", "jadis"],
                "secondary": ["regret", "mélancolie", "hier", "avant"],
                "context": ["enfance", "jeunesse", "époque", "temps", "mémoire"]
            },
            "Curiosité": {
                "primary": ["curieux", "intéressé", "découvrir", "explorer", "questionner"],
                "secondary": ["apprendre", "comprendre", "savoir", "étudier"],
                "context": ["pourquoi", "comment", "recherche", "investigation"]
            },
            "Sérénité": {
                "primary": ["serein", "calme", "paisible", "tranquille", "apaisé"],
                "secondary": ["zen", "relaxé", "détendu", "équilibré"],
                "context": ["paix", "harmonie", "quiétude", "repos", "silence"]
            }
        }
        
        # Modificateurs contextuels
        self.intensity_modifiers = {
            "très": 1.5, "vraiment": 1.3, "super": 1.4, "hyper": 1.6,
            "un peu": 0.7, "légèrement": 0.6, "plutôt": 0.8,
            "extrêmement": 2.0, "complètement": 1.8, "totalement": 1.8
        }
        
        # Négations
        self.negations = ["ne", "pas", "plus", "jamais", "aucun", "sans", "ni"]
    
    def detect_emotion(self, text: str) -> str:
        """Détection d'émotion avec scoring pondéré"""
        text_lower = text.lower()
        words = text_lower.split()
        
        emotion_scores = {}
        
        # Analyser chaque émotion
        for emotion, categories in self.emotion_keywords.items():
            score = 0
            
            # Mots primaires (score 3)
            for word in categories["primary"]:
                if word in text_lower:
                    score += 3 * self._get_context_multiplier(text_lower, word)
            
            # Mots secondaires (score 2)
            for word in categories["secondary"]:
                if word in text_lower:
                    score += 2 * self._get_context_multiplier(text_lower, word)
            
            # Mots contextuels (score 1)
            for word in categories["context"]:
                if word in text_lower:
                    score += 1 * self._get_context_multiplier(text_lower, word)
            
            if score > 0:
                emotion_scores[emotion] = score
        
        # Retourner l'émotion avec le score le plus élevé
        if emotion_scores:
            return max(emotion_scores, key=emotion_scores.get)
        
        return "Présence"  # Défaut
    
    def _get_context_multiplier(self, text: str, word: str) -> float:
        """Calcule le multiplicateur basé sur le contexte"""
        multiplier = 1.0
        
        # Chercher les modificateurs d'intensité
        for modifier, value in self.intensity_modifiers.items():
            if modifier in text and abs(text.index(modifier) - text.index(word)) < 20:
                multiplier *= value
        
        # Vérifier les négations
        for negation in self.negations:
            if negation in text and abs(text.index(negation) - text.index(word)) < 15:
                multiplier *= 0.3  # Réduire fortement le score
        
        return multiplier
    
    def get_emotion_confidence(self, text: str) -> Dict[str, float]:
        """Retourne les scores de confiance pour toutes les émotions"""
        text_lower = text.lower()
        emotion_scores = {}
        
        for emotion, categories in self.emotion_keywords.items():
            score = 0
            
            for word in categories["primary"]:
                if word in text_lower:
                    score += 3 * self._get_context_multiplier(text_lower, word)
            
            for word in categories["secondary"]:
                if word in text_lower:
                    score += 2 * self._get_context_multiplier(text_lower, word)
            
            for word in categories["context"]:
                if word in text_lower:
                    score += 1 * self._get_context_multiplier(text_lower, word)
            
            emotion_scores[emotion] = score
        
        # Normaliser les scores (0-1)
        max_score = max(emotion_scores.values()) if emotion_scores.values() else 1
        return {emotion: score/max_score for emotion, score in emotion_scores.items()}


# Exemple d'utilisation dans votre classe FlowMeStatesDetection
class FlowMeStatesDetection:
    def __init__(self, states_data: Dict[str, Any], source: str = "local"):
        self.states = states_data
        self.source = source
        self.enhanced_detector = EnhancedEmotionDetection(states_data)
        logger.info(f"✅ FlowMe initialisé - {len(states_data)} états - Source: {source}")
    
    def detect_emotion(self, text: str) -> str:
        return self.enhanced_detector.detect_emotion(text)
    
    def get_emotion_analysis(self, text: str) -> Dict[str, Any]:
        """Analyse complète avec scores de confiance"""
        detected = self.enhanced_detector.detect_emotion(text)
        confidence_scores = self.enhanced_detector.get_emotion_confidence(text)
        
        return {
            "primary_emotion": detected,
            "confidence_scores": confidence_scores,
            "confidence_level": confidence_scores.get(detected, 0),
            "alternative_emotions": sorted(
                [(emotion, score) for emotion, score in confidence_scores.items() 
                 if emotion != detected and score > 0.3],
                key=lambda x: x[1], reverse=True
            )[:3]
        }
