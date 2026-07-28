import logging
from datetime import datetime, timezone
from extensions import db

logger = logging.getLogger(__name__)

def _sanitizar_doc_id(doc_id):
    """Garante que o ID enviado ao Firestore seja sempre uma string válida."""
    if isinstance(doc_id, dict):
        # Se um dicionário (ex: payload/key) for passado por engano, extrai o JID/ID
        return str(
            doc_id.get('remoteJid') or 
            doc_id.get('id') or 
            doc_id.get('user_id') or 
            'usuario_desconhecido'
        )
    return str(doc_id) if doc_id else 'usuario_desconhecido'

def salvar_mensagem(user_id, role, content):
    """Salva uma mensagem no histórico da conversa no Firestore."""
    try:
        user_id_clean = _sanitizar_doc_id(user_id)
        doc_ref = db.collection('chats').document(user_id_clean)
        
        doc = doc_ref.get()
        historico = []
        if doc.exists:
            data = doc.to_dict()
            historico = data.get('messages', [])

        historico.append({
            'role': str(role),
            'content': str(content),
            'timestamp': datetime.now(timezone.utc).isoformat()
        })

        # Mantém apenas as últimas 20 mensagens no histórico
        historico = historico[-20:]

        doc_ref.set({
            'messages': historico,
            'updated_at': datetime.now(timezone.utc)
        }, merge=True)
    except Exception as e:
        logger.error(f"Erro ao salvar mensagem no Firestore: {e}", exc_info=True)

def obter_historico(user_id):
    """Recupera o histórico recente de mensagens de um utilizador."""
    try:
        user_id_clean = _sanitizar_doc_id(user_id)
        doc_ref = db.collection('chats').document(user_id_clean)
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict().get('messages', [])
        return []
    except Exception as e:
        logger.error(f"Erro ao obter histórico do Firestore: {e}", exc_info=True)
        return []

def obter_estado_usuario(user_id):
    """Recupera metadados e estado do utilizador (ex: modo humano, instância)."""
    try:
        user_id_clean = _sanitizar_doc_id(user_id)
        doc_ref = db.collection('chats').document(user_id_clean)
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict()
        return {}
    except Exception as e:
        logger.error(f"Erro ao obter estado do utilizador: {e}", exc_info=True)
        return {}

def atualizar_estado_usuario(user_id, novos_dados):
    """Atualiza metadados ou preferências do utilizador no Firestore."""
    try:
        user_id_clean = _sanitizar_doc_id(user_id)
        doc_ref = db.collection('chats').document(user_id_clean)
        
        if isinstance(novos_dados, dict):
            novos_dados['updated_at'] = datetime.now(timezone.utc)
            doc_ref.set(novos_dados, merge=True)
    except Exception as e:
        logger.error(f"Erro ao atualizar estado do utilizador: {e}", exc_info=True)
