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
    raw_b64 = os.getenv('FIREBASE_BASE64') or os.getenv('FIREBASE_CONFIG_B64')
    raw_config = os.getenv('FIREBASE_CONFIG') or os.getenv('FIREBASE_JSON')

    render_secret_path = '/etc/secrets/serviceAccountKey.json'
    local_secret_path = 'serviceAccountKey.json'

    # 1. MÉTODO PRINCIPAL: Base64 (Imune a erros de formatação de ambiente)
    if raw_b64:
      try:
        decoded_bytes = base64.b64decode(raw_b64.strip())
        cred_dict = json.loads(decoded_bytes.decode('utf-8'))

        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
        logger.info(
            '📦 [SISTEMA] Firebase inicializado com sucesso via BASE64!'
        )
      except Exception as e:
        logger.error(f'❌ [SISTEMA] Erro ao ler FIREBASE_BASE64: {e}')
        raise e

    # 2. MÉTODO SECUNDÁRIO: JSON direto (Com reconstrutor de PEM)
    elif raw_config:
      try:
        clean_config = raw_config.strip().strip("'").strip('"')
        cred_dict = json.loads(clean_config)

        if 'private_key' in cred_dict:
          pk = cred_dict['private_key']
          pk = pk.replace('\\\\n', '\n').replace('\\n', '\n')

          # Se o Coolify apagou todas as quebras de linha do PEM
          if '-----BEGIN PRIVATE KEY-----' in pk and '\n' not in pk[27:-25]:
            body = (
                pk.replace('-----BEGIN PRIVATE KEY-----', '')
                .replace('-----END PRIVATE KEY-----', '')
                .replace(' ', '')
                .strip()
            )
            # Reconstroi o bloco PEM em linhas estritas de 64 caracteres
            chunks = [body[i : i + 64] for i in range(0, len(body), 64)]
            pk = (
                '-----BEGIN PRIVATE KEY-----\n'
                + '\n'.join(chunks)
                + '\n-----END PRIVATE KEY-----\n'
            )

          cred_dict['private_key'] = pk

        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
        logger.info(
            '📦 [SISTEMA] Firebase inicializado com sucesso via JSON da ENV!'
        )
      except Exception as e:
        logger.error(f'❌ [SISTEMA] Erro ao ler JSON da ENV: {e}')
        raise e

    # 3. MÉTODOS DE FALLBACK: Ficheiros locais
    elif os.path.exists(render_secret_path):
      cred = credentials.Certificate(render_secret_path)
      firebase_admin.initialize_app(cred)
      logger.info(
          '📦 [SISTEMA] Firebase inicializado via Secret File do Render.'
      )

    elif os.path.exists(local_secret_path):
      cred = credentials.Certificate(local_secret_path)
      firebase_admin.initialize_app(cred)
      logger.info(
          '📦 [SISTEMA] Firebase inicializado via ficheiro local'
          ' serviceAccountKey.json.'
      )

    else:
      raise RuntimeError(
          '❌ [SISTEMA CRÍTICO] Credenciais do Firebase não encontradas na'
          ' ENV, em /etc/secrets/ ou localmente!'
      )

  db = firestore.client()
