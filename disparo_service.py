import time
import requests
import asyncio
from typing import List
from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Negobot Moz - Módulo de Disparo em Massa")

# Configurações Globais da Evolution API
EVOLUTION_API_URL = "https://evolution.62.238.52.209.sslip.io"
API_KEY = "negobot_moz_secret_key_2026"

# Modelo de Dados para a Requisição
class DisparoRequest(BaseModel):
    instance_name: str          # Nome da instância (ex: "assistente_negobot")
    numeros: List[str]          # Lista de contactos [ex: "258841234567", "258857654321"]
    mensagem: str               # Texto do anúncio ou promoção
    delay_segundos: int = 4     # Intervalo entre envios (Padrão: 4 segundos)

# Função Privada que Executa o Processamento em Fila
def processar_disparo_em_massa(instance_name: str, numeros: List[str], mensagem: str, delay: int):
    endpoint = f"{EVOLUTION_API_URL}/message/sendText/{instance_name}"
    headers = {
        "apikey": API_KEY,
        "Content-Type": "application/json"
    }
    
    sucessos = 0
    falhas = 0

    print(f"🚀 [DISPARO INICIADO] Instância: {instance_name} | Total: {len(numeros)} contactos")

    for index, numero in enumerate(numeros, start=1):
        # Limpeza simples do número (remover espaços ou caracteres especiais)
        numero_limpo = str(numero).strip().replace("+", "").replace(" ", "").replace("-", "")

        payload = {
            "number": numero_limpo,
            "text": mensagem,
            "delay": 1200  # Tempo de digitação simulado em ms
        }

        try:
            response = requests.post(endpoint, json=payload, headers=headers, timeout=10)
            
            if response.status_code in [200, 201]:
                sucessos += 1
                print(f"[{index}/{len(numeros)}] ✅ Enviado com sucesso para: {numero_limpo}")
            else:
                falhas += 1
                print(f"[{index}/{len(numeros)}] ❌ Erro ao enviar para {numero_limpo}: HTTP {response.status_code}")

        except Exception as e:
            falhas += 1
            print(f"[{index}/{len(numeros)}] ⚠️ Exceção ao contactar {numero_limpo}: {str(e)}")

        # Pausa de segurança para evitar bloqueio / ban do WhatsApp
        time.sleep(delay)

    print(f"🏁 [DISPARO CONCLUÍDO] Enviados: {sucessos} | Falhas: {falhas}")


# Rota Principal para Disparar Mensagens
@app.post("/api/v1/disparo-em-massa")
def disparar_mensagens(dados: DisparoRequest, background_tasks: BackgroundTasks):
    if not dados.numeros:
        raise HTTPException(status_code=400, detail="A lista de números não pode estar vazia.")
    
    if not dados.mensagem.strip():
        raise HTTPException(status_code=400, detail="A mensagem não pode estar vazia.")

    # Adiciona o processo em segundo plano (Assíncrono)
    background_tasks.add_task(
        processar_disparo_em_massa,
        instance_name=dados.instance_name,
        numeros=dados.numeros,
        mensagem=dados.mensagem,
        delay=dados.delay_segundos
    )

    return {
        "status": "sucesso",
        "mensagem": "O disparo em massa foi iniciado em segundo plano com sucesso!",
        "total_destinatarios": len(dados.numeros),
        "instancia": dados.instance_name,
        "intervalo_aplicado": f"{dados.delay_segundos} segundos"
    }
