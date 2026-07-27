from flask import Flask
from config import configure_app
from routes import register_routes
from services import init_services
from utils import setup_logger

# Configura logger global
setup_logger()

def create_app():
    app = Flask(__name__)
    configure_app(app)
    register_routes(app)
    init_services()
    return app

# Instância exposta para gunicorn: `gunicorn app:app`
app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(app.config.get("PORT", 5000)))
