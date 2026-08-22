import os
import secrets
from datetime import timedelta
from dotenv import load_dotenv

# Carrega as variáveis do ficheiro .env logo na inicialização
load_dotenv()

from flask import Flask
from config import Config
from extensions import init_extensions
from services.service_config import enforce_profile
from services.runtime_health import liveness_report, readiness_report
from routes.webhook_routes import webhook_bp
from routes.web_routes import web_bp
from routes.platform_routes import platform_bp
from routes.omnichannel_routes import omnichannel_bp


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.config["SECRET_KEY"] = os.getenv("PLATFORM_SECRET_KEY") or os.getenv("ADMIN_TOKEN") or secrets.token_hex(32)
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SECURE"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MAX_UPLOAD_BYTES", str(16 * 1024 * 1024)))
    app.config["SESSION_REFRESH_EACH_REQUEST"] = True
    app.permanent_session_lifetime = timedelta(hours=12)

    service_profile = os.getenv("NEGOBOT_SERVICE_PROFILE", "").strip()
    if service_profile:
        enforce_profile(service_profile)
    init_extensions(app)

    app.register_blueprint(webhook_bp)
    app.register_blueprint(web_bp)
    app.register_blueprint(platform_bp)
    app.register_blueprint(omnichannel_bp)

    @app.get("/healthz")
    def healthz():
        return liveness_report(), 200

    @app.get("/readyz")
    def readyz():
        report = readiness_report()
        return report, 200 if report["status"] == "ready" else 503

    return app


app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
