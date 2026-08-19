# Registo automático de Webhook Telegram por tenant

## Objectivo

Quando um cliente introduzir o token criado no BotFather, o backend deve validar o bot, gerar um endereço webhook exclusivo do tenant, registar esse endereço através do método `setWebhook`, confirmar o resultado com `getWebhookInfo` e guardar apenas a configuração necessária para processar mensagens futuras.

O cliente **não deve copiar o URL do webhook**. O URL é montado pelo backend e enviado automaticamente ao Telegram. A API oficial aceita pedidos HTTPS para `https://api.telegram.org/bot<TOKEN>/<METHOD>` e devolve um objecto JSON com o campo booleano `ok`.[1]

## O que já existe na NEGOBOT-MOZ

A base omnichannel já possui o endpoint público:

```text
POST /api/omnichannel/telegram/{tenant_id}
```

O endpoint actual já valida o cabeçalho `X-Telegram-Bot-Api-Secret-Token`, normaliza o evento, calcula um `event_id`, verifica duplicados, grava `omnichannel_events` e coloca o evento em `omnichannel_incoming_queue`. O que falta para a ligação completa é o endpoint autenticado que recebe o token, chama `setWebhook`, verifica o resultado e grava a configuração do canal.

A arquitectura final deve ser:

```text
Cliente introduz token
        |
        v
POST /api/platform/client/channels/telegram/connect
        |
        +--> getMe(token)
        +--> gerar secret_token exclusivo
        +--> setWebhook(url, secret_token, allowed_updates)
        +--> getWebhookInfo(token)
        +--> guardar configuração cifrada no tenant
        |
        v
Telegram envia POST /api/omnichannel/telegram/{tenant_id}
        |
        +--> validar X-Telegram-Bot-Api-Secret-Token
        +--> deduplicar update_id
        +--> Redis omnichannel_incoming_queue
        +--> worker processa e responde por sendMessage
```

## 1. Serviço Telegram

Criar `services/telegram_service.py`. O token nunca deve ser colocado no frontend, nos logs ou na URL pública do webhook.

```python
from __future__ import annotations

import os
from typing import Any

import requests


TELEGRAM_API_BASE = "https://api.telegram.org/bot{}"
TELEGRAM_TIMEOUT_SECONDS = 12


class TelegramApiError(RuntimeError):
    pass


def _api_url(token: str, method: str) -> str:
    return TELEGRAM_API_BASE.format(token) + f"/{method}"


def _call(token: str, method: str, payload: dict[str, Any] | None = None) -> Any:
    response = requests.post(
        _api_url(token, method),
        json=payload or {},
        timeout=TELEGRAM_TIMEOUT_SECONDS,
    )
    try:
        body = response.json()
    except ValueError as exc:
        raise TelegramApiError("Resposta inválida da API Telegram") from exc
    if not response.ok or not body.get("ok"):
        description = body.get("description") or f"HTTP {response.status_code}"
        raise TelegramApiError(f"Telegram {method}: {description}")
    return body.get("result")


def get_me(token: str) -> dict[str, Any]:
    result = _call(token, "getMe")
    if not isinstance(result, dict) or not result.get("id"):
        raise TelegramApiError("O token não corresponde a um bot Telegram válido")
    return result


def set_webhook(
    token: str,
    *,
    url: str,
    secret_token: str,
    allowed_updates: list[str] | None = None,
) -> dict[str, Any]:
    result = _call(
        token,
        "setWebhook",
        {
            "url": url,
            "secret_token": secret_token,
            "allowed_updates": allowed_updates or ["message", "edited_message", "callback_query"],
            "drop_pending_updates": False,
            "max_connections": 40,
        },
    )
    return {"ok": True, "result": result}


def get_webhook_info(token: str) -> dict[str, Any]:
    result = _call(token, "getWebhookInfo")
    return result if isinstance(result, dict) else {}


def send_message(token: str, *, chat_id: str | int, text: str, reply_to_message_id: int | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"chat_id": chat_id, "text": text[:4096]}
    if reply_to_message_id is not None:
        payload["reply_parameters"] = {"message_id": reply_to_message_id}
    result = _call(token, "sendMessage", payload)
    return result if isinstance(result, dict) else {}
```

O Telegram exige que `secret_token` tenha entre 1 e 256 caracteres e use apenas letras, números, `_` ou `-`. O Telegram envia esse valor no cabeçalho `X-Telegram-Bot-Api-Secret-Token` em cada pedido do webhook.[1]

## 2. Cifrar o token por tenant

