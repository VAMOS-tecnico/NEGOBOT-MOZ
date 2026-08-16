import base64
import json
import logging
import os

import firebase_admin
from firebase_admin import credentials, firestore

logger = logging.getLogger(__name__)
db = None


def init_extensions(app=None):
    global db

    if not firebase_admin._apps:
        # Não deixar o SDK tentar interpretar FIREBASE_CONFIG como configuração
        # automática; tratamos o JSON explicitamente abaixo.
        raw_config = os.environ.pop("FIREBASE_CONFIG", None)
        local_secret_path = "serviceAccountKey.json"
        render_secret_path = "/etc/secrets/serviceAccountKey.json"
        raw_b64 = os.getenv("FIREBASE_BASE64") or os.getenv("FIREBASE_CONFIG_B64")
        cred = None

        if os.path.exists(local_secret_path):
            try:
                cred = credentials.Certificate(local_secret_path)
                logger.info("Firebase inicializado via serviceAccountKey.json local")
            except Exception as exc:
                logger.warning("Falha ao carregar credencial local: %s", type(exc).__name__)

        if not cred and os.path.exists(render_secret_path):
            try:
                cred = credentials.Certificate(render_secret_path)
                logger.info("Firebase inicializado via ficheiro de segredo")
            except Exception as exc:
                logger.warning("Falha ao carregar ficheiro de segredo: %s", type(exc).__name__)

        if not cred and raw_b64:
            try:
                decoded = base64.b64decode(raw_b64.strip())
                cred = credentials.Certificate(json.loads(decoded.decode("utf-8")))
                logger.info("Firebase inicializado via configuração Base64")
            except Exception as exc:
                logger.warning("Falha ao carregar configuração Base64: %s", type(exc).__name__)

        if not cred and raw_config:
            try:
                clean_config = raw_config.strip().strip("'").strip('"')
                cred_dict = json.loads(clean_config)
                if "private_key" in cred_dict:
                    private_key = str(cred_dict["private_key"])
                    private_key = private_key.replace("\\\\n", "\n").replace("\\n", "\n")
                    if "-----BEGIN PRIVATE KEY-----" in private_key and "\n" not in private_key[27:-25]:
                        body = (
                            private_key.replace("-----BEGIN PRIVATE KEY-----", "")
                            .replace("-----END PRIVATE KEY-----", "")
                            .replace(" ", "")
                            .strip()
                        )
                        chunks = [body[i : i + 64] for i in range(0, len(body), 64)]
                        private_key = "-----BEGIN PRIVATE KEY-----\n" + "\n".join(chunks) + "\n-----END PRIVATE KEY-----\n"
                    cred_dict["private_key"] = private_key
                cred = credentials.Certificate(cred_dict)
                logger.info("Firebase inicializado via JSON da variável de ambiente")
            except Exception as exc:
                logger.warning("Falha ao carregar JSON Firebase: %s", type(exc).__name__)

        if not cred:
            raise RuntimeError("Nenhuma credencial válida do Firebase foi encontrada.")
        firebase_admin.initialize_app(cred)

    db = firestore.client()
    return db
