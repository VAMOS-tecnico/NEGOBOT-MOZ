import { useEffect, useState, type FormEvent } from "react";
import { ArrowUpRight, Bot, Check, CheckCircle2, ChevronRight, FileText, MessageCircle, Mic, Send, Sparkles, Users, X } from "lucide-react";

type Language = "pt" | "en";
type ChatMessage = { role: "user" | "assistant"; content: string };

type PublicCopy = {
  nav: { capabilities: string; plans: string; how: string; contact: string; assistant: string; language: string };
  hero: { eyebrow: string; titleA: string; titleB: string; lead: string; whatsapp: string; platform: string; note: string; signal: string; online: string; bubble1: string; bubble2: string; bubble2Meta: string; bubble3: string; bubble4: string; bubble4Meta: string; float: string };
  trust: string;
  capabilities: { title: string; text: string };
  features: { number: string; kicker: string; title: string; text: string; icon: typeof MessageCircle }[];
  plansIntro: { title: string; text: string };
  plans: { id: string; label: string; name: string; price: string; month: string; description: string; benefits: string[] }[];
  choose: string;
  current: string;
  workflow: { eyebrow: string; titleA: string; titleB: string; text: string; steps: { num: string; title: string; text: string }[] };
  cta: { eyebrow: string; title: string; text: string; whatsapp: string; platform: string };
  footer: string;
  assistant: { eyebrow: string; title: string; welcome: string; placeholder: string; send: string; close: string; whatsapp: string; error: string; fallback: string; pageEyebrow: string; pageTitle: string; pageLead: string; viewPlans: string };
};

