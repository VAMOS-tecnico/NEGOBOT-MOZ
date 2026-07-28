import logging
from services.firebase_handler import get_db

logger = logging.getLogger(__name__)

def get_chat_history(phone_number):
    """Obtém o histórico de chat de um cliente."""
    try:
        db = get_db()
        doc_ref = db.collection('chats').document(phone_number)
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict().get('history', [])
    except Exception as e:
        logger.error(f"❌ Erro ao obter histórico: {e}")
    return []

def save_chat_history(phone_number, history):
    """Guarda o histórico de chat de um cliente."""
    try:
        db = get_db()
        doc_ref = db.collection('chats').document(phone_number)
        doc_ref.set({"history": history}, merge=True)
        logger.debug(f"✅ Histórico guardado para {phone_number}")
    except Exception as e:
        logger.error(f"❌ Erro ao salvar histórico: {e}")
