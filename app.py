"""
Wrapper Flask compatible avec uvicorn et gunicorn
Point d'entrée universel pour Render
"""

from main import app

# Pour compatibilité avec uvicorn (commande existante Render)
# uvicorn cherche une variable 'app' au niveau module
# On l'exporte depuis main.py

if __name__ == "__main__":
    # Mode développement ou lancement direct
    import os
    port = int(os.getenv("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=False)