const COPY: Record<Language, PublicCopy> = {
  pt: {
    nav: { capabilities: "Capacidades", plans: "Planos", how: "Como funciona", contact: "Contacto", assistant: "Falar com assistente", language: "Idioma" },
    hero: { eyebrow: "Inteligência para atendimento", titleA: "Mais respostas.", titleB: "Mais negócio.", lead: "O NEGOBOT-MOZ transforma conversas no WhatsApp em atendimento consistente, suporte mais rápido e novas oportunidades para empresas em Moçambique.", whatsapp: "Falar com assistente WhatsApp", platform: "Falar com assistente na plataforma", note: "Demonstração de 2 dias · sem compromisso", signal: "NEGOBOT / CENTRAL", online: "ONLINE", bubble1: "Olá. Preciso de ajuda com o meu pedido.", bubble2: "Claro. Vou verificar os detalhes e orientar-te já de seguida.", bubble2Meta: "10:42 · resposta automática", bubble3: "Também posso enviar um comprovativo?", bubble4: "Sim. Envia a imagem aqui. A visão da IA ajuda-nos a extrair os dados relevantes.", bubble4Meta: "10:43 · visão computacional", float: "Atendimento que não para" },
    trust: "Construído para operações modernas",
    capabilities: { title: "Uma camada inteligente para cada conversa.", text: "Da primeira mensagem ao acompanhamento humano, o NEGOBOT-MOZ organiza o atendimento sem perder contexto." },
    features: [
      { number: "01", kicker: "ATENDER", title: "Resposta imediata", text: "Atendimento automatizado via WhatsApp para perguntas frequentes, suporte e orientação comercial.", icon: MessageCircle },
      { number: "02", kicker: "ENTENDER", title: "IA que interpreta", text: "Áudio, imagens, comprovativos, PDFs e folhas de cálculo entram no fluxo certo para cada cliente.", icon: Sparkles },
      { number: "03", kicker: "ESCALAR", title: "Do bot para a equipa", text: "Quando uma conversa precisa de uma pessoa, a equipa assume sem perder o contexto.", icon: Users },
    ],
    plansIntro: { title: "Um plano para cada fase do teu negócio.", text: "Começa com 2 dias de demonstração e escolhe o nível de automação que combina com a tua operação." },
    plans: [
      { id: "basico", label: "BÁSICO", name: "Plano Básico", price: "500 MT", month: "/ mês", description: "Para negócios que querem começar a responder com consistência.", benefits: ["Até 1.500 conversas por mês", "FAQ, horário e catálogo em texto", "1 número de WhatsApp", "Suporte básico até 24 horas"] },
      { id: "medio", label: "CRESCIMENTO", name: "Plano Médio", price: "1.000 MT", month: "/ mês", description: "Para equipas que precisam de mais contexto e acompanhamento.", benefits: ["Conversas ilimitadas", "Fotos e leitura básica de Excel", "Menu interativo e relatórios", "Suporte prioritário até 12 horas"] },
      { id: "premium", label: "MAIS COMPLETO", name: "Plano Premium", price: "1.500 MT", month: "/ mês", description: "Para operações que querem automatizar marketing e atendimento.", benefits: ["IA avançada e documentos", "Áudio, PDFs e artes publicitárias", "Disparos e campanhas em massa", "Suporte dedicado e configuração assistida"] },
    ],
    choose: "Escolher", current: "Plano atual",
    workflow: { eyebrow: "Como funciona", titleA: "A conversa certa,", titleB: "no momento certo.", text: "O ecossistema modular do NEGOBOT-MOZ liga WhatsApp, IA, automações e persistência de dados para criar experiências de atendimento mais simples.", steps: [{ num: "1", title: "O cliente envia uma mensagem", text: "Texto, áudio, imagem ou documento chegam pelo canal de WhatsApp." }, { num: "2", title: "O NEGOBOT interpreta o contexto", text: "Os fluxos combinam regras do negócio e modelos de IA para preparar a resposta." }, { num: "3", title: "A equipa acompanha quando necessário", text: "O atendimento humano assume a conversa sem quebrar a experiência do cliente." }] },
    cta: { eyebrow: "Começa agora", title: "Pronto para atender melhor?", text: "Fala com o assistente e descobre como o NEGOBOT-MOZ se adapta à tua operação.", whatsapp: "Falar pelo WhatsApp", platform: "Falar na plataforma" },
    footer: "Atendimento inteligente para negócios em Moçambique.",
    assistant: { eyebrow: "Assistente comercial", title: "Fala com o NEGOBOT", welcome: "Olá. Sou o assistente comercial do NEGOBOT-MOZ. Posso explicar os planos, benefícios e como ligar o teu WhatsApp. Como posso ajudar?", placeholder: "Escreve a tua pergunta...", send: "Enviar mensagem", close: "Fechar assistente", whatsapp: "Preferes falar pelo WhatsApp?", error: "Tenta novamente ou fala connosco pelo WhatsApp.", fallback: "Fala connosco pelo WhatsApp para continuarmos.", pageEyebrow: "Assistente na plataforma", pageTitle: "Conversa com quem conhece o teu negócio.", pageLead: "Pergunta sobre planos, pagamentos M-Pesa, ligação do WhatsApp ou o fluxo de atendimento. O assistente orienta-te em Português de Moçambique.", viewPlans: "Ver planos" },
  },
  en: {
    nav: { capabilities: "Capabilities", plans: "Plans", how: "How it works", contact: "Contact", assistant: "Talk to an assistant", language: "Language" },
    hero: { eyebrow: "Intelligence for customer care", titleA: "More answers.", titleB: "More business.", lead: "NEGOBOT-MOZ turns WhatsApp conversations into consistent service, faster support and new opportunities for businesses in Mozambique and beyond.", whatsapp: "Talk to the WhatsApp assistant", platform: "Talk to the platform assistant", note: "2-day demonstration · no commitment", signal: "NEGOBOT / CENTRAL", online: "ONLINE", bubble1: "Hi. I need help with my request.", bubble2: "Of course. I will check the details and guide you right away.", bubble2Meta: "10:42 · automated reply", bubble3: "Can I also send a receipt?", bubble4: "Yes. Send the image here. AI vision helps us extract the relevant details.", bubble4Meta: "10:43 · computer vision", float: "Support that never stops" },
    trust: "Built for modern operations",
    capabilities: { title: "An intelligent layer for every conversation.", text: "From the first message to human follow-up, NEGOBOT-MOZ organizes customer care without losing context." },
    features: [
      { number: "01", kicker: "RESPOND", title: "Instant answers", text: "Automated WhatsApp support for common questions, customer care and commercial guidance.", icon: MessageCircle },
      { number: "02", kicker: "UNDERSTAND", title: "AI that interprets", text: "Audio, images, receipts, PDFs and spreadsheets are routed into the right flow for each customer.", icon: Sparkles },
      { number: "03", kicker: "SCALE", title: "From bot to team", text: "When a conversation needs a person, your team takes over without losing context.", icon: Users },
    ],
    plansIntro: { title: "A plan for every stage of your business.", text: "Start with a 2-day demonstration and choose the automation level that fits your operation." },
    plans: [
      { id: "basico", label: "BASIC", name: "Basic Plan", price: "500 MT", month: "/ month", description: "For businesses ready to start answering consistently.", benefits: ["Up to 1,500 conversations per month", "FAQ, hours and text catalog", "1 WhatsApp number", "Basic support within 24 hours"] },
      { id: "medio", label: "GROWTH", name: "Growth Plan", price: "1,000 MT", month: "/ month", description: "For teams that need more context and follow-up.", benefits: ["Unlimited conversations", "Photos and basic Excel reading", "Interactive menu and reports", "Priority support within 12 hours"] },
      { id: "premium", label: "MOST COMPLETE", name: "Premium Plan", price: "1,500 MT", month: "/ month", description: "For operations ready to automate marketing and customer care.", benefits: ["Advanced AI and documents", "Audio, PDFs and advertising artwork", "Mass broadcasts and campaigns", "Dedicated support and assisted setup"] },
    ],
    choose: "Choose", current: "Current plan",
    workflow: { eyebrow: "How it works", titleA: "The right conversation,", titleB: "at the right moment.", text: "NEGOBOT-MOZ connects WhatsApp, AI, automations and persistent data to create simpler customer-care experiences.", steps: [{ num: "1", title: "A customer sends a message", text: "Text, audio, image or document arrives through WhatsApp." }, { num: "2", title: "NEGOBOT understands the context", text: "Business rules and AI models work together to prepare the right response." }, { num: "3", title: "Your team steps in when needed", text: "Human support takes over without breaking the customer experience." }] },
    cta: { eyebrow: "Get started", title: "Ready to serve better?", text: "Talk to the assistant and discover how NEGOBOT-MOZ fits your operation.", whatsapp: "Talk via WhatsApp", platform: "Talk on the platform" },
    footer: "Intelligent customer care for businesses in Mozambique.",
    assistant: { eyebrow: "Sales assistant", title: "Talk to NEGOBOT", welcome: "Hello. I am the NEGOBOT-MOZ sales assistant. I can explain plans, benefits and how to connect your WhatsApp. How can I help?", placeholder: "Write your question...", send: "Send message", close: "Close assistant", whatsapp: "Prefer WhatsApp?", error: "Try again or talk to us on WhatsApp.", fallback: "Talk to us on WhatsApp to continue.", pageEyebrow: "Platform assistant", pageTitle: "Talk to the team that knows your business.", pageLead: "Ask about plans, online payments, WhatsApp connection or the customer-care flow. The assistant will guide you in English.", viewPlans: "View plans" },
  },
};

