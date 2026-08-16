from pathlib import Path

from flask import Blueprint, jsonify, send_from_directory

web_bp = Blueprint("web_bp", __name__)
SITE_ROOT = Path(__file__).resolve().parents[1]


@web_bp.route("/", methods=["GET"])
def home():
    return send_from_directory(SITE_ROOT, "index.html")


@web_bp.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "online", "service": "negobot-moz"}), 200
