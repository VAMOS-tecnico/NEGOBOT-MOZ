import io
import requests
import urllib.parse
from pypdf import PdfReader
import pandas as pd
from services.groq_service import chamar_groq_rest

def extrair_texto_pdf_url(pdf_url):
    try:
        response = requests.get(pdf_url, timeout=25)
        if response.status_code == 200:
            pdf_file = io.BytesIO(response.content)
            reader = PdfReader(pdf_file)
            texto_completo = ""
            for idx, page in enumerate(reader.pages, start=1):
                conteudo_pagina = page.extract_text()
                if conteudo_pagina:
                    texto_completo += f"\n--- PÁGINA {idx} ---\n" + conteudo_pagina
            return texto_completo
    except Exception as e:
        print(f"❌ Erro ao ler PDF da URL {pdf_url}: {e}")
    return ""

def extrair_texto_excel_url(excel_url):
    try:
        response = requests.get(excel_url, timeout=25)
        if response.status_code == 200:
            excel_file = io.BytesIO(response.content)
            todas_abas = pd.read_excel(excel_file, sheet_name=None)
            texto_completo = ""
            for nome_aba, df in todas_abas.items():
                texto_completo += f"\n--- ABA EXCEL: {nome_aba} ---\n"
                texto_completo += df.to_string(index=False) + "\n"
            return texto_completo
    except Exception as e:
        print(f"❌ Erro ao ler Excel da URL {excel_url}: {e}")
    return ""

def criar_prompt_profissional_groq(pedido_utilizador):
    try:
        sys_instruction = (
            "Você é um especialista em Engenharia de Prompts para geração de imagens publicitárias. "
            "Converta o pedido do utilizador num prompt altamente detalhado em INGLÊS. "
            "Adicione detalhes de qualidade visual e contexto corporativo moçambicano como: "
            "'professional marketing banner, microfinance Mozambique context, bright clean lighting, photorealistic, 8k'. "
            "Responda APENAS com o prompt em inglês, sem saudações."
        )
        contents = [{"parts": [{"text": pedido_utilizador}]}]
        resultado = chamar_groq_rest(contents, system_instruction=sys_instruction, temperature=0.7)
        return resultado if resultado else pedido_utilizador
    except Exception as e:
        print(f"❌ Erro ao otimizar prompt no Groq: {e}")
        return pedido_utilizador

def gerar_url_imagem_pollinations(prompt_otimizado):
    prompt_encoded = urllib.parse.quote(prompt_otimizado)
    return f"https://pollinations.ai/p/{prompt_encoded}?width=1024&height=1024&model=flux&seed=42"
