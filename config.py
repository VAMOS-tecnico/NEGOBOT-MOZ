import os

def configure_app(app):
    app.config["ENV"] = os.getenv("FLASK_ENV", "production")
    app.config["PORT"] = os.getenv("PORT", "5000")
    app.config["FIRESTORE_PROJECT"] = os.getenv("FIRESTORE_PROJECT")
    app.config["TIMEOUT_HUMANO_MINUTOS"] = int(os.getenv("TIMEOUT_HUMANO_MINUTOS", 2))
    app.config["GROQ_API_KEY"] = os.getenv("GROQ_API_KEY")
    app.config["GROQ_MODEL"] = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    app.config["GROQ_VISION_MODEL"] = os.getenv("GROQ_VISION_MODEL", "qwen-2.5-32b")
    app.config["EVOLUTION_API_URL"] = os.getenv("EVOLUTION_API_URL")
    app.config["EVOLUTION_API_KEY"] = os.getenv("EVOLUTION_API_KEY")
    app.config["EVOLUTION_INSTANCE_NAME"] = os.getenv("EVOLUTION_INSTANCE_NAME")
    app.config["WEBHOOK_URL"] = os.getenv("WEBHOOK_URL")
    app.config["ADMIN_NUMBER"] = os.getenv("ADMIN_NUMBER")
    app.config["ASSISTANT_NUMBER"] = os.getenv("ASSISTANT_NUMBER")
