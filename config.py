import os

class Config:
    TIMEOUT_HUMANO_MINUTOS = int(os.getenv('TIMEOUT_HUMANO_MINUTOS', 2))
    GROQ_API_KEY = os.getenv('GROQ_API_KEY')
    GROQ_MODEL = os.getenv('GROQ_MODEL', 'llama-3.3-70b-versatile')
    GROQ_VISION_MODEL = os.getenv('GROQ_VISION_MODEL', 'qwen-2.5-32b')
    NUMERO_ASSISTANTE = os.getenv('ASSISTANT_NUMBER')
    ADMIN_NUMBER = os.getenv('ADMIN_NUMBER')
    EVOLUTION_API_KEY = os.getenv('EVOLUTION_API_KEY')
    EVOLUTION_API_URL = os.getenv('EVOLUTION_API_URL')
    EVOLUTION_INSTANCE_NAME = os.getenv('EVOLUTION_INSTANCE_NAME')
    WEBHOOK_URL = os.getenv('WEBHOOK_URL')
    FIREBASE_CONFIG = os.getenv('FIREBASE_CONFIG')
