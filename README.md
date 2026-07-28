# 🤖 Negobot Moz - Ecossistema Modular SaaS & Automação WhatsApp com IA

O **Negobot Moz** é um ecossistema SaaS de atendimento automatizado via WhatsApp alimentado por Inteligência Artificial (Groq - LLaMA 3.3 70B, Qwen Vision e Whisper), totalmente integrado com a Evolution API e Firebase Firestore. O sistema foi arquitetado de forma modular para escalar o atendimento comercial e suporte corporativo em Moçambique.

---

## 🚀 Funcionalidades Principais

* **🤖 Atendimento Multi-Tenant SaaS:** Isolamento total entre o fluxo comercial do Negobot (instância central) e a lógica dos robôs dos subscritores.
* **🎙️ Transcrição Instantânea de Áudio (Whisper):** Converte notas de voz recebidas no WhatsApp em texto com alta precisão via Groq Whisper.
* **👁️ Visão Computacional (Qwen Vision):** Leitura e extração automática de dados contidos em comprovativos bancários, fotos e documentos.
* **📊 Assimilação de Ficheiros (PDF & Excel):** Leitura direta de relatórios e tabelas anexadas, incorporando o conteúdo automaticamente às diretrizes de atendimento.
* **🎨 Geração de Artes Publicitárias (`/criar-arte`):** Criação automática de banners e imagens de marketing utilizando otimização de prompts via IA e engenharia visual.
* **📲 Provisionamento Automático de Instâncias:** Criação automática de instâncias na Evolution API e envio do QR Code diretamente na conversa do WhatsApp para teste gratuito.
* **👨‍💻 Gestão de Transição Humana & Timeout:** Encaminhamento para atendimento humano com monitorização de inatividade e retoma automática pelo bot.

---

## 📁 Estrutura da Arquitetura Modular

```text
NEGOBOT-MOZ/
├── database/          # Gestão de persistência e repositórios do Firestore
│   └── chat_repo.py
├── routes/            # Endpoints Flask (Webhooks da Evolution API e Health Check)
│   ├── webhook_routes.py
│   └── web_routes.py
├── services/          # Conectores de APIs externas (Groq, Evolution, Mídias)
│   ├── evolution_service.py
│   ├── groq_service.py
│   └── media_service.py
├── workflows/         # Regras de negócio e fluxos de conversa isolados
│   ├── central_flow.py
│   └── client_flow.py
├── app.py             # Ponto de entrada e fábrica da aplicação Flask
├── config.py          # Gestão centralizada das variáveis de ambiente
├── extensions.py      # Inicialização das extensões do Firebase
└── requirements.txt   # Dependências e bibliotecas do projeto
