import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { AlertCircle, BarChart3, Bot, Building2, CheckCircle2, CircleDollarSign, FileUp, LifeBuoy, Loader2, MessageCircle, Pause, Play, Plus, QrCode, RefreshCw, Send, Smartphone, Users, Video, XCircle } from "lucide-react";
import { api, type AssistantSettings, type Campaign, type CampaignTemplate, type ClientPlan, type Contact, type Conversation, type DeliveryMetrics, type IntegrationStatus, type LemonSqueezyStatus, type PaymentRecord, type Plan, type PlanAddon, type SupportTicket, type TeamMember, type TenantMetrics, type VideoJob } from "../lib/api";

function ModuleHeader({ eyebrow, title, description, action }: { eyebrow: string; title: string; description: string; action?: ReactNode }) {
  return <div className="module-header"><div><span className="eyebrow">{eyebrow}</span><h1>{title}</h1><p>{description}</p></div>{action}</div>;
}
function LoadingBox() { return <div className="loading-box"><Loader2 size={18} className="spin" /> A carregar informação...</div>; }
function ErrorBox({ message }: { message: string }) { return <div className="alert error"><XCircle size={16} />{message}</div>; }
function SuccessBox({ message }: { message: string }) { return <div className="alert success"><CheckCircle2 size={16} />{message}</div>; }

