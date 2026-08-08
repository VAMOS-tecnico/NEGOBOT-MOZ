import os
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do ficheiro .env no início da aplicação
load_dotenv()

from flask import Flask
from config import Config
from extensions import init_extensions
from routes.webhook_routes import webhook_bp
from routes.web_routes import web_bp


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    init_extensions(app)

    app.register_blueprint(webhook_bp)
    app.register_blueprint(web_bp)

    return app


app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))import os
from flask import Flask
from config import Config
from extensions import init_extensions
from routes.webhook_routes import webhook_bp
from routes.web_routes import web_bp

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    init_extensions(app)

    app.register_blueprint(webhook_bp)
    app.register_blueprint(web_bp)

    return app

app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
