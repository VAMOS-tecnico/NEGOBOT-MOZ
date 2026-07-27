# NEGOBOT-MOZ

Negobot Moz é uma plataforma SaaS de chatbot para atendimento via WhatsApp, desenhada para o mercado moçambicano.

## Estrutura principal
- `app.py` / `main.py` — ponto de entrada da aplicação
- `config.py` — configuração via variáveis de ambiente
- `routes.py` — rotas HTTP (webhook, health)
- `services.py` — lógica principal: Firestore, Groq, Evolution, processamento de webhook, onboarding multitenant
- `executor.py` — worker que automatiza criação de instâncias e envio de QR Codes
- `index.html` — página simples de status
- `Procfile` — comando para deploy (web + worker)
- `requirements.txt` — dependências

## Instalação local
1. Criar virtualenv e instalar dependências:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
