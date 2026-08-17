import { useState, type FormEvent } from "react";
import { ArrowUpRight, Bot, Check, CheckCircle2, ChevronRight, FileText, MessageCircle, Mic, Send, Sparkles, Users, X } from "lucide-react";

type ChatMessage = { role: "user" | "assistant"; content: string };

const plans = [
  {
    id: "basico",
    label: "BÁSICO",
    name: "Plano Básico",
    price: "500 MT",
    description: "Para negócios que querem começar a responder com consistência.",
    benefits: ["Até 1.500 conversas por mês", "FAQ, horário e catálogo em texto", "1 número de WhatsApp", "Suporte básico até 24 horas"],
  },
  {
    id: "medio",
    label: "CRESCIMENTO",
    name: "Plano Médio",
    price: "1.000 MT",
    description: "Para equipas que precisam de mais contexto e acompanhamento.",
    benefits: ["Conversas ilimitadas", "Fotos e leitura básica de Excel", "Menu interativo e relatórios", "Suporte prioritário até 12 horas"],
  },
  {
    id: "premium",
    label: "MAIS COMPLETO",
    name: "Plano Premium",
    price: "1.500 MT",
    description: "Para operações que querem automatizar marketing e atendimento.",
    benefits: ["IA avançada e documentos", "Áudio, PDFs e artes publicitárias", "Disparos e campanhas em massa", "Suporte dedicado e configuração assistida"],
  },
];

const features = [
  { number: "01", kicker: "ATENDER", title: "Resposta imediata", text: "Atendimento automatizado via WhatsApp para perguntas frequentes, suporte e orientação comercial.", icon: MessageCircle },
  { number: "02", kicker: "ENTENDER", title: "IA que interpreta", text: "Áudio, imagens, comprovativos, PDFs e folhas de cálculo entram no fluxo certo para cada cliente.", icon: Sparkles },
  { number: "03", kicker: "ESCALAR", title: "Do bot para a equipa", text: "Quando uma conversa precisa de uma pessoa, a equipa assume sem perder o contexto.", icon: Users },
];

function Brand({ dark = false }: { dark?: boolean }) {
  return <span className={`public-brand ${dark ? "public-brand-dark" : ""}`}><span className="public-brand-mark"><Bot size={18} /></span><span><strong>NEGOBOT</strong><small>MOZ</small></span></span>;
}

function PublicNav({ onAssistant }: { onAssistant?: () => void }) {
  return <header className="public-nav"><div className="public-container public-nav-inner"><a href="#top" aria-label="NEGOBOT-MOZ início"><Brand /></a><nav className="public-nav-links" aria-label="Navegação principal"><a href="#capacidades">Capacidades</a><a href="#planos">Planos</a><a href="#como-funciona">Como funciona</a><a href="#contacto">Contacto</a></nav><button className="public-nav-cta" onClick={onAssistant || (() => { window.location.href = "/assistente"; })}>Falar com assistente <ArrowUpRight size={15} /></button></div></header>;
}

