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
        local_secret_path = 'serviceAccountKey.json'
        render_secret_path = '/etc/secrets/serviceAccountKey.json'
        raw_b64 = os.getenv('FIREBASE_BASE64') or os.getenv('FIREBASE_CONFIG_B64')
        raw_config = os.getenv('FIREBASE_CONFIG') or os.getenv('FIREBASE_JSON')

        cred = None

        # 1. PRIORIDADE 1: Ficheiro local serviceAccountKey.json (Ignora erros de formatação do .env)
        if os.path.exists(local_secret_path):
            try:
                cred = credentials.Certificate(local_secret_path)
                logger.info('📦 Firebase inicializado via serviceAccountKey.json local!')
            except Exception as e:
                logger.warning(f'⚠️ Falha ao carregar serviceAccountKey.json local: {e}')

        # 2. PRIORIDADE 2: Ficheiro de segredos do Render
        if not cred and os.path.exists(render_secret_path):
            try:
                cred = credentials.Certificate(render_secret_path)
                logger.info('📦 Firebase inicializado via Secret File do Render!')
            except Exception as e:
                logger.warning(f'⚠️ Falha ao carregar secret do Render: {e}')

        # 3. PRIORIDADE 3: Base64 da ENV
        if not cred and raw_b64:
            try:
                decoded_bytes = base64.b64decode(raw_b64.strip())
                cred_dict = json.loads(decoded_bytes.decode('utf-8'))
                cred = credentials.Certificate(cred_dict)
                logger.info('📦 Firebase inicializado via BASE64!')
            except Exception as e:
                logger.warning(f'⚠️ Falha ao carregar BASE64: {e}')

        # 4. PRIORIDADE 4: JSON direto da ENV
        if not cred and raw_config:
            try:
                clean_config = raw_config.strip().strip("'").strip('"')
                cred_dict = json.loads(clean_config)

                if 'private_key' in cred_dict:
                    pk = cred_dict['private_key']
                    pk = pk.replace('\\\\n', '\n').replace('\\n', '\n')

                    if '-----BEGIN PRIVATE KEY-----' in pk and '\n' not in pk[27:-25]:
                        body = (
                            pk.replace('-----BEGIN PRIVATE KEY-----', '')
                            .replace('-----END PRIVATE KEY-----', '')
                            .replace(' ', '')
                            .strip()
                        )
                        chunks = [body[i : i + 64] for i in range(0, len(body), 64)]
                        pk = (
                            '-----BEGIN PRIVATE KEY-----\n'
                            + '\n'.join(chunks)
                            + '\n-----END PRIVATE KEY-----\n'
                        )

                    cred_dict['private_key'] = pk

                cred = credentials.Certificate(cred_dict)
                logger.info('📦 Firebase inicializado via JSON da ENV!')
            except Exception as e:
                logger.warning(f'⚠️ Falha ao carregar JSON da ENV: {e}')

        # Inicialização final do Firebase
        if cred:
            firebase_admin.initialize_app(cred)
        else:
            raise RuntimeError(
                '❌ [SISTEMA CRÍTICO] Nenhuma credencial válida do Firebase foi encontrada.'
            )

    db = firestore.client()