function useLanguage() {
  const [language, setLanguage] = useState<Language>(() => {
    if (typeof window === "undefined") return "pt";
    return window.localStorage.getItem("negobot-public-language") === "en" ? "en" : "pt";
  });
  useEffect(() => { window.localStorage.setItem("negobot-public-language", language); document.documentElement.lang = language; }, [language]);
  return { language, setLanguage, copy: COPY[language] };
}

function Brand({ dark = false }: { dark?: boolean }) {
  return <span className={`public-brand ${dark ? "public-brand-dark" : ""}`}><span className="public-brand-mark"><Bot size={18} /></span><span><strong>NEGOBOT</strong><small>MOZ</small></span></span>;
}

function LanguageSwitcher({ language, setLanguage, label }: { language: Language; setLanguage: (language: Language) => void; label: string }) {
  return <div className="public-language-switcher" aria-label={label}><button className={language === "pt" ? "active" : ""} aria-pressed={language === "pt"} onClick={() => setLanguage("pt")}>PT</button><span>/</span><button className={language === "en" ? "active" : ""} aria-pressed={language === "en"} onClick={() => setLanguage("en")}>EN</button></div>;
}

function PublicNav({ language, setLanguage, copy, onAssistant }: { language: Language; setLanguage: (language: Language) => void; copy: PublicCopy; onAssistant?: () => void }) {
  return <header className="public-nav"><div className="public-container public-nav-inner"><a href="#top" aria-label="NEGOBOT-MOZ home"><Brand /></a><nav className="public-nav-links" aria-label="Main navigation"><a href="#capacidades">{copy.nav.capabilities}</a><a href="#planos">{copy.nav.plans}</a><a href="#como-funciona">{copy.nav.how}</a><a href="#contacto">{copy.nav.contact}</a></nav><div className="public-nav-actions"><LanguageSwitcher language={language} setLanguage={setLanguage} label={copy.nav.language} /><button className="public-nav-cta" onClick={onAssistant || (() => { window.location.href = "/assistente"; })}>{copy.nav.assistant} <ArrowUpRight size={15} /></button></div></div></header>;
}