Não guardar `bot_token` nem `webhook_secret` em texto simples no Firestore. O sistema aceita uma chave dedicada `TELEGRAM_TOKEN_ENCRYPTION_KEY`; se ela não existir, deriva automaticamente uma chave Fernet da chave de segurança existente `PLATFORM_SECRET_KEY` ou `ADMIN_TOKEN`. Em ambos os casos, a chave existe apenas no backend.

Adicionar a dependência:

```text
cryptography>=42,<47
```

Criar `services/secret_store.py`:

```python
from __future__ import annotations

import base64
import hashlib
import os
from cryptography.fernet import Fernet, InvalidToken


class SecretStoreError(RuntimeError):
    pass


def _fernet() -> Fernet:
    explicit_key = os.getenv("TELEGRAM_TOKEN_ENCRYPTION_KEY", "").strip()
    if explicit_key:
        key = explicit_key.encode()
    else:
        platform_key = (os.getenv("PLATFORM_SECRET_KEY") or os.getenv("ADMIN_TOKEN") or "").strip()
        if not platform_key:
            raise SecretStoreError("Nenhuma chave de segurança do Backend está configurada")
        digest = hashlib.sha256(f"negobot-telegram-secret-v1:{platform_key}".encode()).digest()
        key = base64.urlsafe_b64encode(digest)
    try:
        return Fernet(key)
    except Exception as exc:
        raise SecretStoreError("Chave de cifragem inválida") from exc


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt_secret(value: str) -> str:
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken as exc:
        raise SecretStoreError("Segredo cifrado inválido") from exc
```

Se quiseres separar a chave Telegram da chave geral, podes gerar uma chave dedicada e colocá-la como variável secreta do backend:

```python
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
```

O valor gerado deve ser guardado no Boomploy, não no repositório GitHub. Esta variável é opcional porque o fallback automático já utiliza a chave existente do Backend.

## 3. Endpoint autenticado de ligação

Adicionar ao `routes/platform_routes.py`. O endpoint deve exigir `owner` ou `operator`, obter o tenant da sessão e nunca aceitar `tenant_id` vindo do browser.

```python
from services.secret_store import encrypt_secret
from services.telegram_service import (
    TelegramApiError,
    get_me,
    get_webhook_info,
    set_webhook,
)


@platform_bp.post("/client/channels/telegram/connect")
@_require_tenant_roles("owner", "operator")
def connect_telegram():
    payload = request.get_json(silent=True) or {}
    token = str(payload.get("bot_token") or "").strip()
    if not token or len(token) > 256:
        return jsonify({"error": "Introduz um token Telegram válido."}), 400

    tenant_id = _tenant_for_identity(_identity())
    if not tenant_id:
        return jsonify({"error": "Tenant não encontrado na sessão."}), 403

    # Validar o token antes de guardar qualquer configuração.
    try:
        bot = get_me(token)
    except TelegramApiError:
        return jsonify({"error": "O token Telegram não é válido ou está inacessível."}), 400

    secret_token = secrets.token_hex(32)
    webhook_url = f"https://negobot-api.duckdns.org/api/omnichannel/telegram/{tenant_id}"

    try:
        set_webhook(
            token,
            url=webhook_url,
            secret_token=secret_token,
            allowed_updates=["message", "edited_message", "callback_query"],
        )
        webhook_info = get_webhook_info(token)
    except TelegramApiError as exc:
        _audit("telegram_webhook_setup_failed", _identity(), tenant_id, {"error": str(exc)[:240]})
        return jsonify({"error": "Não foi possível registar o webhook Telegram."}), 502

    if webhook_info.get("url") != webhook_url:
        _audit("telegram_webhook_verification_failed", _identity(), tenant_id, {})
        return jsonify({"error": "O Telegram não confirmou o URL do webhook."}), 502

    tenant_ref = _db().collection("tenants").document(tenant_id)
    tenant = tenant_ref.get().to_dict() or {}
    channels = dict(tenant.get("channels") or {})
    current = dict(channels.get("telegram") or {})
    current.update({
        "status": "connected",
        "setup": "bot_token",
        "provider": "Telegram Bot API",
        "bot_id": str(bot.get("id")),
        "bot_username": bot.get("username"),
        "bot_name": bot.get("first_name"),
        "token_ciphertext": encrypt_secret(token),
        "webhook_secret_ciphertext": encrypt_secret(secret_token),
        "webhook_url": webhook_url,
        "last_webhook_info": {
            "pending_update_count": webhook_info.get("pending_update_count", 0),
            "last_error_message": webhook_info.get("last_error_message"),
            "last_error_date": webhook_info.get("last_error_date"),
        },
        "connected_at": _now(),
        "updated_at": _now(),
    })
    channels["telegram"] = current
    tenant_ref.set({"channels": channels, "updated_at": _now()}, merge=True)
    _audit("telegram_webhook_connected", _identity(), tenant_id, {"bot_id": str(bot.get("id"))})

    return jsonify({
        "connected": True,
        "channel": "telegram",
        "bot": {"id": bot.get("id"), "username": bot.get("username"), "name": bot.get("first_name")},
        "webhook_url": webhook_url,
        "pending_update_count": webhook_info.get("pending_update_count", 0),
    }), 200
```