export function PublicSite() {
  const [assistantOpen, setAssistantOpen] = useState(false);
  return <div className="public-site" id="top"><PublicNav onAssistant={() => setAssistantOpen(true)} /><main>
    <section className="public-hero"><div className="public-hero-glow" /><div className="public-container public-hero-grid"><div className="public-hero-copy"><p className="public-eyebrow">Inteligência para atendimento</p><h1>Mais respostas.<br /><em>Mais negócio.</em></h1><p className="public-lead">O NEGOBOT-MOZ transforma conversas no WhatsApp em atendimento consistente, suporte mais rápido e novas oportunidades para empresas em Moçambique.</p><div className="public-actions"><a className="public-button public-button-primary" href="/falar-whatsapp">Falar com assistente WhatsApp <ArrowUpRight size={17} /></a><button className="public-button public-button-ghost" onClick={() => setAssistantOpen(true)}>Falar com assistente na plataforma <MessageCircle size={17} /></button></div><p className="public-note"><span className="public-live-dot" /> Demonstração de 2 dias · sem compromisso</p></div><div className="public-signal-card" aria-label="Exemplo de conversa com o NEGOBOT-MOZ"><div className="public-card-top"><span>NEGOBOT / CENTRAL</span><span className="public-live">ONLINE</span></div><div className="public-chat-window"><div className="public-bubble">Olá. Preciso de ajuda com o meu pedido.<small>10:42</small></div><div className="public-bubble public-bubble-bot">Claro. Vou verificar os detalhes e orientar-te já de seguida.<small>10:42 · resposta automática</small></div><div className="public-bubble">Também posso enviar um comprovativo?<small>10:43</small></div><div className="public-bubble public-bubble-bot">Sim. Envia a imagem aqui. A visão da IA ajuda-nos a extrair os dados relevantes.<small>10:43 · visão computacional</small></div></div><div className="public-float-label"><span><CheckCircle2 size={16} /></span>Atendimento que não para</div></div></div></section>
    <section className="public-trust" aria-label="Integrações"><div className="public-container public-trust-inner"><span>Construído para operações modernas</span><div><b>WHATSAPP</b><b>GROQ AI</b><b>EVOLUTION API</b><b>FIREBASE</b></div></div></section>
    <section className="public-section" id="capacidades"><div className="public-container"><div className="public-section-head"><h2>Uma camada inteligente para cada conversa.</h2><p>Da primeira mensagem ao acompanhamento humano, o NEGOBOT-MOZ organiza o atendimento sem perder contexto.</p></div><div className="public-feature-grid">{features.map(({ number, kicker, title, text, icon: Icon }) => <article className="public-feature" key={number}><span className="public-feature-number">{number} / {kicker}</span><div className="public-feature-icon"><Icon size={20} /></div><h3>{title}</h3><p>{text}</p></article>)}</div></div></section>
    <section className="public-section public-plans-section" id="planos"><div className="public-container"><div className="public-section-head"><h2>Um plano para cada fase do teu negócio.</h2><p>Começa com 2 dias de demonstração e escolhe o nível de automação que combina com a tua operação.</p></div><div className="public-plans-grid">{plans.map((plan) => <article className={`public-plan ${plan.id === "premium" ? "public-plan-featured" : ""}`} key={plan.id}><p className="public-plan-label">{plan.label}</p><h3>{plan.name}</h3><p className="public-plan-description">{plan.description}</p><div className="public-price">{plan.price}<small>/ mês</small></div><ul>{plan.benefits.map((benefit) => <li key={benefit}><Check size={15} />{benefit}</li>)}</ul><button className={`public-button ${plan.id === "premium" ? "public-button-primary" : "public-button-light"}`} onClick={() => setAssistantOpen(true)}>Escolher {plan.name.replace("Plano ", "")} <ChevronRight size={16} /></button></article>)}</div></div></section>
    <section className="public-section public-dark-section" id="como-funciona"><div className="public-container public-workflow"><div><p className="public-eyebrow">Como funciona</p><h2>A conversa certa,<br />no momento certo.</h2><p className="public-workflow-copy">O ecossistema modular do NEGOBOT-MOZ liga WhatsApp, IA, automações e persistência de dados para criar experiências de atendimento mais simples.</p><div className="public-channel-row"><span><MessageCircle size={16} /> WhatsApp</span><span><Mic size={16} /> Áudio</span><span><FileText size={16} /> Documentos</span></div></div><div className="public-steps">{[{ num: "1", title: "O cliente envia uma mensagem", text: "Texto, áudio, imagem ou documento chegam pelo canal de WhatsApp." }, { num: "2", title: "O NEGOBOT interpreta o contexto", text: "Os fluxos combinam regras do negócio e modelos de IA para preparar a resposta." }, { num: "3", title: "A equipa acompanha quando necessário", text: "O atendimento humano assume a conversa sem quebrar a experiência do cliente." }].map((step) => <article className="public-step" key={step.num}><span>{step.num}</span><div><h3>{step.title}</h3><p>{step.text}</p></div></article>)}</div></div></section>
    <section className="public-cta" id="contacto"><div className="public-container public-cta-inner"><div><p className="public-eyebrow public-eyebrow-dark">Começa agora</p><h2>Pronto para atender melhor?</h2><p>Fala com o assistente e descobre como o NEGOBOT-MOZ se adapta à tua operação.</p></div><div className="public-actions"><a className="public-button public-button-dark" href="/falar-whatsapp">Falar pelo WhatsApp <ArrowUpRight size={17} /></a><button className="public-button public-button-outline-dark" onClick={() => setAssistantOpen(true)}>Falar na plataforma <MessageCircle size={17} /></button></div></div></section>
  </main><footer className="public-footer"><div className="public-container public-footer-inner"><a href="#top"><Brand dark /></a><span>Atendimento inteligente para negócios em Moçambique.</span><span>© 2026 NEGOBOT-MOZ</span><div className="public-socials" aria-label="Redes sociais"><span>IG</span><span>in</span></div></div></footer>{assistantOpen && <PublicAssistantDialog onClose={() => setAssistantOpen(false)} />}</div>;
}

