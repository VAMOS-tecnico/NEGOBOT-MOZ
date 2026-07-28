import extensions

def get_chat_history(phone_number):
    try:
        doc_ref = extensions.db.collection('chats').document(phone_number)
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict().get('history', [])
    except Exception as e:
        print(f"Erro ao obter histórico: {e}")
    return []

def save_chat_history(phone_number, history):
    try:
        doc_ref = extensions.db.collection('chats').document(phone_number)
        doc_ref.set({"history": history}, merge=True)
    except Exception as e:
        print(f"Erro ao salvar histórico: {e}")