export function PublicSite() {
  const { language, setLanguage, copy } = useLanguage();
  const [assistantOpen, setAssistantOpen] = useState(false);
  return <div className="public-site" id="top"><PublicNav language={language} setLanguage={setLanguage} copy={copy} onAssistant={() => setAssistantOpen(true)} /><main>
    <section className="public-hero"><div className="public-hero-glow" /><div className="public-container public-hero-grid"><div className="public-hero-copy"><p className="public-eyebrow">{copy.hero.eyebrow}</p><h1>{copy.hero.titleA}<br /><em>{copy.hero.titleB}</em></h1><p className="public-lead">{copy.hero.lead}</p><div className="public-actions"><a className="public-button public-button-primary" href="/falar-whatsapp">{copy.hero.whatsapp} <ArrowUpRight size={17} /></a><button className="public-button public-button-ghost" onClick={() => setAssistantOpen(true)}>{copy.hero.platform} <MessageCircle size={17} /></button></div><p className="public-note"><span className="public-live-dot" /> {copy.hero.note}</p></div><div className="public-signal-card" aria-label="NEGOBOT-MOZ conversation example"><div className="public-card-top"><span>{copy.hero.signal}</span><span className="public-live">{copy.hero.online}</span></div><div className="public-chat-window"><div className="public-bubble">{copy.hero.bubble1}<small>10:42</small></div><div className="public-bubble public-bubble-bot">{copy.hero.bubble2}<small>{copy.hero.bubble2Meta}</small></div><div className="public-bubble">{copy.hero.bubble3}<small>10:43</small></div><div className="public-bubble public-bubble-bot">{copy.hero.bubble4}<small>{copy.hero.bubble4Meta}</small></div></div><div className="public-float-label"><span><CheckCircle2 size={16} /></span>{copy.hero.float}</div></div></div></section>
    <section className="public-trust" aria-label="Integrations"><div className="public-container public-trust-inner"><span>{copy.trust}</span><div><b>WHATSAPP</b><b>GROQ AI</b><b>EVOLUTION API</b><b>FIREBASE</b></div></div></section>
    <section className="public-section" id="capacidades"><div className="public-container"><div className="public-section-head"><h2>{copy.capabilities.title}</h2><p>{copy.capabilities.text}</p></div><div className="public-feature-grid">{copy.features.map(({ number, kicker, title, text, icon: Icon }) => <article className="public-feature" key={number}><span className="public-feature-number">{number} / {kicker}</span><div className="public-feature-icon"><Icon size={20} /></div><h3>{title}</h3><p>{text}</p></article>)}</div></div></section>
    <section className="public-section public-plans-section" id="planos"><div className="public-container"><div className="public-section-head"><h2>{copy.plansIntro.title}</h2><p>{copy.plansIntro.text}</p></div><div className="public-plans-grid">{copy.plans.map((plan) => <article className={`public-plan ${plan.id === "premium" ? "public-plan-featured" : ""}`} key={plan.id}><p className="public-plan-label">{plan.label}</p><h3>{plan.name}</h3><p className="public-plan-description">{plan.description}</p><div className="public-price">{plan.price}<small>{plan.month}</small></div><ul>{plan.benefits.map((benefit) => <li key={benefit}><Check size={15} />{benefit}</li>)}</ul><button className={`public-button ${plan.id === "premium" ? "public-button-primary" : "public-button-light"}`} onClick={() => setAssistantOpen(true)}>{copy.choose} {plan.name.replace(language === "pt" ? "Plano " : " Plan", "")} <ChevronRight size={16} /></button></article>)}</div></div></section>
    <section className="public-section public-dark-section" id="como-funciona"><div className="public-container public-workflow"><div><p className="public-eyebrow">{copy.workflow.eyebrow}</p><h2>{copy.workflow.titleA}<br />{copy.workflow.titleB}</h2><p className="public-workflow-copy">{copy.workflow.text}</p><div className="public-channel-row"><span><MessageCircle size={16} /> WhatsApp</span><span><Mic size={16} /> {language === "pt" ? "Áudio" : "Audio"}</span><span><FileText size={16} /> {language === "pt" ? "Documentos" : "Documents"}</span></div></div><div className="public-steps">{copy.workflow.steps.map((step) => <article className="public-step" key={step.num}><span>{step.num}</span><div><h3>{step.title}</h3><p>{step.text}</p></div></article>)}</div></div></section>
    <section className="public-cta" id="contacto"><div className="public-container public-cta-inner"><div><p className="public-eyebrow public-eyebrow-dark">{copy.cta.eyebrow}</p><h2>{copy.cta.title}</h2><p>{copy.cta.text}</p></div><div className="public-actions"><a className="public-button public-button-dark" href="/falar-whatsapp">{copy.cta.whatsapp} <ArrowUpRight size={17} /></a><button className="public-button public-button-outline-dark" onClick={() => setAssistantOpen(true)}>{copy.cta.platform} <MessageCircle size={17} /></button></div></div></section>
  </main><footer className="public-footer"><div className="public-container public-footer-inner"><a href="#top"><Brand dark /></a><span>{copy.footer}</span><span>© 2026 NEGOBOT-MOZ</span><div className="public-socials" aria-label="Social networks"><span>IG</span><span>in</span></div></div></footer>{assistantOpen && <PublicAssistantDialog language={language} copy={copy} onClose={() => setAssistantOpen(false)} />}</div>;
}

