# NEGOBOT-MOZ

Negobot Moz é uma plataforma SaaS de chatbot para atendimento via WhatsApp, desenhada para o mercado moçambicano.  
Este repositório contém a aplicação Flask que integra Firestore, Groq (NLP/vision/audio) e Evolution API (WhatsApp).

## Estrutura
- `app.py` / `main.py` — ponto de entrada da aplicação
- `config.py` — configuração via variáveis de ambiente
- `routes.py` — rotas HTTP (webhook, health)
- `services.py` — lógica principal: Firestore, Groq, Evolution, processamento de webhook, onboarding multitenant
- `executor.py` — utilitários para threads/background
- `index.html` — página simples de status (opcional)
- `Procfile` — comando para deploy (Heroku/Render)
- `requirements.txt` — dependências

## Como usar (local)
1. Criar virtualenv e instalar dependências:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
