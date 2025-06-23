"""
Wrapper Flask pour Render
Point d'entrée compatible avec la commande uvicorn
"""

from main import app

# Pour compatibility avec la commande Render existante
# uvicorn app:app sera équivalent à flask run
if __name__ == "__main__":
    import os
    port = int(os.getenv("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=False)