function PublicAssistantDialog({ onClose }: { onClose: () => void }) {
  const [message, setMessage] = useState(""); const [messages, setMessages] = useState<ChatMessage[]>([{ role: "assistant", content: "Olá. Sou o assistente comercial do NEGOBOT-MOZ. Posso explicar os planos, benefícios e como ligar o teu WhatsApp. Como posso ajudar?" }]); const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  async function submit(event: FormEvent) { event.preventDefault(); const value = message.trim(); if (!value || busy) return; setMessage(""); setError(""); setMessages((current) => [...current, { role: "user", content: value }]); setBusy(true); try { const response = await fetch("/api/platform/public/assistant/chat", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message: value, source: "platform" }) }); const data = await response.json(); if (!response.ok) throw new Error(data.error || "Não foi possível responder agora."); setMessages((current) => [...current, { role: "assistant", content: data.answer || "Fala connosco pelo WhatsApp para continuarmos." }]); } catch (reason) { setError(reason instanceof Error ? reason.message : "Tenta novamente ou fala connosco pelo WhatsApp."); } finally { setBusy(false); } }
  return <div className="public-modal-backdrop" role="dialog" aria-modal="true" aria-label="Assistente comercial"><section className="public-assistant-modal"><div className="public-assistant-head"><div><span className="public-eyebrow">Assistente comercial</span><h2>Fala com o NEGOBOT</h2></div><button className="public-close" onClick={onClose} aria-label="Fechar assistente"><X size={19} /></button></div><div className="public-assistant-messages">{messages.map((item, index) => <div className={`public-assistant-message ${item.role}`} key={`${item.role}-${index}`}>{item.content}</div>)}{busy && <div className="public-assistant-message assistant public-typing"><span /><span /><span /></div>}</div>{error && <p className="public-assistant-error">{error}</p>}<form className="public-assistant-form" onSubmit={submit}><input value={message} onChange={(event) => setMessage(event.target.value)} placeholder="Escreve a tua pergunta..." aria-label="Mensagem para o assistente" maxLength={1200} /><button type="submit" disabled={busy || !message.trim()} aria-label="Enviar mensagem"><Send size={17} /></button></form><a className="public-assistant-whatsapp" href="/falar-whatsapp"><MessageCircle size={16} /> Preferes falar pelo WhatsApp?</a></section></div>;
}

export function PublicAssistantPage() {
  return <div className="public-site public-assistant-page"><PublicNav /><main className="public-assistant-page-main"><div className="public-container public-assistant-page-grid"><div><p className="public-eyebrow">Assistente na plataforma</p><h1>Conversa com quem conhece o teu negócio.</h1><p className="public-lead public-lead-light">Pergunta sobre planos, pagamentos M-Pesa, ligação do WhatsApp ou o fluxo de atendimento. O assistente orienta-te em Português de Moçambique.</p><div className="public-actions"><a className="public-button public-button-primary" href="/falar-whatsapp">Falar pelo WhatsApp <ArrowUpRight size={17} /></a><a className="public-button public-button-ghost" href="/#planos">Ver planos <ChevronRight size={17} /></a></div></div><PublicAssistantDialog onClose={() => { window.location.href = "/"; }} /></div></main></div>;
}
