# FlowMe v3 - Documentation API

## 🌊 Endpoints Principaux

### `POST /chat`
**Conversation avec FlowMe**

**Request:**
```json
{
  "message": "Je me sens perdu...",
  "session_id": "sess_abc123",  // optionnel
  "context": {                  // optionnel
    "timestamp": "2025-06-23T15:30:00Z",
    "user_agent": "Mozilla/5.0..."
  }
}
```

**Response:**
```json
{
  "session_id": "sess_abc123",
  "timestamp": "2025-06-23T15:30:05Z",
  "user_message": "Je me sens perdu...",
  "detected_state": {
    "id": 7,
    "name": "Curiosité Écoute",
    "description": "État d'ouverture et d'exploration",
    "advice": "🤔 Prenez le temps de cette réflexion profonde",
    "color": "#708090",
    "icon": "🤔"
  },
  "mistral_response": "Je comprends ce sentiment de désorientation...",
  "context_analysis": {
    "has_violence": false,
    "has_love": false,
    "has_contradiction": false,
    "dominant_emotion": "confusion",
    "intensity": "moyenne"
  },
  "success": true
}
```

### `GET /states/{state_id}`
**Informations détaillées d'un état**

**Response:**
```json
{
  "id": 8,
  "name": "Résonance - Écoute subtile et harmonie",
  "brief": "Capacité d'écoute profonde et de connexion harmonieuse",
  "advice": "🎵 Restez à l'écoute de cette harmonie",
  "color": "#87CEEB",
  "icon": "🎵",
  "source": "nocodb"
}
```

### `GET /session/{session_id}/summary`
**Résumé d'une session**

**Response:**
```json
{
  "session_id": "sess_abc123",
  "message_count": 15,
  "most_frequent_state": 8,
  "states_distribution": {
    "8": 6,
    "16": 4,
    "22": 3,
    "40": 2
  },
  "first_interaction": "2025-06-23T15:00:00Z",
  "last_interaction": "2025-06-23T15:30:00Z"
}
```

### `GET /analytics`
**Analytiques d'usage**

**Parameters:**
- `days` (int): Période d'analyse (1-30 jours, défaut: 7)

**Response:**
```json
{
  "period_days": 7,
  "total_interactions": 1247,
  "unique_sessions": 156,
  "top_states": [
    [8, 234],   // État 8: 234 occurrences
    [16, 189],  // État 16: 189 occurrences
    [22, 145]   // État 22: 145 occurrences
  ],
  "avg_interactions_per_session": 8.0
}
```

### `GET /health`
**État de santé du système**

**Response:**
```json
{
  "mistral_api": true,
  "nocodb": true,
  "states_cache": true,
  "overall_status": true,
  "timestamp": "2025-06-23T15:30:00Z"
}
```

### `GET /version`
**Informations de version**

**Response:**
```json
{
  "version": "3.0.0",
  "name": "FlowMe",
  "architecture": "Stefan Hoareau - 64 États de Conscience",
  "components": {
    "detection": "flowme_states_detection.py",
    "llm": "Mistral AI",
    "database": "NocoDB",
    "framework": "FastAPI"
  },
  "features": [
    "Détection d'états de conscience",
    "Réponses empathiques IA",
    "Persistance conversations",
    "Analytiques d'usage"
  ]
}
```

## 🔒 Codes d'Erreur

- **400**: Requête invalide (message vide, paramètres incorrects)
- **404**: Ressource non trouvée (état inexistant, session introuvable)
- **500**: Erreur serveur interne
- **503**: Service indisponible (Mistral ou NocoDB hors ligne)

## 🎯 États de Conscience

### États Principaux Détectés

| ID | Nom | Description | Trigger |
|----|-----|-------------|---------|
| 1 | Émerveillement | Ouverture à la nouveauté | Surprise, découverte |
| 8 | Résonance | Écoute subtile | Harmonie, connexion |
| 14 | Colère Constructive | Transformation énergie | Indignation, révolte |
| 16 | Amour | Bienveillance du cœur | Affection, compassion |
| 22 | Joie | Célébration de la vie | Bonheur, allégresse |
| 32 | Expression Libre | Authenticité | Mots forts, vérité |
| 40 | Réflexion | Contemplation | Analyse, méditation |
| 58 | Inclusion | Intégration contradictions | Paradoxes, complexité |

## 🔧 Intégration

### Exemple JavaScript (Frontend)
```javascript
async function chatWithFlowMe(message, sessionId) {
  const response = await fetch('/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message: message,
      session_id: sessionId
    })
  });
  
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  
  return await response.json();
}
```

### Exemple Python (Client)
```python
import httpx

async def chat_with_flowme(message: str, session_id: str = None):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://your-app.onrender.com/chat",
            json={
                "message": message,
                "session_id": session_id
            }
        )
        response.raise_for_status()
        return response.json()
```

## 📊 Monitoring

### Health Check
```bash
curl https://your-app.onrender.com/health
```

### Analytics
```bash
curl "https://your-app.onrender.com/analytics?days=30"
```
