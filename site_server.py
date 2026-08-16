from pathlib import Path

from flask import Flask, jsonify, send_from_directory

SITE_ROOT = Path(__file__).resolve().parent
app = Flask(__name__, static_folder=None)


@app.get("/")
def home():
    return send_from_directory(SITE_ROOT, "index.html")


@app.get("/health")
def health():
    return jsonify({"status": "online", "service": "negobot-site"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)
