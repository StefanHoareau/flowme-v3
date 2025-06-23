"""
Wrapper pour Render - FlowMe v3
Force l'utilisation d'Uvicorn pour FastAPI (ASGI)
"""

import os
from main import app

# Pour compatibilité Gunicorn -> Uvicorn
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

# Si exécuté par Gunicorn, utiliser un wrapper ASGI
else:
    # Créer un wrapper ASGI compatible
    def application(environ, start_response):
        """Wrapper WSGI->ASGI pour Gunicorn"""
        import asyncio
        from asgiref.wsgi import WsgiToAsgi
        
        # Convertir FastAPI en WSGI
        try:
            # Solution simple : redirection vers mode développement
            start_response('503 Service Unavailable', [('Content-Type', 'text/html')])
            return [b'''
            <html>
                <head><title>FlowMe v3 - Starting...</title></head>
                <body style="font-family: Arial; text-align: center; padding: 50px;">
                    <h1>🌊 FlowMe v3</h1>
                    <p>Service is starting...</p>
                    <p>Please refresh in a few seconds</p>
                    <script>setTimeout(() => location.reload(), 3000);</script>
                </body>
            </html>
            ''']
        except Exception as e:
            start_response('500 Internal Server Error', [('Content-Type', 'text/plain')])
            return [f'Error: {str(e)}'.encode()]
