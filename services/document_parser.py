import io
import requests
import pandas as pd
from pypdf import PdfReader
import logging

logger = logging.getLogger(__name__)

def extrair_conteudo_documento(media_url, file_extension, apikey):
    """
    Descarrega o ficheiro enviado pelo WhatsApp usando a Evolution API e extrai o texto.
    """
    try:
        headers = {"apikey": apikey}
        response = requests.get(media_url, headers=headers)
        
        if response.status_code != 200:
            logger.error(f"Erro ao descarregar media. Status: {response.status_code}")
            return None
            
        file_stream = io.BytesIO(response.content)
        conteudo_extraido = ""
        ext = file_extension.lower()

        # Leitura de PDF
        if ext == '.pdf':
            reader = PdfReader(file_stream)
            for page in reader.pages:
                texto_pagina = page.extract_text()
                if texto_pagina:
                    conteudo_extraido += texto_pagina + "\n"
                    
        # Leitura de Excel ou CSV
        elif ext in ['.xlsx', '.xls', '.csv']:
            df = ler_tabela_por_extensao(file_stream, ext)
            if df is not None:
                # Converte os dados da tabela num formato de texto legível para a IA
                conteudo_extraido = df.to_string(index=False)

        return conteudo_extraido.strip()

    except Exception as e:
        logger.error(f"Erro ao processar o documento: {str(e)}", exc_info=True)
        return None

def ler_tabela_por_extensao(file_stream, ext):
    try:
        if ext == '.csv':
            return pd.read_csv(file_stream)
        else:
            return pd.read_excel(file_stream)
    except Exception as e:
        logger.error(f"Erro ao ler tabela (Excel/CSV): {str(e)}")
        return None