export function ConversationsPage() {
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [search, setSearch] = useState("");
  const [tag, setTag] = useState("");
  const [busy, setBusy] = useState(true);
  const [saving, setSaving] = useState(false);
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function load(filters: { search?: string; tag?: string } = {}) {
    setBusy(true); setError("");
    try {
      const [contactResult, conversationResult] = await Promise.all([api.client.contacts({ search: filters.search ?? search, tag: filters.tag ?? tag }), api.client.conversations()]);
      setContacts(contactResult.contacts || []); setConversations(conversationResult.conversations || []);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível carregar as conversas."); }
    finally { setBusy(false); }
  }
  useEffect(() => { void load(); }, []);

  async function addContact(event: FormEvent) {
    event.preventDefault(); setSaving(true); setError(""); setNotice("");
    try { await api.client.createContact(name, phone); setName(""); setPhone(""); setNotice("Contacto guardado com sucesso."); await load(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível guardar o contacto."); }
    finally { setSaving(false); }
  }
  async function importFile(file?: File) {
    if (!file) return;
    setImporting(true); setError(""); setNotice("");
    try { const result = await api.client.importContacts(file); setNotice(`${result.imported} contactos importados; ${result.skipped} ignorados.`); await load(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível importar o ficheiro."); }
    finally { setImporting(false); }
  }
  async function handoff(item: Conversation, mode: "bot" | "humano") {
    if (!item.phone) return;
    try { await api.client.handoff(item.phone, mode); setNotice(`Atendimento de ${item.phone} entregue ao ${mode}.`); await load(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível alterar o atendimento."); }
  }

  return <div className="content-stack"><ModuleHeader eyebrow="CONTACTOS E CONVERSAS" title="Central de conversas" description="Mantém os teus contactos organizados e acompanha as interações do assistente." action={<button className="secondary-button compact" onClick={() => void load()}><RefreshCw size={16} /> Atualizar</button>} />
    {error && <ErrorBox message={error} />}{notice && <SuccessBox message={notice} />}
    <div className="module-grid two"><section className="data-panel"><div className="panel-heading"><div><span className="eyebrow">CONTACTOS</span><h3>{contacts.length} contactos</h3></div><Users size={19} /></div><form className="filter-row" onSubmit={(event) => { event.preventDefault(); void load({ search, tag }); }}><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Pesquisar nome ou telefone" /><input value={tag} onChange={(event) => setTag(event.target.value)} placeholder="Etiqueta" /><button className="secondary-button compact" type="submit">Filtrar</button></form>{busy ? <LoadingBox /> : contacts.length ? <div className="data-list">{contacts.slice(0, 100).map((contact) => <div className="data-row" key={contact.id}><div className="avatar">{contact.name.slice(0, 1).toUpperCase()}</div><div className="row-main"><strong>{contact.name}</strong><small>{contact.phone}{contact.tags?.length ? ` · ${contact.tags.join(", ")}` : ""}</small></div><span className="tag">{contact.opt_in === false ? "Sem opt-in" : "Opt-in"}</span></div>)}</div> : <div className="empty-state">Ainda não existem contactos.</div>}</section>
      <section className="data-panel" id="new-contact"><div className="panel-heading"><div><span className="eyebrow">ADICIONAR</span><h3>Novo contacto</h3></div><Plus size={19} /></div><form className="stack-form compact-form" onSubmit={addContact}><label>Nome<input value={name} onChange={(event) => setName(event.target.value)} placeholder="Nome do contacto" required /></label><label>WhatsApp<input value={phone} onChange={(event) => setPhone(event.target.value)} placeholder="2588..." required /></label><button className="primary-button" disabled={saving} type="submit">{saving ? "A guardar..." : "Guardar contacto"}</button></form><label className="upload-field"><span><FileUp size={16} /> Importar CSV ou XLSX</span><input type="file" accept=".csv,.xlsx" disabled={importing} onChange={(event) => { void importFile(event.target.files?.[0]); event.currentTarget.value = ""; }} />{importing && <small>A importar contactos...</small>}</label></section></div>
    <section className="data-panel"><div className="panel-heading"><div><span className="eyebrow">ATIVIDADE</span><h3>Conversas recentes</h3></div><MessageCircle size={19} /></div>{conversations.length ? <div className="data-list">{conversations.map((conversation) => <div className="data-row" key={conversation.id || conversation.phone}><div className="quick-icon"><MessageCircle size={17} /></div><div className="row-main"><strong>{conversation.name || conversation.phone || "Contacto"}</strong><small>{conversation.last_message || "Sem mensagem recente"}</small></div><span className="tag">{conversation.status_atendimento || conversation.status || "bot"}</span><div className="row-actions"><button title="Entregar ao bot" onClick={() => void handoff(conversation, "bot")}><Bot size={14} /></button><button title="Entregar a humano" onClick={() => void handoff(conversation, "humano")}><Users size={14} /></button></div></div>)}</div> : <div className="empty-state">As conversas recebidas pelo webhook aparecerão aqui.</div>}</section>
  </div>;
}

export function CampaignsPage() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [templates, setTemplates] = useState<CampaignTemplate[]>([]);
  const [name, setName] = useState(""); const [message, setMessage] = useState(""); const [templateId, setTemplateId] = useState(""); const [segmentTags, setSegmentTags] = useState("");
  const [channels, setChannels] = useState<string[]>(["whatsapp"]); const [language, setLanguage] = useState("pt-MZ"); const [tone, setTone] = useState("profissional"); const [offer, setOffer] = useState(""); const [scheduledAt, setScheduledAt] = useState("");
  const [busy, setBusy] = useState(true); const [saving, setSaving] = useState(false); const [error, setError] = useState(""); const [notice, setNotice] = useState("");
  const channelOptions = [{ id: "whatsapp", label: "WhatsApp" }, { id: "facebook", label: "Facebook" }, { id: "instagram", label: "Instagram" }, { id: "tiktok", label: "TikTok" }, { id: "x", label: "X" }, { id: "linkedin", label: "LinkedIn" }, { id: "telegram", label: "Telegram" }, { id: "email", label: "E-mail" }];
  async function load() { setBusy(true); try { const [campaignResult, templateResult] = await Promise.all([api.client.campaigns(), api.client.templates()]); setCampaigns(campaignResult.campaigns || []); setTemplates(templateResult.templates || []); } catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível carregar campanhas."); } finally { setBusy(false); } }
  useEffect(() => { void load(); }, []);
  async function create(event: FormEvent) { event.preventDefault(); setSaving(true); setError(""); setNotice(""); try { const tags = segmentTags.split(",").map((item) => item.trim()).filter(Boolean); await api.client.createCampaign(name, message, { ...(templateId ? { template_id: templateId } : {}), ...(tags.length ? { tags } : {}), channels, language, tone, offer, ...(scheduledAt ? { scheduled_at: scheduledAt } : {}) }); setName(""); setMessage(""); setTemplateId(""); setSegmentTags(""); setChannels(["whatsapp"]); setOffer(""); setScheduledAt(""); setNotice("Campanha omnichannel colocada na fila persistente."); await load(); } catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível criar a campanha."); } finally { setSaving(false); } }
  async function action(id: string, value: "pause" | "resume" | "cancel") { try { await api.client.campaignAction(id, value); await load(); } catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível atualizar a campanha."); } }
  return <div className="content-stack"><ModuleHeader eyebrow="CAMPANHAS OMNICHANNEL" title="Uma mensagem, vários canais" description="Cria a oferta uma vez e encaminha-a para os canais autorizados pelo teu tenant." action={<div className="live-pill"><span className="status-dot" /> Redis + n8n</div>} />{error && <ErrorBox message={error} />}{notice && <SuccessBox message={notice} />}<div className="module-grid two"><section className="data-panel"><div className="panel-heading"><div><span className="eyebrow">NOVA CAMPANHA</span><h3>Preparar conteúdo</h3></div><Send size={19} /></div><form className="stack-form compact-form" onSubmit={create}><label>Nome da campanha<input value={name} onChange={(event) => setName(event.target.value)} placeholder="Promoção de agosto" required /></label><label>Canais de publicação<div className="channel-grid">{channelOptions.map((channel) => <label className="check-card" key={channel.id}><input type="checkbox" checked={channels.includes(channel.id)} onChange={() => setChannels((current) => current.includes(channel.id) ? current.filter((item) => item !== channel.id) : [...current, channel.id])} />{channel.label}</label>)}</div></label><label>Template opcional<select value={templateId} onChange={(event) => { const value = event.target.value; setTemplateId(value); const selected = templates.find((item) => item.id === value); if (selected) setMessage(selected.body); }}><option value="">Escrever mensagem</option>{templates.filter((item) => item.status !== "archived").map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label>Mensagem<textarea value={message} onChange={(event) => setMessage(event.target.value)} placeholder="Escreve a mensagem base ou seleciona um template" rows={5} required={!templateId} /></label><label>Oferta ou produto<small className="muted">Opcional; o n8n pode adaptar o conteúdo por canal.</small><input value={offer} onChange={(event) => setOffer(event.target.value)} placeholder="Ex.: Plano Premium por 1.500 MT" /></label><div className="form-grid-two"><label>Idioma<select value={language} onChange={(event) => setLanguage(event.target.value)}><option value="pt-MZ">Português de Moçambique</option><option value="en">English</option></select></label><label>Tom<select value={tone} onChange={(event) => setTone(event.target.value)}><option value="profissional">Profissional</option><option value="direto">Direto</option><option value="amigável">Amigável</option><option value="promocional">Promocional</option></select></label></div><label>Agendar<small className="muted">Opcional; usa o fuso horário configurado no servidor.</small><input type="datetime-local" value={scheduledAt} onChange={(event) => setScheduledAt(event.target.value)} /></label><label>Etiquetas do segmento<small className="muted">Separadas por vírgulas; vazio envia para todos com opt-in.</small><input value={segmentTags} onChange={(event) => setSegmentTags(event.target.value)} placeholder="vip, cliente" /></label><button className="primary-button" disabled={saving || channels.length === 0} type="submit">{saving ? "A preparar..." : "Colocar na fila omnichannel"}</button></form></section><section className="data-panel"><div className="panel-heading"><div><span className="eyebrow">HISTÓRICO</span><h3>{campaigns.length} campanhas</h3></div><ActivityIcon /></div>{busy ? <LoadingBox /> : campaigns.length ? <div className="data-list">{campaigns.map((campaign) => <div className="data-row" key={campaign.id}><div className="quick-icon"><Send size={16} /></div><div className="row-main"><strong>{campaign.name}</strong><small>{(campaign.channels || ["whatsapp"]).join(", ")} · {campaign.total || 0} destinatários · {campaign.sent || 0} enviados</small></div><span className={`status-badge ${campaign.status || "queued"}`}>{campaign.status || "queued"}</span><div className="row-actions">{campaign.status === "paused" ? <button title="Retomar" onClick={() => void action(campaign.id, "resume")}><Play size={14} /></button> : <button title="Pausar" onClick={() => void action(campaign.id, "pause")}><Pause size={14} /></button>}<button title="Cancelar" onClick={() => void action(campaign.id, "cancel")}><XCircle size={14} /></button></div></div>)}</div> : <div className="empty-state">Ainda não criaste nenhuma campanha.</div>}</section></div></div>;
}
function ActivityIcon() { return <Send size={19} />; }

export function BillingPage() {
  const [plan, setPlan] = useState<ClientPlan | null>(null);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [addons, setAddons] = useState<PlanAddon[]>([]);
  const [payments, setPayments] = useState<PaymentRecord[]>([]);
  const [lemonStatus, setLemonStatus] = useState<LemonSqueezyStatus | null>(null);
  const [mpesaNumber, setMpesaNumber] = useState("855000929");
  const [mpesaName, setMpesaName] = useState("Abel Francisco");
  const [messageText, setMessageText] = useState("");
  const [clientPhone, setClientPhone] = useState("");
  const [busy, setBusy] = useState(true);
  const [verifying, setVerifying] = useState(false);
  const [checkoutPlan, setCheckoutPlan] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [qrCode, setQrCode] = useState<string | null>(null);
  const [qrState, setQrState] = useState("");

  async function load() {
    setBusy(true);
    setError("");
    try {
      const [current, catalog, history, online] = await Promise.all([api.client.plan(), api.client.plans(), api.client.paymentHistory(), api.client.lemonSqueezyStatus()]);
      setPlan(current); setPlans(catalog.plans || []); setAddons(catalog.addons || []); setPayments(history.payments || []); setLemonStatus(online);
      if (catalog.mpesa_number) setMpesaNumber(catalog.mpesa_number);
      if (catalog.mpesa_name) setMpesaName(catalog.mpesa_name);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível carregar os planos."); }
    finally { setBusy(false); }
  }

  useEffect(() => { void load(); }, []);

  const trialStatus = plan?.trial_status || plan?.status || "demonstracao";
  const isInternational = plan?.billing_region === "international";
    const trialMessage = trialStatus === "trial_pending_connection" ? "A demonstração ainda não começou: liga o WhatsApp para iniciar os 2 dias." : trialStatus === "trial_active" ? "Demonstração activa: tens 2 dias desde a ligação do WhatsApp." : trialStatus === "trial_expired" ? "Demonstração terminada: escolhe um plano e confirma o pagamento para voltar a ligar o WhatsApp." : plan?.status === "ativo" ? "Plano activo e pronto para operar." : "A aguardar activação.";
  const limits = plan?.limits || {};
  const contactLimit = typeof limits.contact_limit === "number" ? limits.contact_limit : 0;
  const campaignLimit = typeof limits.campaigns_per_month === "number" ? limits.campaigns_per_month : 0;
  const teamLimit = typeof limits.team_seats === "number" ? limits.team_seats : 0;

  async function verify(event: FormEvent) {
    event.preventDefault(); setVerifying(true); setError(""); setNotice("");
    try { const result = await api.client.verifyPayment(messageText, clientPhone); setNotice(result.response); setQrCode(result.qrcode || null); setQrState(result.state || ""); setMessageText(""); await load(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível validar o pagamento."); }
    finally { setVerifying(false); }
  }

  async function checkout(planId: string) {
    setCheckoutPlan(planId); setError(""); setNotice("");
    try { const result = await api.client.createLemonSqueezyCheckout(planId); window.location.assign(result.checkout_url); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível abrir o checkout online."); setCheckoutPlan(""); }
  }

  return <div className="content-stack">
    <ModuleHeader eyebrow="PLANO E PAGAMENTOS" title="Escolhe o teu próximo nível" description="Consulta os benefícios, paga por M-Pesa ou abre um checkout online seguro." />
    {error && <ErrorBox message={error} />}{notice && <SuccessBox message={notice} />}
    <section className="current-plan"><div><span className="eyebrow">PLANO ATUAL</span><h3>{plan?.plan_name || "Demonstração"}</h3><p>{trialMessage}{plan?.expires_at ? ` · expira em ${plan.expires_at}` : ""}</p></div><div className="plan-status"><CircleDollarSign size={20} />{plan?.mass_broadcast ? "Disparos ativos" : trialStatus === "trial_active" ? "Trial activo" : trialStatus === "trial_expired" ? "Pagamento necessário" : "Trial pendente"}</div>    </section>
    <section className="data-panel"><div className="panel-heading"><div><span className="eyebrow">USO DO PLANO</span><h3>Limites e consumo actual</h3></div><BarChart3 size={19} /></div><div className="stat-grid"><div className="stat-card"><span>Contactos</span><strong>{plan?.usage?.contacts ?? 0}{contactLimit ? ` / ${contactLimit}` : ""}</strong></div><div className="stat-card"><span>Campanhas este mês</span><strong>{plan?.usage?.campaigns_this_month ?? 0}{campaignLimit ? ` / ${campaignLimit}` : ""}</strong></div><div className="stat-card"><span>Lugares da equipa</span><strong>{plan?.usage?.team_seats ?? 0}{teamLimit ? ` / ${teamLimit}` : ""}</strong></div></div><p className="muted">Os canais adicionais dependem do plano, da autorização do fornecedor e da configuração do tenant.</p></section>
    {isInternational && <section className="payment-instruction"><div className="quick-icon"><CircleDollarSign size={20} /></div><div><strong>Pagamento internacional com Lemon Squeezy</strong><p>Usa cartão, PayPal ou outro método apresentado no checkout. A subscrição só activa o plano depois da confirmação segura do webhook.</p></div></section>}
    {!isInternational && <><section className="payment-instruction"><div className="quick-icon"><Smartphone size={20} /></div><div><strong>Pagamento local por M-Pesa</strong><p>Transfere para <b>{mpesaNumber}</b>, em nome de <b>{mpesaName}</b>. Depois cola abaixo o SMS completo ou o ID da transacção. O AutoPay compara a transacção recebida antes de activar o plano.</p></div></section>
    <section className="data-panel"><div className="panel-heading"><div><span className="eyebrow">VALIDAÇÃO AUTOPAY</span><h3>Enviar comprovativo</h3></div><CheckCircle2 size={19} /></div><form className="stack-form compact-form" onSubmit={verify}><label>Número que fez a transferência<input value={clientPhone} onChange={(event) => setClientPhone(event.target.value)} placeholder="2588..." required /></label><label>SMS ou ID da transferência<textarea value={messageText} onChange={(event) => setMessageText(event.target.value)} placeholder="Cole aqui o SMS recebido do M-Pesa" rows={4} required /></label><button className="primary-button" disabled={verifying} type="submit">{verifying ? "A validar..." : "Validar pagamento"}</button></form></section></>}
    {(qrCode || qrState === "pending") && <section className="data-panel qr-panel"><div className="panel-heading"><div><span className="eyebrow">PRÓXIMO PASSO</span><h3>{qrCode ? "Liga o WhatsApp" : "QR Code em preparação"}</h3></div><QrCode size={19} /></div>{qrCode ? <><p>Pagamento confirmado. Abre o WhatsApp que vais automatizar, entra em <b>Aparelhos conectados</b> e lê este código.</p><img className="qr-image" src={qrCode} alt="QR Code para ligar o WhatsApp" /></> : <div className="empty-state">O pagamento foi confirmado. A instância está a preparar o QR Code; atualiza esta página ou usa o botão Gerar QR Code na área WhatsApp.</div>}</section>}
    <section className="data-panel"><div className="panel-heading"><div><span className="eyebrow">HISTÓRICO DE PAGAMENTOS</span><h3>{payments.length} registos</h3></div><RefreshCw size={19} /></div>{payments.length ? <div className="data-list">{payments.map((payment) => <div className="data-row" key={payment.id}><div className="quick-icon"><CircleDollarSign size={16} /></div><div className="row-main"><strong>{payment.provider === "lemonsqueezy" ? `Lemon Squeezy · ${payment.plan_name || payment.plan_id || "checkout"}` : (payment.transaction_id || "Código ainda não identificado")}</strong><small>{payment.client_phone || payment.payment_provider || "Pagamento online"} · {payment.created_at ? new Date(payment.created_at).toLocaleString("pt-PT") : "agora"}</small></div><span className={`status-badge ${payment.status || "pending"}`}>{payment.status || "pendente"}</span></div>)}</div> : <div className="empty-state">Os registos de pagamento aparecerão aqui.</div>}</section>
    <section className="plan-grid">{busy ? <LoadingBox /> : plans.map((item) => <article className={`plan-card ${item.id === plan?.plan ? "selected" : ""}`} key={item.id}><span className="eyebrow">{item.name}</span><strong>{item.price_mt} MT</strong><small>{item.validity_days} dias · {item.team_seats || 1} lugar(es) · {item.campaigns_per_month || 0} campanhas/mês</small><div className="benefits">{item.benefits.map((benefit) => <span key={benefit}><CheckIcon />{benefit}</span>)}</div>{!isInternational && <button className="secondary-button" type="button" onClick={() => setNotice(item.id === plan?.plan ? "Este é o teu plano actual." : `Plano ${item.name} seleccionado. Faz a transferência de ${item.price_mt} MT e envia o SMS acima.`)}>{item.id === plan?.plan ? "Plano actual" : "Escolher por M-Pesa"}</button>}{isInternational && lemonStatus?.configured && lemonStatus.plans[item.id] && <button className="primary-button" type="button" disabled={checkoutPlan === item.id} onClick={() => void checkout(item.id)}>{checkoutPlan === item.id ? "A abrir checkout..." : "Pagar online"}</button>}</article>)}</section>
    {addons.length > 0 && <section className="data-panel"><div className="panel-heading"><div><span className="eyebrow">EXTRAS</span><h3>Adapta o teu plano</h3></div><Plus size={19} /></div><div className="data-list">{addons.map((addon) => <div className="data-row" key={addon.name}><div className="quick-icon"><Plus size={16} /></div><div className="row-main"><strong>{addon.name}</strong><small>{addon.description}</small></div><span className="tag">+{addon.price_mt} MT/mês</span><button className="secondary-button compact" type="button" onClick={() => setNotice(`O extra ${addon.name} será activado após confirmação comercial.`)}>Falar com especialista</button></div>)}</div></section>}
  </div>;
}
function CheckIcon() { return <span className="check-icon">✓</span>; }

export function WhatsAppPage() {
  const [status, setStatus] = useState<IntegrationStatus | null>(null); const [phone, setPhone] = useState(""); const [qr, setQr] = useState<string | null>(null); const [busy, setBusy] = useState(true); const [generating, setGenerating] = useState(false); const [error, setError] = useState("");
  async function load() { setBusy(true); try { setStatus(await api.client.integrationStatus()); } catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível consultar a Evolution API."); } finally { setBusy(false); } }
  useEffect(() => { void load(); }, []);
  async function generate(event: FormEvent) { event.preventDefault(); setGenerating(true); setError(""); setQr(null); try { const result = await api.client.evolutionQr(phone); setQr(result.qrcode || null); setStatus({ instance_name: result.instance_name, state: result.state, configured: true }); if (!result.qrcode && result.state === "open") setError("Este WhatsApp já está ligado; não é necessário ler um novo QR Code."); } catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível gerar o QR Code."); } finally { setGenerating(false); } }
  return <div className="content-stack"><ModuleHeader eyebrow="INTEGRAÇÃO WHATSAPP" title="Liga o teu número" description="Prepara a instância Evolution API e lê o QR Code com o WhatsApp que será automatizado." action={<button className="secondary-button compact" onClick={() => void load()}><RefreshCw size={16} /> Atualizar estado</button>} />{error && <ErrorBox message={error} />}<div className="module-grid two"><section className="data-panel"><div className="panel-heading"><div><span className="eyebrow">ESTADO DA INSTÂNCIA</span><h3>{busy ? "A consultar..." : status?.state || "não configurada"}</h3></div><Smartphone size={20} /></div><div className="health-list"><div className="health-item"><span className="status-dot" /><div className="row-main"><strong>Evolution API</strong><small>{status?.configured ? "Configurada" : "A aguardar configuração"}</small></div></div><div className="health-item"><span className="status-dot" /><div className="row-main"><strong>Instância</strong><small>{status?.instance_name || "Será criada com o número"}</small></div></div></div><form className="stack-form compact-form" onSubmit={generate}><label>Número de WhatsApp<input value={phone} onChange={(event) => setPhone(event.target.value)} placeholder="2588..." required /></label><button className="primary-button" disabled={generating} type="submit">{generating ? "A preparar QR Code..." : "Gerar QR Code"}</button></form></section><section className="data-panel qr-panel"><div className="panel-heading"><div><span className="eyebrow">LIGAÇÃO SEGURA</span><h3>{qr ? "Lê o código com o WhatsApp" : "QR Code"}</h3></div><QrCode size={20} /></div>{qr ? <img className="qr-image" src={qr} alt="QR Code para ligar o WhatsApp" /> : <div className="empty-state">Depois de gerar o código, ele aparecerá aqui. Mantém o WhatsApp aberto em Dispositivos associados.</div>}</section></div></div>;
}

export function AssistantPage() {
  const [settings, setSettings] = useState<AssistantSettings>({ diretrizes_corporativas: "", base_conhecimento_documentos: "", timeout_humano_minutos: 15 }); const [busy, setBusy] = useState(true); const [saving, setSaving] = useState(false); const [error, setError] = useState(""); const [notice, setNotice] = useState("");
  useEffect(() => { api.client.assistant().then(setSettings).catch((reason) => setError(reason instanceof Error ? reason.message : "Não foi possível carregar o assistente.")).finally(() => setBusy(false)); }, []);
  async function save(event: FormEvent) { event.preventDefault(); setSaving(true); setError(""); setNotice(""); try { await api.client.updateAssistant(settings); setNotice("Configuração do assistente guardada."); } catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível guardar a configuração."); } finally { setSaving(false); } }
  if (busy) return <div className="content-stack"><LoadingBox /></div>;
  return <div className="content-stack"><ModuleHeader eyebrow="ASSISTENTE NEGOBOT" title="Configura o teu assistente" description="Define as regras de atendimento, a base de conhecimento e quando uma conversa passa para uma pessoa." />{error && <ErrorBox message={error} />}{notice && <SuccessBox message={notice} />}<form className="data-panel stack-form" onSubmit={save}><div className="panel-heading"><div><span className="eyebrow">PERSONALIDADE E REGRAS</span><h3>Diretrizes corporativas</h3></div><Bot size={20} /></div><textarea rows={7} value={settings.diretrizes_corporativas} onChange={(event) => setSettings({ ...settings, diretrizes_corporativas: event.target.value })} placeholder="Ex.: responde em Português de Moçambique, apresenta preços reais e encaminha pagamentos para validação AutoPay." /><label>Base de conhecimento<textarea rows={8} value={settings.base_conhecimento_documentos} onChange={(event) => setSettings({ ...settings, base_conhecimento_documentos: event.target.value })} placeholder="Produtos, horários, localização, perguntas frequentes e informação que o bot deve conhecer." /></label><label>Timeout para atendimento humano (minutos)<input type="number" min={1} max={240} value={settings.timeout_humano_minutos} onChange={(event) => setSettings({ ...settings, timeout_humano_minutos: Number(event.target.value) })} /></label><small className="muted">Modelos ativos: texto {settings.models?.text || "configurado"} · visão {settings.models?.vision || "configurado"}</small><button className="primary-button" disabled={saving} type="submit">{saving ? "A guardar..." : "Guardar configuração"}</button></form></div>;
}


export function BusinessProfilePage() {
  const [profile, setProfile] = useState<import("../lib/api").BusinessProfile>({ empresa_nome: "", nicho: "", email_corporativo: "", redes_sociais: { facebook: "", instagram: "", twitter_x: "", tiktok: "", telegram: "", linkedin: "" } });
  const [busy, setBusy] = useState(true); const [saving, setSaving] = useState(false); const [error, setError] = useState(""); const [notice, setNotice] = useState("");
  useEffect(() => { api.client.profile().then(setProfile).catch((reason) => setError(reason instanceof Error ? reason.message : "Não foi possível carregar o perfil empresarial.")).finally(() => setBusy(false)); }, []);
  function changeSocial(key: keyof typeof profile.redes_sociais, value: string) { setProfile((current) => ({ ...current, redes_sociais: { ...current.redes_sociais, [key]: value } })); }
  async function save(event: FormEvent) { event.preventDefault(); setSaving(true); setError(""); setNotice(""); try { await api.client.updateProfile(profile); setNotice("Perfil empresarial e redes sociais guardados no teu tenant."); } catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível guardar o perfil."); } finally { setSaving(false); } }
  if (busy) return <div className="content-stack"><LoadingBox /></div>;
  return <div className="content-stack"><ModuleHeader eyebrow="PERFIL EMPRESARIAL" title="Empresa e redes sociais" description="Estes dados ficam associados ao email da tua conta e serão usados pelo assistente e pelas integrações omnichannel." />{error && <ErrorBox message={error} />}{notice && <SuccessBox message={notice} />}<form className="data-panel stack-form" onSubmit={save}><div className="panel-heading"><div><span className="eyebrow">IDENTIFICAÇÃO</span><h3>Dados do negócio</h3></div><Building2 size={20} /></div><label>Email da conta<input value={profile.email || ""} readOnly disabled /></label><label>Nome da empresa<input value={profile.empresa_nome} onChange={(event) => setProfile({ ...profile, empresa_nome: event.target.value })} required /></label><label>Nicho de negócio<input value={profile.nicho} onChange={(event) => setProfile({ ...profile, nicho: event.target.value })} placeholder="Ex.: comércio, restauração, imobiliária" /></label><label>Email corporativo<input type="email" value={profile.email_corporativo} onChange={(event) => setProfile({ ...profile, email_corporativo: event.target.value })} placeholder="contacto@empresa.co.mz" /></label><div className="panel-heading"><div><span className="eyebrow">CANAIS DIGITAIS</span><h3>Redes sociais e mensageria</h3></div></div><label>Facebook<input value={profile.redes_sociais.facebook} onChange={(event) => changeSocial("facebook", event.target.value)} placeholder="URL ou nome de utilizador" /></label><label>Instagram<input value={profile.redes_sociais.instagram} onChange={(event) => changeSocial("instagram", event.target.value)} placeholder="URL ou nome de utilizador" /></label><label>X / Twitter<input value={profile.redes_sociais.twitter_x} onChange={(event) => changeSocial("twitter_x", event.target.value)} placeholder="URL ou nome de utilizador" /></label><label>TikTok<input value={profile.redes_sociais.tiktok} onChange={(event) => changeSocial("tiktok", event.target.value)} placeholder="URL ou nome de utilizador" /></label><label>Telegram<input value={profile.redes_sociais.telegram} onChange={(event) => changeSocial("telegram", event.target.value)} placeholder="URL ou nome de utilizador" /></label><label>LinkedIn<input value={profile.redes_sociais.linkedin} onChange={(event) => changeSocial("linkedin", event.target.value)} placeholder="URL ou nome de utilizador" /></label><button className="primary-button" disabled={saving} type="submit">{saving ? "A guardar..." : "Guardar perfil empresarial"}</button></form></div>;
}


export function TeamPage() {
  const [members, setMembers] = useState<TeamMember[]>([]);
  const [currentRole, setCurrentRole] = useState("");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function load() {
    setBusy(true);
    setError("");
    try {
      const result = await api.client.team();
      setMembers(result.users || []);
      setCurrentRole(result.current_role || "");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Não foi possível carregar a equipa.");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => { void load(); }, []);

  async function create(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError("");
    setNotice("");
    try {
      await api.client.createOperator(name, email, password);
      setName("");
      setEmail("");
      setPassword("");
      setNotice("Operador criado. Pode iniciar sessão com as credenciais definidas.");
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Não foi possível criar o operador.");
    } finally {
      setSaving(false);
    }
  }

  async function updateMember(member: TeamMember, fields: { status?: "active" | "suspended"; tenant_role?: "operator" | "viewer" }) {
    setError("");
    setNotice("");
    try {
      await api.client.updateTeamMember(member.id, fields);
      setNotice("Permissões da equipa atualizadas.");
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Não foi possível atualizar o membro.");
    }
  }

  const canManage = currentRole === "owner";
  return <div className="content-stack">
    <ModuleHeader eyebrow="EQUIPA E PERMISSÕES" title="A tua equipa" description="Convida operadores e controla quem pode atender conversas dentro deste tenant." action={<button className="secondary-button compact" onClick={() => void load()}><RefreshCw size={16} /> Atualizar</button>} />
    {error && <ErrorBox message={error} />}
    {notice && <SuccessBox message={notice} />}
    <div className="module-grid two">
      <section className="data-panel">
        <div className="panel-heading"><div><span className="eyebrow">MEMBROS</span><h3>{members.length} utilizadores</h3></div><Users size={19} /></div>
        {busy ? <LoadingBox /> : members.length ? <div className="data-list">{members.map((member) => <div className="data-row" key={member.id}>
          <div className="avatar">{member.name.slice(0, 1).toUpperCase()}</div>
          <div className="row-main"><strong>{member.name}</strong><small>{member.email} · {member.tenant_role}</small></div>
          <span className={`status-badge ${member.status}`}>{member.status === "active" ? "ativo" : "suspenso"}</span>
          {canManage && member.tenant_role !== "owner" && <div className="row-actions"><button title={member.status === "active" ? "Suspender" : "Reativar"} onClick={() => void updateMember(member, { status: member.status === "active" ? "suspended" : "active" })}>{member.status === "active" ? <XCircle size={14} /> : <CheckCircle2 size={14} />}</button><button title={member.tenant_role === "operator" ? "Tornar visualizador" : "Tornar operador"} onClick={() => void updateMember(member, { tenant_role: member.tenant_role === "operator" ? "viewer" : "operator" })}><Users size={14} /></button></div>}
        </div>)}</div> : <div className="empty-state">Ainda não existem membros nesta equipa.</div>}
      </section>
      <section className="data-panel">
        <div className="panel-heading"><div><span className="eyebrow">CONVIDAR</span><h3>Novo operador</h3></div><Plus size={19} /></div>
        {canManage ? <form className="stack-form compact-form" onSubmit={create}><label>Nome<input value={name} onChange={(event) => setName(event.target.value)} required /></label><label>Email<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required /></label><label>Palavra-passe inicial<input type="password" minLength={8} value={password} onChange={(event) => setPassword(event.target.value)} required /></label><button className="primary-button" disabled={saving} type="submit">{saving ? "A criar..." : "Criar operador"}</button></form> : <div className="empty-state">Apenas o proprietário do tenant pode convidar ou alterar membros.</div>}
      </section>
    </div>
  </div>;
}


export function MetricsPage() {
  const [metrics, setMetrics] = useState<TenantMetrics | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");
  async function load() {
    setBusy(true); setError("");
    try { const result = await api.client.metrics(); setMetrics(result.metrics); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível carregar as métricas."); }
    finally { setBusy(false); }
  }
  useEffect(() => { void load(); }, []);
  const deliveryRate = metrics?.deliveries.delivery_rate ?? 0;
  return <div className="content-stack">
    <ModuleHeader eyebrow="MÉTRICAS E RELATÓRIOS" title="Desempenho da tua operação" description="Acompanha contactos, campanhas, entregas e conversas do teu tenant." action={<button className="secondary-button compact" onClick={() => void load()}><RefreshCw size={16} /> Atualizar</button>} />
    {error && <ErrorBox message={error} />}
    {busy ? <LoadingBox /> : metrics && <>
      <section className="stat-grid"><StatMetric label="Contactos" value={String(metrics.contacts.total)} caption={`${metrics.contacts.opt_in} com opt-in`} icon={Users} /><StatMetric label="Campanhas" value={String(metrics.campaigns.total)} caption={`${metrics.campaigns.by_status.running || 0} em execução`} icon={Send} /><StatMetric label="Conversas" value={String(metrics.conversations)} caption="Conversas registadas" icon={MessageCircle} tone="blue" /><StatMetric label="Entrega" value={`${deliveryRate}%`} caption={`${metrics.deliveries.sent} mensagens entregues`} icon={BarChart3} tone={deliveryRate >= 80 ? "green" : "amber"} /></section>
      <div className="module-grid two"><section className="data-panel"><div className="panel-heading"><div><span className="eyebrow">ENTREGAS</span><h3>Estado dos destinatários</h3></div><BarChart3 size={19} /></div><div className="data-list">{Object.entries(metrics.deliveries.by_status).map(([status, count]) => <div className="data-row" key={status}><div className="row-main"><strong>{status}</strong><small>Destinatários nesta situação</small></div><span className="status-badge active">{count}</span></div>)}</div></section><section className="data-panel"><div className="panel-heading"><div><span className="eyebrow">CAMPANHAS RECENTES</span><h3>Últimas campanhas</h3></div><Send size={19} /></div>{metrics.campaigns.recent.length ? <div className="data-list">{metrics.campaigns.recent.map((campaign) => <div className="data-row" key={campaign.id}><div className="row-main"><strong>{campaign.name}</strong><small>{campaign.total || 0} destinatários · {campaign.status || "sem estado"}</small></div><span className="status-badge">{campaign.sent || 0} enviados</span></div>)}</div> : <div className="empty-state">Ainda não existem campanhas.</div>}</section></div>
    </>}
  </div>;
}

function StatMetric({ label, value, caption, icon: Icon, tone = "green" }: { label: string; value: string; caption: string; icon: typeof BarChart3; tone?: string }) { return <article className={`stat-card ${tone}`}><div className="stat-top"><span>{label}</span><span className="icon-chip"><Icon size={17} /></span></div><strong>{value}</strong><small>{caption}</small></article>; }

export function SupportPage() {
  const [tickets, setTickets] = useState<SupportTicket[]>([]);
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");
  const [priority, setPriority] = useState<SupportTicket["priority"]>("normal");
  const [busy, setBusy] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  async function load() { setBusy(true); setError(""); try { const result = await api.client.supportTickets(); setTickets(result.tickets || []); } catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível carregar o suporte."); } finally { setBusy(false); } }
  useEffect(() => { void load(); }, []);
  async function create(event: FormEvent) { event.preventDefault(); setSaving(true); setError(""); setNotice(""); try { await api.client.createSupportTicket({ subject, message, priority }); setSubject(""); setMessage(""); setPriority("normal"); setNotice("Pedido de suporte criado. A nossa equipa irá acompanhar o ticket."); await load(); } catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível criar o ticket."); } finally { setSaving(false); } }
  return <div className="content-stack"><ModuleHeader eyebrow="SUPORTE" title="Fala com a nossa equipa" description="Cria pedidos, acompanha respostas e mantém o histórico do atendimento." action={<button className="secondary-button compact" onClick={() => void load()}><RefreshCw size={16} /> Atualizar</button>} />{error && <ErrorBox message={error} />}{notice && <SuccessBox message={notice} />}<div className="module-grid two"><section className="data-panel"><div className="panel-heading"><div><span className="eyebrow">NOVO PEDIDO</span><h3>Como podemos ajudar?</h3></div><LifeBuoy size={19} /></div><form className="stack-form compact-form" onSubmit={create}><label>Assunto<input value={subject} onChange={(event) => setSubject(event.target.value)} minLength={4} maxLength={160} required placeholder="Ex.: Não consigo ligar o WhatsApp" /></label><label>Prioridade<select value={priority} onChange={(event) => setPriority(event.target.value as SupportTicket["priority"])}><option value="low">Baixa</option><option value="normal">Normal</option><option value="high">Alta</option><option value="urgent">Urgente</option></select></label><label>Descrição<textarea value={message} onChange={(event) => setMessage(event.target.value)} minLength={10} maxLength={5000} rows={6} required placeholder="Explica o que aconteceu e inclui os detalhes relevantes." /></label><button className="primary-button" disabled={saving} type="submit">{saving ? "A enviar..." : "Criar pedido"}</button></form></section><section className="data-panel"><div className="panel-heading"><div><span className="eyebrow">HISTÓRICO</span><h3>{tickets.length} pedidos</h3></div><AlertCircle size={19} /></div>{busy ? <LoadingBox /> : tickets.length ? <div className="data-list">{tickets.map((ticket) => <div className="data-row" key={ticket.id}><div className="row-main"><strong>{ticket.subject}</strong><small>{ticket.category || "geral"} · prioridade {ticket.priority || "normal"}</small>{ticket.last_admin_reply && <small className="muted">Resposta: {ticket.last_admin_reply}</small>}</div><span className={`status-badge ${ticket.status || "open"}`}>{ticket.status || "open"}</span></div>)}</div> : <div className="empty-state">Ainda não criaste pedidos de suporte.</div>}</section></div></div>;
}


export function VideoPage() {
  const [title, setTitle] = useState("");
  const [sceneText, setSceneText] = useState("");
  const [language, setLanguage] = useState("pt-MZ");
  const [job, setJob] = useState<VideoJob | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  useEffect(() => {
    if (!job?.id || ["completed", "failed"].includes(job.status || "")) return;
    const timer = window.setInterval(() => { void api.client.videoJob(job.id).then((result) => setJob(result.job)).catch(() => undefined); }, 3500);
    return () => window.clearInterval(timer);
  }, [job?.id, job?.status]);
  async function create(event: FormEvent) {
    event.preventDefault(); setSaving(true); setError(""); setNotice("");
    const scenes = sceneText.split("\n").map((text) => text.trim()).filter(Boolean).map((text) => ({ text, duration_seconds: 3.5 }));
    if (!scenes.length) { setError("Escreve pelo menos uma cena, uma por linha."); setSaving(false); return; }
    try { const result = await api.client.createVideoJob({ title, scenes, language, subtitles: true }); setJob(result.job); setNotice("Vídeo colocado na fila. Podes sair desta página; o worker continua no servidor."); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "O motor de vídeos ainda não está disponível."); }
    finally { setSaving(false); }
  }
  return <div className="content-stack"><ModuleHeader eyebrow="VÍDEOS CURTOS" title="Cria vídeos verticais com IA" description="Transforma um roteiro em cenas 9:16 e acompanha a renderização no worker persistente." action={<div className="live-pill"><span className="status-dot" /> Fila assíncrona</div>} />{error && <ErrorBox message={error} />}{notice && <SuccessBox message={notice} />}<div className="module-grid two"><section className="data-panel"><div className="panel-heading"><div><span className="eyebrow">NOVO VÍDEO</span><h3>Roteiro por cenas</h3></div><Video size={19} /></div><form className="stack-form compact-form" onSubmit={create}><label>Título<input value={title} onChange={(event) => setTitle(event.target.value)} required minLength={2} maxLength={160} placeholder="Oferta especial de agosto" /></label><label>Idioma<select value={language} onChange={(event) => setLanguage(event.target.value)}><option value="pt-MZ">Português de Moçambique</option><option value="en">English</option></select></label><label>Cenas<small className="muted">Escreve uma cena por linha. O motor gera cartões verticais e locução quando o TTS estiver configurado.</small><textarea value={sceneText} onChange={(event) => setSceneText(event.target.value)} rows={10} required placeholder="Cena 1: Apresenta o problema do cliente\nCena 2: Mostra a solução NEGOBOT\nCena 3: Termina com uma chamada para ação" /></label><button className="primary-button" disabled={saving} type="submit">{saving ? "A colocar na fila..." : "Renderizar vídeo"}</button></form></section><section className="data-panel"><div className="panel-heading"><div><span className="eyebrow">ESTADO DO JOB</span><h3>{job?.title || "Nenhum job ativo"}</h3></div><Video size={19} /></div>{job ? <div className="content-stack"><div className="stat-card blue"><div className="stat-top"><span>Estado</span><span className="status-badge">{job.status || "queued"}</span></div><strong>{job.progress || 0}%</strong><small>Progresso da renderização</small></div>{job.error && <ErrorBox message={job.error} />}{job.status === "completed" && <div className="payment-instruction"><div className="quick-icon"><CheckCircle2 size={20} /></div><div><strong>Vídeo concluído</strong><p>O ficheiro foi renderizado pelo worker. O armazenamento e a publicação podem ser ligados ao n8n nesta fase.</p></div></div>}{job.status !== "completed" && job.status !== "failed" && <div className="loading-box"><Loader2 size={18} className="spin" /> A processar no servidor...</div>}</div> : <div className="empty-state">Cria um roteiro para iniciar a renderização.</div>}</section></div></div>;
}