O `webhook_url` pode ser devolvido ao frontend apenas para informação. O cliente não precisa de o copiar ou configurar manualmente.

## 4. Endpoint para desligar ou substituir o bot

Quando o cliente troca de bot, remover primeiro o webhook antigo. O token antigo deve ser lido da configuração cifrada do mesmo tenant, nunca de outro tenant.

```python
from services.secret_store import decrypt_secret
from services.telegram_service import _call


@platform_bp.post("/client/channels/telegram/disconnect")
@_require_tenant_roles("owner", "operator")
def disconnect_telegram():
    tenant_id = _tenant_for_identity(_identity())
    tenant_ref = _db().collection("tenants").document(tenant_id)
    tenant = tenant_ref.get().to_dict() or {}
    channels = dict(tenant.get("channels") or {})
    telegram = dict(channels.get("telegram") or {})
    ciphertext = str(telegram.get("token_ciphertext") or "")
    if ciphertext:
        try:
            _call(decrypt_secret(ciphertext), "deleteWebhook", {"drop_pending_updates": False})
        except Exception:
            # Mesmo que o Telegram esteja temporariamente indisponível, apagar o segredo local.
            logger.exception("Falha ao remover webhook Telegram tenant=%s", tenant_id)
    channels["telegram"] = {
        "status": "disabled",
        "provider": "Telegram Bot API",
        "updated_at": _now(),
    }
    tenant_ref.set({"channels": channels, "updated_at": _now()}, merge=True)
    _audit("telegram_webhook_disconnected", _identity(), tenant_id, {})
    return jsonify({"disconnected": True, "channel": "telegram"})
```

## 5. Reforçar o webhook de entrada

O endpoint existente em `routes/omnichannel_routes.py` já valida o segredo e faz idempotência. Para Telegram, deve também rejeitar um update sem `update_id` ou sem mensagem suportada, e pode guardar o `update_id` explicitamente.

```python
if channel == "telegram":
    update_id = payload.get("update_id")
    if not isinstance(update_id, int):
        return jsonify({"error": "Update Telegram sem update_id"}), 400
    event_id = f"telegram:{tenant_id}:{update_id}"
else:
    event_id = hashlib.sha256(
        json.dumps(
            {"channel": channel, "tenant": tenant_id, "payload": payload},
            sort_keys=True,
            default=str,
        ).encode()
    ).hexdigest()
```

A deduplicação por `update_id` é mais clara para Telegram porque o próprio objecto `Update` fornece esse identificador crescente; a documentação recomenda usá-lo para ignorar actualizações repetidas.[1]

Para garantir que o evento pertence ao canal certo, antes de enfileirar deve confirmar que a configuração do tenant possui:

```python
telegram_config = (tenant.get("channels") or {}).get("telegram") or {}
if telegram_config.get("status") != "connected":
    return jsonify({"error": "Canal Telegram não está activo"}), 403
```

O cabeçalho deve ser validado com comparação constante:

```python
from services.secret_store import decrypt_secret

expected_ciphertext = str(telegram_config.get("webhook_secret_ciphertext") or "")
provided = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
try:
    expected = decrypt_secret(expected_ciphertext) if expected_ciphertext else ""
except Exception:
    expected = ""
if not expected or not provided or not hmac.compare_digest(provided, expected):
    return jsonify({"error": "Secret Telegram inválido"}), 401
```

O webhook deve responder `200` logo depois de gravar/enfileirar o evento. O processamento de IA e o envio de resposta pertencem ao worker, não ao pedido HTTP do Telegram.

## 6. Processamento no worker

O worker deve retirar o evento da `omnichannel_incoming_queue`, extrair o texto e o `chat_id` e encaminhar a mensagem para o fluxo comum do tenant.

```python
from services.secret_store import decrypt_secret
from services.telegram_service import send_message


def process_telegram_event(event: dict) -> None:
    tenant_id = str(event["tenant_id"])
    payload = event.get("payload") or {}
    message = payload.get("message") or payload.get("edited_message") or {}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    text = str(message.get("text") or "").strip()
    message_id = message.get("message_id")
    if chat_id is None or not text:
        return

    tenant = _load_tenant(tenant_id)
    telegram = ((tenant.get("channels") or {}).get("telegram") or {})
    token_ciphertext = str(telegram.get("token_ciphertext") or "")
    if not token_ciphertext:
        return
    token = decrypt_secret(token_ciphertext)

    reply_text = process_tenant_message(
        tenant_id=tenant_id,
        channel="telegram",
        conversation_id=str(chat_id),
        text=text,
    )
    if reply_text:
        send_message(
            token,
            chat_id=chat_id,
            text=reply_text,
            reply_to_message_id=message_id if isinstance(message_id, int) else None,
        )
```

