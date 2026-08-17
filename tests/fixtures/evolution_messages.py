from copy import deepcopy

INSTANCE = "assistente_negobot"
REMOTE_JID = "258840000000@s.whatsapp.net"


def message_payload(text="Olá", message_id="msg-text-001", instance=INSTANCE, remote_jid=REMOTE_JID, from_me=False):
    return {
        "event": "MESSAGES_UPSERT",
        "instance": instance,
        "data": {
            "key": {
                "remoteJid": remote_jid,
                "fromMe": from_me,
                "id": message_id,
            },
            "pushName": "Utilizador de teste",
            "message": {"conversation": text},
            "messageType": "conversation",
            "messageTimestamp": 1709553296,
        },
    }


def group_message_payload():
    return message_payload(
        text="Olá grupo",
        message_id="msg-group-001",
        remote_jid="120363000000000000@g.us",
    )


def audio_message_payload(message_id="msg-audio-001"):
    payload = message_payload(text="", message_id=message_id)
    payload["data"]["message"] = {
        "audioMessage": {
            "mimetype": "audio/ogg; codecs=opus",
            "ptt": True,
        }
    }
    payload["data"]["messageType"] = "audioMessage"
    return payload


def unknown_event_payload():
    payload = message_payload(text="evento desconhecido", message_id="msg-unknown-001")
    payload["event"] = "PRESENCE_UPDATE"
    return payload


def clone(payload):
    return deepcopy(payload)
