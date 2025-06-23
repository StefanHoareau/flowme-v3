"""
Wrapper pour Render - FlowMe v3
Render cherche app.py par défaut, on importe depuis main.py
"""

from main import app

# C'est tout ! Render va maintenant trouver app:app
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