function PublicAssistantDialog({ language, copy, onClose }: { language: Language; copy: PublicCopy; onClose: () => void }) {
  const [message, setMessage] = useState(""); const [messages, setMessages] = useState<ChatMessage[]>([{ role: "assistant", content: copy.assistant.welcome }]); const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  async function submit(event: FormEvent) { event.preventDefault(); const value = message.trim(); if (!value || busy) return; setMessage(""); setError(""); setMessages((current) => [...current, { role: "user", content: value }]); setBusy(true); try { const response = await fetch("/api/platform/public/assistant/chat", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message: value, source: "platform", language }) }); const data = await response.json(); if (!response.ok) throw new Error(data.error || copy.assistant.error); setMessages((current) => [...current, { role: "assistant", content: data.answer || copy.assistant.fallback }]); } catch (reason) { setError(reason instanceof Error ? reason.message : copy.assistant.error); } finally { setBusy(false); } }
  return <div className="public-modal-backdrop" role="dialog" aria-modal="true" aria-label={copy.assistant.eyebrow}><section className="public-assistant-modal"><div className="public-assistant-head"><div><span className="public-eyebrow">{copy.assistant.eyebrow}</span><h2>{copy.assistant.title}</h2></div><button className="public-close" onClick={onClose} aria-label={copy.assistant.close}><X size={19} /></button></div><div className="public-assistant-messages">{messages.map((item, index) => <div className={`public-assistant-message ${item.role}`} key={`${item.role}-${index}`}>{item.content}</div>)}{busy && <div className="public-assistant-message assistant public-typing"><span /><span /><span /></div>}</div>{error && <p className="public-assistant-error">{error}</p>}<form className="public-assistant-form" onSubmit={submit}><input value={message} onChange={(event) => setMessage(event.target.value)} placeholder={copy.assistant.placeholder} aria-label={copy.assistant.placeholder} maxLength={1200} /><button type="submit" disabled={busy || !message.trim()} aria-label={copy.assistant.send}><Send size={17} /></button></form><a className="public-assistant-whatsapp" href="/falar-whatsapp"><MessageCircle size={16} /> {copy.assistant.whatsapp}</a></section></div>;
}

export function PublicAssistantPage() {
  const { language, setLanguage, copy } = useLanguage();
  return <div className="public-site public-assistant-page"><PublicNav language={language} setLanguage={setLanguage} copy={copy} /><main className="public-assistant-page-main"><div className="public-container public-assistant-page-grid"><div><p className="public-eyebrow">{copy.assistant.pageEyebrow}</p><h1>{copy.assistant.pageTitle}</h1><p className="public-lead public-lead-light">{copy.assistant.pageLead}</p><div className="public-actions"><a className="public-button public-button-primary" href="/falar-whatsapp">{copy.cta.whatsapp} <ArrowUpRight size={17} /></a><a className="public-button public-button-ghost" href="/#planos">{copy.assistant.viewPlans} <ChevronRight size={17} /></a></div></div><PublicAssistantDialog language={language} copy={copy} onClose={() => { window.location.href = "/"; }} /></div></main></div>;
}
