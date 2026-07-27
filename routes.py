from flask import Blueprint, request, jsonify, send_file
from services import processar_webhook_background
import os
import threading

def register_routes(app):
    bp = Blueprint("webhook", __name__)

    @bp.route("/", methods=["GET"])
    def health():
        idx = os.path.join(os.path.dirname(__file__), "index.html")
        try:
            return send_file(idx)
        except Exception:
            return "Negobot Moz operacional", 200

    @bp.route("/webhook", methods=["POST"])
    @bp.route("/webhook-global", methods=["POST"])
    @bp.route("/webhook-cliente", methods=["POST"])
    def webhook():
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"status":"ok"}), 200
        # processa em background para não bloquear a requisição
        threading.Thread(target=processar_webhook_background, args=(data,), daemon=True).start()
        return jsonify({"status":"received"}), 202

    app.register_blueprint(bp, url_prefix="")
