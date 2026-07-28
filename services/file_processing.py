import requests
import io
import urllib.parse
import logging
from pypdf import PdfReader
import pandas as pd

logger = logging.getLogger(__name__)

def extrair_texto_pdf_url(pdf_url):
    """Extrai texto de um PDF a partir de URL."""
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
            logger.info(f"✅ PDF extraído com sucesso: {len(texto_completo)} caracteres")
            return texto_completo
    except Exception as e:
        logger.error(f"❌ Erro ao ler PDF da URL {pdf_url}: {e}")
    return ""

def extrair_texto_excel_url(excel_url):
    """Extrai texto de um ficheiro Excel a partir de URL."""
    try:
        response = requests.get(excel_url, timeout=25)
        if response.status_code == 200:
            excel_file = io.BytesIO(response.content)
            todas_abas = pd.read_excel(excel_file, sheet_name=None)
            texto_completo = ""
            for nome_aba, df in todas_abas.items():
                texto_completo += f"\n--- ABA EXCEL: {nome_aba} ---\n"
                texto_completo += df.to_string(index=False) + "\n"
            logger.info(f"✅ Excel extraído com sucesso: {len(texto_completo)} caracteres")
            return texto_completo
    except Exception as e:
        logger.error(f"❌ Erro ao ler Excel da URL {excel_url}: {e}")
    return ""

def gerar_url_imagem_pollinations(prompt_otimizado):
    """Gera URL de imagem via Pollinations AI."""
    prompt_encoded = urllib.parse.quote(prompt_otimizado)
    return f"https://pollinations.ai/p/{prompt_encoded}?width=1024&height=1024&model=flux&seed=42"
