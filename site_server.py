import os
from pathlib import Path

import requests
from flask import Flask, Response, jsonify, redirect, request, send_from_directory

SITE_ROOT = Path(__file__).resolve().parent
app = Flask(__name__, static_folder=None)


@app.get("/")
def home():
    return _react_index()


REACT_DIST = SITE_ROOT / "platform-react" / "dist"


def _react_index():
    return send_from_directory(REACT_DIST, "index.html")


def _react_asset(asset: str):
    if "." not in Path(asset).name:
        return _react_index()
    return send_from_directory(REACT_DIST, asset)


# A rota principal usa React; a versão antiga fica preservada no ficheiro platform.html
# e pode ser restaurada rapidamente se for necessário fazer rollback.
@app.get("/plataforma")
@app.get("/plataforma/")
def platform():
    return _react_index()


@app.get("/plataforma/<path:asset>")
def platform_asset(asset):
    return _react_asset(asset)


@app.get("/plataforma-react")
@app.get("/plataforma-react/")
def platform_react():
    return _react_index()


@app.get("/plataforma-react/<path:asset>")
def platform_react_asset(asset):
    return _react_asset(asset)


@app.get("/assistente")
def assistant():
    return _react_index()


@app.get("/assets/<path:asset>")
def public_asset(asset):
    return send_from_directory(REACT_DIST / "assets", asset)


@app.post("/api/platform/public/assistant/chat")
def public_assistant_chat_proxy():
    payload = request.get_json(silent=True) or {}
    upstream_url = os.getenv("PLATFORM_API_URL", "https://negobot-api.duckdns.org").rstrip("/") + "/api/platform/public/assistant/chat"
    try:
        upstream = requests.post(upstream_url, json=payload, timeout=45)
    except requests.RequestException:
        return jsonify({"error": "O assistente está temporariamente indisponível. Tenta novamente ou fala connosco pelo WhatsApp."}), 502
    content_type = upstream.headers.get("Content-Type", "application/json").split(";", 1)[0]
    return Response(upstream.content, status=upstream.status_code, content_type=content_type)


@app.get("/falar-whatsapp")
def talk_whatsapp():
    number = "".join(ch for ch in os.getenv("ASSISTANT_NUMBER", "") if ch.isdigit())
    if not number:
        return jsonify({"error": "Assistente WhatsApp não configurado."}), 503
    return redirect(f"https://wa.me/{number}", code=302)


@app.get("/health")
def health():
    return jsonify({"status": "online", "service": "negobot-site"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)