`process_tenant_message` deve usar apenas documentos filtrados por `tenant_id`. O worker nunca deve aceitar um `tenant_id` vindo apenas do texto da mensagem ou de um campo não validado.

A documentação do Telegram também permite responder ao webhook directamente usando o método da API no corpo da resposta, mas para a arquitectura da NEGOBOT-MOZ é mais seguro manter o padrão produtor/worker Redis, responder rapidamente ao Telegram e deixar a IA fora do request.[1]

## 7. Endpoints de estado para a interface

Adicionar um endpoint `GET /api/platform/client/channels/telegram` que devolva somente dados não sensíveis:

```python
return jsonify({
    "channel": "telegram",
    "status": telegram.get("status", "not_configured"),
    "bot": {
        "id": telegram.get("bot_id"),
        "username": telegram.get("bot_username"),
        "name": telegram.get("bot_name"),
    },
    "webhook_url": telegram.get("webhook_url"),
    "last_event_at": telegram.get("last_event_at"),
    "last_error": telegram.get("last_error"),
    "pending_update_count": (telegram.get("last_webhook_info") or {}).get("pending_update_count", 0),
    "has_token": bool(telegram.get("token_ciphertext")),
})
```

Nunca devolver `token_ciphertext`, `webhook_secret` ou o token original ao React.

## 8. Testes obrigatórios

Os testes de backend devem cobrir, pelo menos, os casos seguintes.

```python
@patch("services.telegram_service.requests.post")
def test_connect_registers_webhook_for_current_tenant(mock_post):
    mock_post.side_effect = [
        fake_response({"ok": True, "result": {"id": 123, "username": "cliente_bot", "first_name": "Cliente"}}),
        fake_response({"ok": True, "result": True}),
        fake_response({"ok": True, "result": {"url": "https://negobot-api.duckdns.org/api/omnichannel/telegram/tenant-a", "pending_update_count": 0}}),
    ]
    set_identity(client, {"role": "client", "tenant_id": "tenant-a", "tenant_role": "owner"})
    response = client.post("/api/platform/client/channels/telegram/connect", json={"bot_token": "123:ABC"})
    assert response.status_code == 200
    assert db.collection("tenants").document("tenant-a").get().to_dict()["channels"]["telegram"]["status"] == "connected"


def test_telegram_webhook_rejects_wrong_secret():
    response = client.post(
        "/api/omnichannel/telegram/tenant-a",
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"},
        json={"update_id": 1, "message": {"chat": {"id": 9}, "text": "Olá"}},
    )
    assert response.status_code == 401


def test_telegram_webhook_is_idempotent():
    payload = {"update_id": 777, "message": {"message_id": 2, "chat": {"id": 9}, "text": "Olá"}}
    first = client.post(telegram_url, headers=valid_headers, json=payload)
    second = client.post(telegram_url, headers=valid_headers, json=payload)
    assert first.status_code == 200
    assert second.get_json()["duplicate"] is True


def test_telegram_webhook_cannot_cross_tenants():
    response = client.post(
        "/api/omnichannel/telegram/tenant-b",
        headers=headers_for_tenant_a,
        json={"update_id": 1, "message": {"chat": {"id": 9}, "text": "Olá"}},
    )
    assert response.status_code in {401, 403}
```

Também testar `getWebhookInfo` com URL divergente, token inválido, Telegram indisponível, reconfiguração do mesmo bot e `deleteWebhook` ao desligar.

## Resultado esperado

Depois destes passos, o cliente fará apenas três coisas: criar o bot no BotFather, copiar o token para o campo seguro e clicar em **Ligar Telegram**. O backend fará todo o resto: validar o bot, gerar o segredo, criar o URL tenant-scoped, chamar `setWebhook`, validar `getWebhookInfo`, guardar o token cifrado, receber eventos e enviar respostas pelo bot correcto.

A parte de recepção tenant-scoped e fila já existe na NEGOBOT-MOZ. A parte que ainda precisa de implementação é o serviço Telegram, os endpoints `connect/disconnect/status`, a cifragem dos tokens e o adaptador de saída do worker.

## Referências

[1]: https://core.telegram.org/bots/api "Telegram Bot API — documentação oficial"
