import os
from pathlib import Path

from flask import Flask, jsonify, redirect, send_from_directory

SITE_ROOT = Path(__file__).resolve().parent
app = Flask(__name__, static_folder=None)


@app.get("/")
def home():
    return send_from_directory(SITE_ROOT, "index.html")


@app.get("/plataforma")
def platform():
    return send_from_directory(SITE_ROOT, "platform.html")


REACT_DIST = SITE_ROOT / "platform-react" / "dist"


@app.get("/plataforma-react")
@app.get("/plataforma-react/")
def platform_react():
    return send_from_directory(REACT_DIST, "index.html")


@app.get("/plataforma-react/<path:asset>")
def platform_react_asset(asset):
    if "." not in Path(asset).name:
        return send_from_directory(REACT_DIST, "index.html")
    return send_from_directory(REACT_DIST, asset)


@app.get("/assistente")
def assistant():
    return send_from_directory(SITE_ROOT, "assistant.html")


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
