import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { AlertCircle, BarChart3, Bot, Building2, CheckCircle2, CircleDollarSign, Download, FileSpreadsheet, FileText, FileType, FileUp, Image as ImageIcon, LifeBuoy, Loader2, MessageCircle, Pause, Play, Plus, Presentation, QrCode, RefreshCw, Send, ShieldCheck, Smartphone, Sparkles, Trash2, UploadCloud, Users, Video, XCircle } from "lucide-react";
import { usePlatformLanguage } from "../lib/platformLanguage";
import { api, type AssistantKnowledgeFile, type AssistantSettings, type Campaign, type CampaignTemplate, type CampaignSettings, type ClientPlan, type ChatMessage, type Contact, type Conversation, type DeliveryMetrics, type IntegrationStatus, type LemonSqueezyStatus, type PaymentRecord, type Plan, type PlanAddon, type SupportTicket, type TeamMember, type TenantMetrics, type VideoAsset, type VideoJob, type VideoScene, type VideoVisualMode, type WhatsAppGroup } from "../lib/api";

function ModuleHeader({ eyebrow, title, description, action }: { eyebrow: string; title: string; description: string; action?: ReactNode }) {
  const { language } = usePlatformLanguage();
  const english = language === "en";
  const eyebrowMap: Record<string, string> = { "CONTACTOS E CONVERSAS": "CONTACTS & CONVERSATIONS", "PLANO E PAGAMENTOS": "PLAN & BILLING", "INTEGRAÇÃO WHATSAPP": "WHATSAPP INTEGRATION", "ASSISTENTE NEGOBOT": "NEGOBOT ASSISTANT", "PERFIL EMPRESARIAL": "BUSINESS PROFILE", "EQUIPA E PERMISSÕES": "TEAM & PERMISSIONS", "MÉTRICAS E RELATÓRIOS": "METRICS & REPORTS", "SUPORTE": "SUPPORT", "VÍDEOS CURTOS": "SHORT VIDEOS" };
  const titleMap: Record<string, string> = { "Central de conversas": "Conversation centre", "Escolhe o teu próximo nível": "Choose your next level", "Liga o teu número": "Connect your number", "Configura o teu assistente": "Configure your assistant", "Empresa e redes sociais": "Business and social networks", "A tua equipa": "Your team", "Desempenho da tua operação": "Operation performance", "Fala com a nossa equipa": "Talk to our team", "Cria vídeos verticais com IA": "Create vertical AI videos" };
  const descriptionMap: Record<string, string> = { "Mantém os teus contactos organizados e acompanha as interações do assistente.": "Keep your contacts organised and follow assistant interactions.", "Preços internacionais em USD · paga com cartão ou PayPal através do Lemon Squeezy.": "International prices in USD · pay by card or PayPal through Lemon Squeezy.", "Preços locais em MT · paga por M-Pesa e valida o comprovativo com AutoPay.": "Local prices in MT · pay by M-Pesa and validate the receipt with AutoPay.", "Prepara a instância Evolution API e lê o QR Code com o WhatsApp que será automatizado.": "Prepare the Evolution API instance and scan the QR Code with the WhatsApp you want to automate.", "Define as regras de atendimento, a base de conhecimento e quando uma conversa passa para uma pessoa.": "Define customer-care rules, knowledge and when a conversation moves to a human.", "Estes dados ficam associados ao email da tua conta e serão usados pelo assistente e pelas integrações omnichannel.": "These details are linked to your account email and used by the assistant and omnichannel integrations.", "Convida operadores e controla quem pode atender conversas dentro deste tenant.": "Invite operators and control who can handle conversations in this tenant.", "Acompanha contactos, campanhas, entregas e conversas do teu tenant.": "Monitor contacts, campaigns, deliveries and conversations in your tenant.", "Cria pedidos, acompanha respostas e mantém o histórico do atendimento.": "Create requests, follow replies and keep your support history.", "Transforma um roteiro em cenas 9:16 e acompanha a renderização no worker persistente.": "Turn a script into 9:16 scenes and follow rendering in the persistent worker." };
  return <div className="module-header"><div><span className="eyebrow">{english ? (eyebrowMap[eyebrow] || eyebrow) : eyebrow}</span><h1>{english ? (titleMap[title] || title) : title}</h1><p>{english ? (descriptionMap[description] || description) : description}</p></div>{action}</div>;
}
function LoadingBox() { return <div className="loading-box"><Loader2 size={18} className="spin" /> A carregar informação...</div>; }
function ErrorBox({ message }: { message: string }) { return <div className="alert error"><XCircle size={16} />{message}</div>; }
function SuccessBox({ message }: { message: string }) { return <div className="alert success"><CheckCircle2 size={16} />{message}</div>; }
function formatUsd(value: number) { return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(value); }
function formatPlanPrice(plan: Pick<Plan, "price_mt" | "price_usd">, international: boolean) { return international ? formatUsd(plan.price_usd ?? Math.round(plan.price_mt / 64)) : `${plan.price_mt.toLocaleString("pt-MZ")} MT`; }
function formatAddonPrice(addon: Pick<PlanAddon, "price_mt" | "price_usd">, international: boolean) { return international ? formatUsd(addon.price_usd ?? Math.round(addon.price_mt / 64)) : `${addon.price_mt.toLocaleString("pt-MZ")} MT`; }

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
  const { language: interfaceLanguage } = usePlatformLanguage();
  const english = interfaceLanguage === "en";
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [templates, setTemplates] = useState<CampaignTemplate[]>([]);
  const [name, setName] = useState("");
  const [message, setMessage] = useState("");
  const [templateId, setTemplateId] = useState("");
  const [segmentTags, setSegmentTags] = useState("");
  const [channels, setChannels] = useState<string[]>(["whatsapp"]);
  const [language, setLanguage] = useState("pt-MZ");
  const [tone, setTone] = useState("profissional");
  const [offer, setOffer] = useState("");
  const [scheduledAt, setScheduledAt] = useState("");
  const [recipientLimit, setRecipientLimit] = useState(200);
  const [consentConfirmed, setConsentConfirmed] = useState(false);
  const [includeContacts, setIncludeContacts] = useState(true);
  const [includeConversations, setIncludeConversations] = useState(false);
  const [conversationAudience, setConversationAudience] = useState<Conversation[]>([]);
  const [groups, setGroups] = useState<WhatsAppGroup[]>([]);
  const [selectedGroupJids, setSelectedGroupJids] = useState<string[]>([]);
  const [groupAuthorizationConfirmed, setGroupAuthorizationConfirmed] = useState(false);
  const [busy, setBusy] = useState(true);
  const [saving, setSaving] = useState(false);
  const [settingsSaving, setSettingsSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [campaignSettings, setCampaignSettings] = useState<CampaignSettings>({
    timezone: "Africa/Maputo",
    silence_start: "22:00",
    silence_end: "08:00",
    daily_limit: 200,
    min_delay_seconds: 5,
    max_delay_seconds: 12,
  });
  const channelOptions = [
    { id: "whatsapp", label: "WhatsApp" }, { id: "facebook", label: "Facebook" },
    { id: "instagram", label: "Instagram" }, { id: "tiktok", label: "TikTok" },
    { id: "x", label: "X" }, { id: "linkedin", label: "LinkedIn" },
    { id: "telegram", label: "Telegram" }, { id: "email", label: "E-mail" },
  ];
  const verifiedGroups = groups.filter((group) => group.admin_verified && group.bot_is_admin && group.status === "active");

  async function load() {
    setBusy(true);
    setError("");
    try {
      const [campaignResult, templateResult, groupResult, settingsResult, audienceResult] = await Promise.all([
        api.client.campaigns(), api.client.templates(), api.client.groups(), api.client.campaignSettings(), api.client.campaignConversationAudience(),
      ]);
      setCampaigns(campaignResult.campaigns || []);
      setTemplates(templateResult.templates || []);
      setGroups(groupResult.groups || []);
      setConversationAudience(audienceResult.conversations || []);
      setCampaignSettings(settingsResult);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Não foi possível carregar campanhas.");
    } finally { setBusy(false); }
  }
  useEffect(() => { void load(); }, []);

  async function create(event: FormEvent) {
    event.preventDefault();
    setSaving(true); setError(""); setNotice("");
    try {
      const tags = segmentTags.split(",").map((item) => item.trim()).filter(Boolean);
      await api.client.createCampaign(name, message, {
        ...(templateId ? { template_id: templateId } : {}), ...(tags.length ? { tags } : {}),
        channels, language, tone, offer, recipient_limit: recipientLimit,
        include_contacts: includeContacts, include_conversations: includeConversations, consent_confirmed: consentConfirmed,
        group_jids: selectedGroupJids, group_authorization_confirmed: groupAuthorizationConfirmed,
        ...(scheduledAt ? { scheduled_at: scheduledAt } : {}),
      });
      setName(""); setMessage(""); setTemplateId(""); setSegmentTags(""); setChannels(["whatsapp"]);
      setOffer(""); setScheduledAt(""); setRecipientLimit(200); setConsentConfirmed(false);
      setIncludeContacts(true); setIncludeConversations(false); setSelectedGroupJids([]); setGroupAuthorizationConfirmed(false);
      setNotice("Campanha validada e colocada na fila persistente.");
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Não foi possível criar a campanha.");
    } finally { setSaving(false); }
  }
  async function action(id: string, value: "pause" | "resume" | "cancel") {
    try { await api.client.campaignAction(id, value); await load(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível atualizar a campanha."); }
  }
  async function saveCampaignSettings(event: FormEvent) {
    event.preventDefault(); setSettingsSaving(true); setError(""); setNotice("");
    try {
      await api.client.updateCampaignSettings(campaignSettings);
      setNotice("Protecções de campanha guardadas: limite diário, silêncio e atrasos aplicados ao worker.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Não foi possível guardar as protecções.");
    } finally { setSettingsSaving(false); }
  }

  return <div className="content-stack">
    <ModuleHeader eyebrow={english ? "OMNICHANNEL CAMPAIGNS" : "CAMPANHAS OMNICHANNEL"} title={english ? "Broadcasts, groups and conversations" : "Disparos, grupos e conversas"} description={english ? "Create a message for opted-in contacts or publish directly to your own groups. WhatsApp is processed by a persistent worker with consent, pauses, scheduling and retries." : "Cria uma mensagem para contactos autorizados ou publica directamente nos teus grupos próprios. O WhatsApp é processado por um worker persistente com consentimento, pausa, agendamento e retries."} action={<div className="live-pill"><span className="status-dot" /> Redis worker</div>} />
    {error && <ErrorBox message={error} />}{notice && <SuccessBox message={notice} />}
    <div className="module-grid two">
      <section className="data-panel"><div className="panel-heading"><div><span className="eyebrow">{english ? "NEW CAMPAIGN" : "NOVA CAMPANHA"}</span><h3>{english ? "Prepare content" : "Preparar conteúdo"}</h3></div><Send size={19} /></div>
        <form className="stack-form compact-form" onSubmit={create}>
          <label>Nome da campanha<input value={name} onChange={(event) => setName(event.target.value)} placeholder="Promoção de agosto" required /></label>
          <label>Canais de publicação<div className="channel-grid">{channelOptions.map((channel) => <label className="check-card" key={channel.id}><input type="checkbox" checked={channels.includes(channel.id)} onChange={() => setChannels((current) => current.includes(channel.id) ? current.filter((item) => item !== channel.id) : [...current, channel.id])} />{channel.label}</label>)}</div></label>
          <fieldset className="destination-fieldset"><legend>{english ? "Sending destinations" : "Destinos de envio"}</legend><small className="muted">{english ? <>Contacts use only <code>opt_in=true</code>. Groups receive the message directly; members are never extracted for marketing.</> : <>Contactos usam apenas <code>opt_in=true</code>. Grupos recebem a mensagem directamente; os membros nunca são extraídos para marketing.</>}</small>
            <label className="check-card"><input type="checkbox" checked={includeContacts} onChange={(event) => setIncludeContacts(event.target.checked)} />{english ? "Opted-in contacts" : "Contactos autorizados"}</label>
            <label className="check-card"><input type="checkbox" checked={includeConversations} onChange={(event) => setIncludeConversations(event.target.checked)} disabled={conversationAudience.length === 0} /><span><strong>{english ? "Existing conversations with opt-in" : "Conversas existentes com opt-in"}</strong><small className="muted">{conversationAudience.length ? (english ? `${conversationAudience.length} eligible conversation${conversationAudience.length === 1 ? "" : "s"}; only linked opted-in contacts are included.` : `${conversationAudience.length} conversa${conversationAudience.length === 1 ? " elegível" : "s elegíveis"}; só entram contactos ligados com opt-in.`) : (english ? "No eligible conversations. A conversation must match an opted-in contact." : "Não há conversas elegíveis. A conversa tem de corresponder a um contacto com opt-in.")}</small></span></label>
            {verifiedGroups.length ? <><div className="group-target-list">{verifiedGroups.map((group) => <label className="check-card" key={group.id}><input type="checkbox" checked={selectedGroupJids.includes(group.group_jid)} onChange={(event) => setSelectedGroupJids((current) => event.target.checked ? [...current, group.group_jid] : current.filter((item) => item !== group.group_jid))} />Grupo próprio: {group.name || group.group_jid}</label>)}</div><label className="check-card"><input type="checkbox" checked={groupAuthorizationConfirmed} onChange={(event) => setGroupAuthorizationConfirmed(event.target.checked)} required={selectedGroupJids.length > 0} />Confirmo que autorizo o envio apenas para estes grupos próprios onde a instância é administradora.</label></> : <small className="muted">{english ? <>No verified own groups yet. Open <b>Own groups</b> and click <b>Sync groups</b>.</> : <>Ainda não há grupos próprios verificados. Abre <b>Grupos próprios</b> e clica em <b>Sincronizar grupos</b>.</>}</small>}
          </fieldset>
          <label>Template opcional<select value={templateId} onChange={(event) => { const value = event.target.value; setTemplateId(value); const selected = templates.find((item) => item.id === value); if (selected) setMessage(selected.body); }}><option value="">Escrever mensagem</option>{templates.filter((item) => item.status !== "archived").map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
          <label>Mensagem<textarea value={message} onChange={(event) => setMessage(event.target.value)} placeholder="Escreve a mensagem base ou seleciona um template" rows={5} required={!templateId} /></label>
          <label>Oferta ou produto<small className="muted">Opcional; o n8n pode adaptar o conteúdo por canal.</small><input value={offer} onChange={(event) => setOffer(event.target.value)} placeholder="Ex.: Plano Premium por 1.500 MT" /></label>
          <div className="form-grid-two"><label>Idioma<select value={language} onChange={(event) => setLanguage(event.target.value)}><option value="pt-MZ">Português de Moçambique</option><option value="en">English</option></select></label><label>Tom<select value={tone} onChange={(event) => setTone(event.target.value)}><option value="profissional">Profissional</option><option value="direto">Direto</option><option value="amigável">Amigável</option><option value="promocional">Promocional</option></select></label></div>
          <label>Agendar data e hora<small className="muted">Opcional; usa o fuso horário configurado abaixo.</small><input type="datetime-local" value={scheduledAt} onChange={(event) => setScheduledAt(event.target.value)} /></label>
          <label>Limite de contactos<small className="muted">Só afecta contactos com opt-in; grupos seleccionados são destinos directos e não contam como membros extraídos.</small><input type="number" min={1} max={15000} value={recipientLimit} onChange={(event) => setRecipientLimit(Math.max(1, Number(event.target.value) || 1))} required /></label>
          <label>Etiquetas do segmento<small className="muted">Separadas por vírgulas; vazio envia para todos com opt-in.</small><input value={segmentTags} onChange={(event) => setSegmentTags(event.target.value)} placeholder="vip, cliente" /></label>
          <label className="check-card consent-card"><input type="checkbox" checked={consentConfirmed} onChange={(event) => setConsentConfirmed(event.target.checked)} required={includeContacts || includeConversations} disabled={!includeContacts && !includeConversations} />{english ? "I confirm that the selected contacts/conversations authorised messages and that STOP will be respected." : "Confirmo que os contactos/conversas seleccionados autorizaram mensagens e que PARAR/STOP/SAIR será respeitado."}</label>
          <button className="primary-button" disabled={saving || channels.length === 0 || ((includeContacts || includeConversations) && !consentConfirmed) || (selectedGroupJids.length > 0 && !groupAuthorizationConfirmed)} type="submit">{saving ? "A preparar..." : "Colocar na fila omnichannel"}</button>
        </form>
      </section>
      <section className="data-panel"><div className="panel-heading"><div><span className="eyebrow">{english ? "HISTORY" : "HISTÓRICO"}</span><h3>{campaigns.length} {english ? "campaigns" : "campanhas"}</h3></div><ActivityIcon /></div>{busy ? <LoadingBox /> : campaigns.length ? <div className="data-list">{campaigns.map((campaign) => <div className="data-row" key={campaign.id}><div className="quick-icon"><Send size={16} /></div><div className="row-main"><strong>{campaign.name}</strong><small>{(campaign.channels || ["whatsapp"]).join(", ")} · {campaign.total || 0} destinos · {campaign.sent || 0} enviados</small></div><span className={`status-badge ${campaign.status || "queued"}`}>{campaign.status || "queued"}</span><div className="row-actions">{campaign.status === "paused" ? <button title="Retomar" onClick={() => void action(campaign.id, "resume")}><Play size={14} /></button> : <button title="Pausar" onClick={() => void action(campaign.id, "pause")}><Pause size={14} /></button>}<button title="Cancelar" onClick={() => void action(campaign.id, "cancel")}><XCircle size={14} /></button></div></div>)}</div> : <div className="empty-state">Ainda não criaste nenhuma campanha.</div>}</section>
    </div>
    <section className="data-panel campaign-safety-settings"><div className="panel-heading"><div><span className="eyebrow">{english ? "ANTI-SPAM PROTECTION" : "PROTECÇÃO CONTRA SPAM"}</span><h3>{english ? "Automatic sending rules" : "Regras automáticas de envio"}</h3></div><ShieldCheck size={19} /></div><p className="muted">{english ? "The worker pauses during the silence window, enforces the daily volume and uses random delays to reduce spam risk." : "O worker pausa na janela de silêncio, limita o volume diário e usa atrasos aleatórios para reduzir risco de spam."}</p><form className="form-grid-two" onSubmit={saveCampaignSettings}><label>Fuso horário<select value={campaignSettings.timezone} onChange={(event) => setCampaignSettings({ ...campaignSettings, timezone: event.target.value })}><option value="Africa/Maputo">África/Maputo</option><option value="UTC">UTC</option></select></label><label>Limite diário<input type="number" min={1} max={10000} value={campaignSettings.daily_limit} onChange={(event) => setCampaignSettings({ ...campaignSettings, daily_limit: Number(event.target.value) || 1 })} /></label><label>Silêncio começa às<input type="time" value={campaignSettings.silence_start} onChange={(event) => setCampaignSettings({ ...campaignSettings, silence_start: event.target.value })} /></label><label>Silêncio termina às<input type="time" value={campaignSettings.silence_end} onChange={(event) => setCampaignSettings({ ...campaignSettings, silence_end: event.target.value })} /></label><label>Atraso mínimo (segundos)<input type="number" min={5} max={120} value={campaignSettings.min_delay_seconds} onChange={(event) => setCampaignSettings({ ...campaignSettings, min_delay_seconds: Number(event.target.value) || 5 })} /></label><label>Atraso máximo (segundos)<input type="number" min={5} max={120} value={campaignSettings.max_delay_seconds} onChange={(event) => setCampaignSettings({ ...campaignSettings, max_delay_seconds: Number(event.target.value) || 12 })} /></label><button className="primary-button" disabled={settingsSaving} type="submit">{settingsSaving ? (english ? "Saving..." : "A guardar...") : (english ? "Save protections" : "Guardar protecções")}</button></form></section>
  </div>;
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
  const [selectedAddonId, setSelectedAddonId] = useState("");
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
  const trialPremium = Boolean(plan?.trial_access && trialStatus === "trial_active");
  const trialMessage = trialStatus === "trial_pending_connection" ? "A demonstração ainda não começou: liga o WhatsApp para iniciar os 2 dias." : trialPremium ? "Demonstração Premium activa: tens acesso às funcionalidades avançadas durante os 2 dias." : trialStatus === "trial_expired" ? "Demonstração terminada: escolhe um plano e confirma o pagamento para voltar a ligar o WhatsApp." : plan?.status === "ativo" ? "Plano activo e pronto para operar." : "A aguardar activação.";
  const limits = plan?.limits || {};
  const contactLimit = typeof limits.contact_limit === "number" ? limits.contact_limit : 0;
  const campaignLimit = typeof limits.campaigns_per_month === "number" ? limits.campaigns_per_month : 0;
  const teamLimit = typeof limits.team_seats === "number" ? limits.team_seats : 0;

  async function verify(event: FormEvent) {
    event.preventDefault(); setVerifying(true); setError(""); setNotice("");
    try {       const result = await api.client.verifyPayment(messageText, clientPhone, selectedAddonId || undefined); setNotice(result.response); setQrCode(result.qrcode || null); setQrState(result.state || ""); setMessageText(""); setSelectedAddonId(""); await load(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível validar o pagamento."); }
    finally { setVerifying(false); }
  }

  async function checkout(planId: string) {
    setCheckoutPlan(planId); setError(""); setNotice("");
    try { const result = await api.client.createLemonSqueezyCheckout(planId); window.location.assign(result.checkout_url); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível abrir o checkout online."); setCheckoutPlan(""); }
  }
  async function checkoutAddon(addonId: string) {
    setCheckoutPlan(`addon:${addonId}`); setError(""); setNotice("");
    try { const result = await api.client.createLemonSqueezyAddonCheckout(addonId); window.location.assign(result.checkout_url); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível abrir o checkout do extra."); setCheckoutPlan(""); }
  }

  return <div className="content-stack">
    <ModuleHeader eyebrow="PLANO E PAGAMENTOS" title="Escolhe o teu próximo nível" description={isInternational ? "Preços internacionais em USD · paga com cartão ou PayPal através do Lemon Squeezy." : "Preços locais em MT · paga por M-Pesa e valida o comprovativo com AutoPay."} />
    {error && <ErrorBox message={error} />}{notice && <SuccessBox message={notice} />}
    <section className="current-plan"><div><span className="eyebrow">PLANO ATUAL</span><h3>{plan?.plan_name || "Demonstração"}</h3><p>{trialMessage}{plan?.expires_at ? ` · expira em ${plan.expires_at}` : ""}</p></div><div className="plan-status"><CircleDollarSign size={20} />{trialPremium ? "Premium temporário" : plan?.mass_broadcast ? "Disparos ativos" : trialStatus === "trial_expired" ? "Pagamento necessário" : "Trial pendente"}</div></section>
    {trialPremium && <section className="trial-premium-banner"><div className="trial-premium-icon"><Sparkles size={21} /></div><div><span className="eyebrow">ACESSO TOTAL DURANTE A DEMONSTRAÇÃO</span><strong>Experimenta o poder do Premium</strong><p>{(plan?.trial_features || ["vídeo", "PDFs e documentos", "áudio", "imagens", "campanhas avançadas"]).join(" · ")}. Depois dos 2 dias, escolhes o plano que melhor se adapta ao teu negócio.</p></div></section>}
    {trialStatus === "trial_expired" && <section className="trial-expired-banner"><div><span className="eyebrow">DEMONSTRAÇÃO TERMINADA</span><strong>Escolhe como continuar</strong><p>O acesso Premium temporário foi encerrado. Compara os três planos abaixo e paga apenas o nível que precisas.</p></div><CircleDollarSign size={21} /></section>}
    <section className="data-panel"><div className="panel-heading"><div><span className="eyebrow">USO DO PLANO</span><h3>Limites e consumo actual</h3></div><BarChart3 size={19} /></div><div className="stat-grid"><div className="stat-card"><span>Contactos</span><strong>{plan?.usage?.contacts ?? 0}{contactLimit ? ` / ${contactLimit}` : ""}</strong></div><div className="stat-card"><span>Campanhas este mês</span><strong>{plan?.usage?.campaigns_this_month ?? 0}{campaignLimit ? ` / ${campaignLimit}` : ""}</strong></div><div className="stat-card"><span>Lugares da equipa</span><strong>{plan?.usage?.team_seats ?? 0}{teamLimit ? ` / ${teamLimit}` : ""}</strong></div></div><p className="muted">Os canais adicionais dependem do plano, da autorização do fornecedor e da configuração do tenant.</p></section>
    {isInternational && <section className="payment-instruction"><div className="quick-icon"><CircleDollarSign size={20} /></div><div><strong>Pagamento internacional com Lemon Squeezy</strong><p>Usa cartão, PayPal ou outro método apresentado no checkout. A subscrição só activa o plano depois da confirmação segura do webhook.</p></div></section>}
    {!isInternational && <><section className="payment-instruction"><div className="quick-icon"><Smartphone size={20} /></div><div><strong>Pagamento local por M-Pesa</strong><p>Transfere para <b>{mpesaNumber}</b>, em nome de <b>{mpesaName}</b>. Depois cola abaixo o SMS completo ou o ID da transacção. O AutoPay compara a transacção recebida antes de activar o plano.</p></div></section>
    <section className="data-panel"><div className="panel-heading"><div><span className="eyebrow">VALIDAÇÃO AUTOPAY</span><h3>Enviar comprovativo</h3></div><CheckCircle2 size={19} /></div>{selectedAddonId && <div className="payment-selection"><strong>Extra seleccionado: {addons.find((addon) => addon.id === selectedAddonId)?.name}</strong><button type="button" className="ghost-button" onClick={() => setSelectedAddonId("")}>Alterar</button></div>}<form className="stack-form compact-form" onSubmit={verify}><label>Número que fez a transferência<input value={clientPhone} onChange={(event) => setClientPhone(event.target.value)} placeholder="2588..." required /></label><label>SMS ou ID da transferência<textarea value={messageText} onChange={(event) => setMessageText(event.target.value)} placeholder="Cole aqui o SMS recebido do M-Pesa" rows={4} required /></label><button className="primary-button" disabled={verifying} type="submit">{verifying ? "A validar..." : selectedAddonId ? "Validar extra por M-Pesa" : "Validar pagamento"}</button></form></section></>}
    {(qrCode || qrState === "pending") && <section className="data-panel qr-panel"><div className="panel-heading"><div><span className="eyebrow">PRÓXIMO PASSO</span><h3>{qrCode ? "Liga o WhatsApp" : "QR Code em preparação"}</h3></div><QrCode size={19} /></div>{qrCode ? <><p>Pagamento confirmado. Abre o WhatsApp que vais automatizar, entra em <b>Aparelhos conectados</b> e lê este código.</p><img className="qr-image" src={qrCode} alt="QR Code para ligar o WhatsApp" /></> : <div className="empty-state">O pagamento foi confirmado. A instância está a preparar o QR Code; atualiza esta página ou usa o botão Gerar QR Code na área WhatsApp.</div>}</section>}
    <section className="data-panel"><div className="panel-heading"><div><span className="eyebrow">HISTÓRICO DE PAGAMENTOS</span><h3>{payments.length} registos</h3></div><RefreshCw size={19} /></div>{payments.length ? <div className="data-list">{payments.map((payment) => <div className="data-row" key={payment.id}><div className="quick-icon"><CircleDollarSign size={16} /></div><div className="row-main"><strong>{payment.provider === "lemonsqueezy" ? `Lemon Squeezy · ${payment.plan_name || payment.plan_id || "checkout"}` : (payment.transaction_id || "Código ainda não identificado")}</strong><small>{payment.client_phone || payment.payment_provider || "Pagamento online"} · {payment.created_at ? new Date(payment.created_at).toLocaleString("pt-PT") : "agora"}</small></div><span className={`status-badge ${payment.status || "pending"}`}>{payment.status || "pendente"}</span></div>)}</div> : <div className="empty-state">Os registos de pagamento aparecerão aqui.</div>}</section>
    <section className="plan-grid">{busy ? <LoadingBox /> : plans.map((item) => <article className={`plan-card ${item.id === plan?.plan ? "selected" : ""}`} key={item.id}><span className="eyebrow">{item.name}</span><strong>{formatPlanPrice(item, isInternational)}</strong><small>{item.validity_days} dias · {item.team_seats || 1} lugar(es) · {item.campaigns_per_month || 0} campanhas/mês</small><div className="benefits">{item.benefits.map((benefit) => <span key={benefit}><CheckIcon />{benefit}</span>)}</div>{!isInternational && <button className="secondary-button" type="button" onClick={() => setNotice(item.id === plan?.plan ? "Este é o teu plano actual." : `Plano ${item.name} seleccionado. Faz a transferência de ${formatPlanPrice(item, false)} e envia o SMS acima.`)}>{item.id === plan?.plan ? "Plano actual" : "Escolher por M-Pesa"}</button>}{isInternational && lemonStatus?.configured && lemonStatus.plans[item.id] && <button className="primary-button" type="button" disabled={checkoutPlan === item.id} onClick={() => void checkout(item.id)}>{checkoutPlan === item.id ? "A abrir checkout..." : "Pagar online"}</button>}</article>)}</section>
    {addons.length > 0 && <section className="data-panel"><div className="panel-heading"><div><span className="eyebrow">EXTRAS</span><h3>Adapta o teu plano</h3></div><Plus size={19} /></div><div className="data-list">{addons.map((addon) => <div className="data-row" key={addon.id}><div className="quick-icon"><Plus size={16} /></div><div className="row-main"><strong>{addon.name}</strong><small>{addon.description}</small></div><span className="tag">+{formatAddonPrice(addon, isInternational)}/mês</span>{isInternational && lemonStatus?.configured && lemonStatus.addons?.[addon.id] ? <button className="primary-button compact" type="button" disabled={checkoutPlan === `addon:${addon.id}`} onClick={() => void checkoutAddon(addon.id)}>{checkoutPlan === `addon:${addon.id}` ? "A abrir checkout..." : "Adicionar no checkout"}</button> : !isInternational ? <button className="secondary-button compact" type="button" onClick={() => { setSelectedAddonId(addon.id); setNotice(`Transfere ${formatAddonPrice(addon, false)} para 855000929 e envia o comprovativo abaixo para activar ${addon.name}.`); }}>{selectedAddonId === addon.id ? "Extra seleccionado" : "Activar por M-Pesa"}</button> : <button className="secondary-button compact" type="button" onClick={() => setNotice("Configura a variante deste extra no Lemon Squeezy para activar o checkout online.")}>Configuração necessária</button>}</div>)}</div></section>}
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
  const { language } = usePlatformLanguage();
  const english = language === "en";
  const [settings, setSettings] = useState<AssistantSettings>({ diretrizes_corporativas: "", base_conhecimento_documentos: "", timeout_humano_minutos: 15 });
  const [knowledgeFiles, setKnowledgeFiles] = useState<AssistantKnowledgeFile[]>([]);
  const [busy, setBusy] = useState(true);
  const [knowledgeBusy, setKnowledgeBusy] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [deletingId, setDeletingId] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    let mounted = true;
    void Promise.allSettled([api.client.assistant(), api.client.assistantKnowledge()]).then(([settingsResult, knowledgeResult]) => {
      if (!mounted) return;
      if (settingsResult.status === "fulfilled") setSettings(settingsResult.value);
      else setError(settingsResult.reason instanceof Error ? settingsResult.reason.message : (english ? "Unable to load the assistant." : "Não foi possível carregar o assistente."));
      if (knowledgeResult.status === "fulfilled") setKnowledgeFiles(knowledgeResult.value.files || []);
      else setError((current) => current || (english ? "Unable to load the knowledge base." : "Não foi possível carregar a base de conhecimento."));
    }).finally(() => { if (mounted) { setBusy(false); setKnowledgeBusy(false); } });
    return () => { mounted = false; };
  }, [english]);

  async function save(event: FormEvent) {
    event.preventDefault(); setSaving(true); setError(""); setNotice("");
    try { await api.client.updateAssistant(settings); setNotice(english ? "Assistant configuration saved." : "Configuração do assistente guardada."); }
    catch (reason) { setError(reason instanceof Error ? reason.message : (english ? "Unable to save the configuration." : "Não foi possível guardar a configuração.")); }
    finally { setSaving(false); }
  }

  async function refreshKnowledge() {
    try { const result = await api.client.assistantKnowledge(); setKnowledgeFiles(result.files || []); }
    catch (reason) { setError(reason instanceof Error ? reason.message : (english ? "Unable to refresh the knowledge base." : "Não foi possível actualizar a base de conhecimento.")); }
  }

  async function uploadKnowledge(file?: File) {
    if (!file) return;
    setUploading(true); setError(""); setNotice("");
    try {
      const result = await api.client.uploadAssistantKnowledge(file);
      if (result.file) setKnowledgeFiles((current) => [result.file, ...current.filter((item) => item.id !== result.file.id)]);
      setNotice(english ? `${file.name} is indexed and ready for the assistant.` : `${file.name} foi indexado e já está disponível para o assistente.`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : (english ? "Unable to process this file." : "Não foi possível processar este ficheiro."));
      await refreshKnowledge();
    } finally { setUploading(false); }
  }

  async function removeKnowledge(file: AssistantKnowledgeFile) {
    const question = english ? `Remove ${file.file_name} from the knowledge base?` : `Remover ${file.file_name} da base de conhecimento?`;
    if (!window.confirm(question)) return;
    setDeletingId(file.id); setError(""); setNotice("");
    try { await api.client.deleteAssistantKnowledge(file.id); setKnowledgeFiles((current) => current.filter((item) => item.id !== file.id)); setNotice(english ? "File removed from the knowledge base." : "Ficheiro removido da base de conhecimento."); }
    catch (reason) { setError(reason instanceof Error ? reason.message : (english ? "Unable to remove this file." : "Não foi possível remover este ficheiro.")); }
    finally { setDeletingId(""); }
  }

  function formatFileSize(bytes: number) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  function fileIcon(file: AssistantKnowledgeFile) {
    if ([".png", ".jpg", ".jpeg"].includes(file.extension)) return <ImageIcon size={19} />;
    if ([".xlsx", ".csv"].includes(file.extension)) return <FileSpreadsheet size={19} />;
    if (file.extension === ".pptx") return <Presentation size={19} />;
    if (file.extension === ".docx") return <FileType size={19} />;
    return <FileText size={19} />;
  }

  function statusLabel(status: string) {
    if (status === "indexed") return english ? "Indexed" : "Indexado";
    if (status === "processing") return english ? "Processing..." : "A processar...";
    return english ? "Error" : "Erro";
  }

  if (busy) return <div className="content-stack"><LoadingBox /></div>;
  return <div className="content-stack"><ModuleHeader eyebrow="ASSISTENTE NEGOBOT" title="Configura o teu assistente" description="Define as regras de atendimento, a base de conhecimento e quando uma conversa passa para uma pessoa." />
    {error && <ErrorBox message={error} />}{notice && <SuccessBox message={notice} />}
    <form className="data-panel stack-form" onSubmit={save}>
      <div className="panel-heading"><div><span className="eyebrow">PERSONALIDADE E REGRAS</span><h3>Diretrizes corporativas</h3></div><Bot size={20} /></div>
      <textarea rows={7} value={settings.diretrizes_corporativas} onChange={(event) => setSettings({ ...settings, diretrizes_corporativas: event.target.value })} placeholder="Ex.: responde em Português de Moçambique, apresenta preços reais e encaminha pagamentos para validação AutoPay." />
      <label>{english ? "Manual knowledge notes" : "Notas manuais da base de conhecimento"}<textarea rows={6} value={settings.base_conhecimento_documentos} onChange={(event) => setSettings({ ...settings, base_conhecimento_documentos: event.target.value })} placeholder={english ? "Products, hours, location, FAQs and information the bot should know." : "Produtos, horários, localização, perguntas frequentes e informação que o bot deve conhecer."} /></label>
      <label>{english ? "Human handoff timeout (minutes)" : "Timeout para atendimento humano (minutos)"}<input type="number" min={1} max={240} value={settings.timeout_humano_minutos} onChange={(event) => setSettings({ ...settings, timeout_humano_minutos: Number(event.target.value) })} /></label>
      <section className="knowledge-base-section" aria-labelledby="knowledge-base-title">
        <div className="panel-heading"><div><span className="eyebrow">BASE DE CONHECIMENTO</span><h3 id="knowledge-base-title">{english ? "Support files" : "Ficheiros de suporte"}</h3></div><FileUp size={20} /></div>
        <p className="knowledge-intro">{english ? "Upload official files so the assistant can use their text, tables and slides when answering customers." : "Carrega ficheiros oficiais para o assistente consultar textos, tabelas e apresentações ao responder aos clientes."}</p>
        <label className={`knowledge-dropzone${dragging ? " is-dragging" : ""}`} onDragEnter={(event) => { event.preventDefault(); setDragging(true); }} onDragOver={(event) => { event.preventDefault(); setDragging(true); }} onDragLeave={(event) => { if (event.currentTarget === event.target) setDragging(false); }} onDrop={(event) => { event.preventDefault(); setDragging(false); void uploadKnowledge(event.dataTransfer.files?.[0]); }}>
          <UploadCloud size={26} />
          <strong>{uploading ? (english ? "Processing file..." : "A processar ficheiro...") : (english ? "Drag a file here or click to select" : "Arrasta um ficheiro aqui ou clica para seleccionar")}</strong>
          <small>PDF · XLSX · CSV · PPTX · DOCX · PNG · JPG · {english ? "up to 16 MB" : "até 16 MB"}</small>
          <input type="file" accept=".pdf,.xlsx,.csv,.pptx,.docx,.png,.jpg,.jpeg" disabled={uploading} onChange={(event) => { void uploadKnowledge(event.target.files?.[0]); event.currentTarget.value = ""; }} />
        </label>
        {knowledgeBusy ? <LoadingBox /> : knowledgeFiles.length ? <div className="knowledge-file-list">{knowledgeFiles.map((file) => <div className="knowledge-file-row" key={file.id}><div className="knowledge-file-icon">{fileIcon(file)}</div><div className="row-main"><strong title={file.file_name}>{file.file_name}</strong><small>{formatFileSize(file.size_bytes)} · {file.extension.replace(".", "").toUpperCase()} · {file.extracted_chars ? `${file.extracted_chars.toLocaleString()} ${english ? "characters" : "caracteres"}` : ""}</small>{file.error && <small className="knowledge-file-error">{file.error}</small>}</div><span className={`knowledge-status ${file.status}`}>{file.status === "indexed" && <CheckCircle2 size={13} />}{file.status === "processing" && <Loader2 size={13} className="spin" />}{file.status === "error" && <XCircle size={13} />}{statusLabel(file.status)}</span><button className="icon-button" type="button" title={english ? "Remove file" : "Remover ficheiro"} aria-label={english ? `Remove ${file.file_name}` : `Remover ${file.file_name}`} disabled={deletingId === file.id} onClick={() => void removeKnowledge(file)}>{deletingId === file.id ? <Loader2 size={15} className="spin" /> : <Trash2 size={15} />}</button></div>)}</div> : <div className="knowledge-empty">{english ? "No support files indexed yet." : "Ainda não existem ficheiros de suporte indexados."}</div>}
      </section>
      <div className="model-summary"><strong>{english ? "Active AI engines" : "Motores de IA activos"}</strong><span>{english ? "Text Engine Pro" : "Motor de Texto Pro"}<small>{english ? "For conversations, FAQs and scripts" : "Para conversas, FAQs e roteiros"}</small></span><span>{english ? "Advanced Vision Engine" : "Motor de Visão Avançada"}<small>{english ? "For images and documents" : "Para imagens e documentos"}</small></span></div>
      <button className="primary-button" disabled={saving} type="submit">{saving ? (english ? "Saving..." : "A guardar...") : (english ? "Save configuration" : "Guardar configuração")}</button>
    </form>
  </div>;
}


export function BusinessProfilePage() {
  const { language } = usePlatformLanguage();
  const english = language === "en";
  const [profile, setProfile] = useState<import("../lib/api").BusinessProfile>({ empresa_nome: "", nicho: "", email_corporativo: "", redes_sociais: { facebook: "", instagram: "", twitter_x: "", tiktok: "", telegram: "", linkedin: "" } });
  const [busy, setBusy] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  useEffect(() => { api.client.profile().then(setProfile).catch((reason) => setError(reason instanceof Error ? reason.message : (english ? "Unable to load the business profile." : "Não foi possível carregar o perfil empresarial."))).finally(() => setBusy(false)); }, [english]);
  function changeSocial(key: keyof typeof profile.redes_sociais, value: string) { setProfile((current) => ({ ...current, redes_sociais: { ...current.redes_sociais, [key]: value } })); }
  async function save(event: FormEvent) {
    event.preventDefault(); setSaving(true); setError(""); setNotice("");
    try { await api.client.updateProfile(profile); setNotice(english ? "Business profile and social networks saved to your workspace." : "Perfil empresarial e redes sociais guardados no teu tenant."); }
    catch (reason) { setError(reason instanceof Error ? reason.message : (english ? "Unable to save the profile." : "Não foi possível guardar o perfil.")); }
    finally { setSaving(false); }
  }
  if (busy) return <div className="content-stack"><LoadingBox /></div>;
  const socialPlaceholder = english ? "URL or username" : "URL ou nome de utilizador";
  return <div className="content-stack">
    <ModuleHeader eyebrow="PERFIL EMPRESARIAL" title="Empresa e redes sociais" description="Estes dados ficam associados ao email da tua conta e serão usados pelo assistente e pelas integrações omnichannel." />
    {error && <ErrorBox message={error} />}{notice && <SuccessBox message={notice} />}
    <form className="data-panel stack-form" onSubmit={save}>
      <div className="panel-heading"><div><span className="eyebrow">IDENTIFICAÇÃO</span><h3>Dados do negócio</h3></div><Building2 size={20} /></div>
      <label>{english ? "Account email" : "Email da conta"}<input value={profile.email || ""} readOnly disabled /></label>
      <label>{english ? "Company name" : "Nome da empresa"}<input value={profile.empresa_nome} onChange={(event) => setProfile({ ...profile, empresa_nome: event.target.value })} required /></label>
      <label>{english ? "Business niche" : "Nicho de negócio"}<input value={profile.nicho} onChange={(event) => setProfile({ ...profile, nicho: event.target.value })} placeholder={english ? "e.g. retail, hospitality, real estate" : "Ex.: comércio, restauração, imobiliária"} /></label>
      <label>{english ? "Business email" : "Email corporativo"}<input type="email" value={profile.email_corporativo} onChange={(event) => setProfile({ ...profile, email_corporativo: event.target.value })} placeholder={english ? "e.g. your@business.com" : "ex.: o@seu-negocio.com"} /></label>
      <div className="panel-heading"><div><span className="eyebrow">{english ? "DIGITAL CHANNELS" : "CANAIS DIGITAIS"}</span><h3>{english ? "Social networks and messaging" : "Redes sociais e mensageria"}</h3></div></div>
      <label>Facebook<input value={profile.redes_sociais.facebook} onChange={(event) => changeSocial("facebook", event.target.value)} placeholder={socialPlaceholder} /></label>
      <label>Instagram<input value={profile.redes_sociais.instagram} onChange={(event) => changeSocial("instagram", event.target.value)} placeholder={socialPlaceholder} /></label>
      <label>X / Twitter<input value={profile.redes_sociais.twitter_x} onChange={(event) => changeSocial("twitter_x", event.target.value)} placeholder={socialPlaceholder} /></label>
      <label>TikTok<input value={profile.redes_sociais.tiktok} onChange={(event) => changeSocial("tiktok", event.target.value)} placeholder={socialPlaceholder} /></label>
      <label>Telegram<input value={profile.redes_sociais.telegram} onChange={(event) => changeSocial("telegram", event.target.value)} placeholder={socialPlaceholder} /></label>
      <label>LinkedIn<input value={profile.redes_sociais.linkedin} onChange={(event) => changeSocial("linkedin", event.target.value)} placeholder={socialPlaceholder} /></label>
      <button className="primary-button" disabled={saving} type="submit">{saving ? (english ? "Saving..." : "A guardar...") : (english ? "Save business profile" : "Guardar perfil empresarial")}</button>
    </form>
  </div>;
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


type VideoSceneDraft = VideoScene & { id: number; media?: VideoAsset; voiceSample?: VideoAsset };

const VIDEO_VOICES = [
  { value: "pt_mz_male", pt: "António · Português", en: "António · Portuguese" },
  { value: "pt_mz_female", pt: "Francisca · Português", en: "Francisca · Portuguese" },
  { value: "en_us_male", pt: "Christopher · Inglês", en: "Christopher · English" },
  { value: "en_us_female", pt: "Aria · Inglês", en: "Aria · English" },
];

const MAX_VIDEO_SCENE_TEXT_LENGTH = 12_000;
const MAX_VIDEO_SCENE_DURATION_SECONDS = 300;

function formatVideoBytes(bytes: number) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function estimateSceneDuration(text: string) {
  const words = text.trim().split(/\s+/).filter(Boolean).length;
  if (!words) return 3.5;
  return Math.min(MAX_VIDEO_SCENE_DURATION_SECONDS, Math.max(1, Math.ceil((words / 2.35) * 2) / 2));
}

export function VideoPage() {
  const { language: interfaceLanguage } = usePlatformLanguage();
  const english = interfaceLanguage === "en";
  const [title, setTitle] = useState("");
  const [scenes, setScenes] = useState<VideoSceneDraft[]>([{ id: 1, text: "", duration_seconds: 3.5, visual_mode: "ai_media", voice: "pt_mz_male", subtitles: true }]);
  const [assets, setAssets] = useState<VideoAsset[]>([]);
  const [language, setLanguage] = useState("pt-MZ");
  const [transition, setTransition] = useState<"cut" | "fade">("fade");
  const [job, setJob] = useState<VideoJob | null>(null);
  const [saving, setSaving] = useState(false);
  const [assetsBusy, setAssetsBusy] = useState(true);
  const [uploading, setUploading] = useState<string | null>(null);
  const [draggingScene, setDraggingScene] = useState<number | null>(null);
  const mediaInputRefs = useRef<Record<number, HTMLInputElement | null>>({});
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [previewError, setPreviewError] = useState(false);

  useEffect(() => {
    void api.client.videoAssets().then((result) => setAssets(result.assets || [])).catch(() => undefined).finally(() => setAssetsBusy(false));
  }, []);
  useEffect(() => {
    if (!job?.id || ["completed", "deleted", "failed"].includes(job.status || "")) return;
    const timer = window.setInterval(() => { void api.client.videoJob(job.id).then((result) => setJob(result.job)).catch(() => undefined); }, 3500);
    return () => window.clearInterval(timer);
  }, [job?.id, job?.status]);

  function updateScene(id: number, fields: Partial<VideoSceneDraft>) {
    setScenes((current) => current.map((scene) => scene.id === id ? { ...scene, ...fields } : scene));
  }
  function addScene() {
    setScenes((current) => [...current, { id: Math.max(0, ...current.map((scene) => scene.id)) + 1, text: "", duration_seconds: 3.5, visual_mode: "ai_media", voice: language.startsWith("pt") ? "pt_mz_male" : "en_us_male", subtitles: true }]);
  }
  function removeScene(id: number) { setScenes((current) => current.length <= 1 ? current : current.filter((scene) => scene.id !== id)); }
  async function uploadForScene(sceneId: number, file: File, assetRole: "media" | "voice") {
    if (!file) return;
    setUploading(`${sceneId}:${assetRole}`); setError(""); setNotice("");
    try {
      const result = await api.client.uploadVideoAsset(file);
      setAssets((current) => [result.asset, ...current.filter((item) => item.id !== result.asset.id)]);
      if (assetRole === "voice") updateScene(sceneId, { voice_sample_url: result.asset.asset_url, voice_sample_mime: result.asset.mime_type, voiceSample: result.asset });
      else updateScene(sceneId, { asset_url: result.asset.asset_url, asset_kind: result.asset.kind === "image" ? "image" : "video", media: result.asset, visual_mode: "upload_media" });
      setNotice(english ? `${file.name} uploaded and attached to the scene.` : `${file.name} carregado e associado à cena.`);
    } catch (reason) { setError(reason instanceof Error ? reason.message : (english ? "The file could not be uploaded." : "Não foi possível carregar o ficheiro.")); }
    finally { setUploading(null); }
  }
  function isSupportedMediaFile(file: File) {
    const extension = file.name.toLowerCase().split(".").pop() || "";
    return ["mp4", "mov", "webm", "png", "jpg", "jpeg"].includes(extension) || ["video/mp4", "video/quicktime", "video/webm", "image/png", "image/jpeg"].includes(file.type);
  }
  function handleDragEnter(sceneId: number, event: React.DragEvent<HTMLDivElement>) {
    event.preventDefault(); event.stopPropagation();
    if (event.dataTransfer.types.includes("Files")) setDraggingScene(sceneId);
  }
  function handleDragOver(sceneId: number, event: React.DragEvent<HTMLDivElement>) {
    event.preventDefault(); event.stopPropagation(); event.dataTransfer.dropEffect = "copy";
    if (event.dataTransfer.types.includes("Files")) setDraggingScene(sceneId);
  }
  function handleDragLeave(sceneId: number, event: React.DragEvent<HTMLDivElement>) {
    event.preventDefault();
    const nextTarget = event.relatedTarget as Node | null;
    if (!nextTarget || !event.currentTarget.contains(nextTarget)) setDraggingScene((current) => current === sceneId ? null : current);
  }
  function handleDrop(sceneId: number, event: React.DragEvent<HTMLDivElement>) {
    event.preventDefault(); event.stopPropagation(); setDraggingScene(null);
    const file = Array.from(event.dataTransfer.files || [])[0];
    if (!file) return;
    if (!isSupportedMediaFile(file)) {
      setError(english ? "Use an MP4, MOV, WEBM, PNG or JPG file." : "Usa um ficheiro MP4, MOV, WEBM, PNG ou JPG.");
      return;
    }
    void uploadForScene(sceneId, file, "media");
  }
  async function create(event: FormEvent) {
    event.preventDefault(); setSaving(true); setError(""); setNotice("");
    const invalid = scenes.find((scene) => !scene.text.trim() || (scene.visual_mode === "upload_media" && !scene.asset_url) || (scene.visual_mode === "avatar_ai" && !scene.avatar_id?.trim()));
    if (invalid) { setError(english ? "Complete the text and the required visual option for every scene." : "Preenche o texto e a opção visual obrigatória de cada cena."); setSaving(false); return; }
    const payloadScenes = scenes.map(({ id: _id, media: _media, voiceSample: _voiceSample, ...scene }) => ({ ...scene, text: scene.text.trim(), duration_seconds: Math.min(MAX_VIDEO_SCENE_DURATION_SECONDS, Math.max(scene.duration_seconds || 3.5, estimateSceneDuration(scene.text))) }));
    try { const result = await api.client.createVideoJob({ title, scenes: payloadScenes, language, transition, subtitles: true }); setJob(result.job); setPreviewError(false); setNotice(english ? "Video queued. The worker will process each scene in sequence." : "Vídeo colocado na fila. O worker vai processar cada cena em sequência."); }
    catch (reason) { setError(reason instanceof Error ? reason.message : (english ? "The video engine is not available." : "O motor de vídeos ainda não está disponível.")); }
    finally { setSaving(false); }
  }
  async function downloadVideo() {
    if (!job) return;
    setError(""); setNotice("");
    try { const result = await api.client.downloadVideoJob(job.id); const url = URL.createObjectURL(result.blob); const anchor = document.createElement("a"); anchor.href = url; anchor.download = result.filename; document.body.appendChild(anchor); anchor.click(); anchor.remove(); window.setTimeout(() => URL.revokeObjectURL(url), 1000); const refreshed = await api.client.videoJob(job.id).catch(() => undefined); if (refreshed) setJob(refreshed.job); setNotice(english ? "Download started. The server copy was removed after the complete transfer." : "O download começou. A cópia do servidor foi eliminada depois da transferência completa."); }
    catch (reason) { setError(reason instanceof Error ? reason.message : (english ? "The video could not be downloaded." : "Não foi possível baixar o vídeo.")); }
  }
  async function deleteVideo() {
    if (!job) return;
    setError(""); setNotice("");
    try { await api.client.deleteVideoJob(job.id); setJob({ ...job, status: "deleted", output_available: false }); setNotice(english ? "The video was removed from the server." : "O vídeo foi removido do servidor."); }
    catch (reason) { setError(reason instanceof Error ? reason.message : (english ? "The video could not be removed." : "Não foi possível apagar o vídeo.")); }
  }
  function renderSceneOptions(scene: VideoSceneDraft, index: number) {
    const mediaAccept = ".mp4,.mov,.webm,.png,.jpg,.jpeg";
    const voiceAccept = ".mp3,.wav";
    return <div className="scene-item" key={scene.id}>
      <div className="scene-item-heading"><strong>{english ? `Scene ${index + 1}` : `Cena ${index + 1}`}</strong>{scenes.length > 1 && <button type="button" className="ghost-button" onClick={() => removeScene(scene.id)}>{english ? "Remove" : "Remover"}</button>}</div>
      <textarea value={scene.text} onChange={(event) => { const nextText = event.target.value.slice(0, MAX_VIDEO_SCENE_TEXT_LENGTH); const currentEstimate = estimateSceneDuration(scene.text); const shouldAutoUpdate = !scene.text.trim() || scene.duration_seconds === 3.5 || scene.duration_seconds === currentEstimate; updateScene(scene.id, { text: nextText, ...(shouldAutoUpdate ? { duration_seconds: estimateSceneDuration(nextText) } : {}) }); }} rows={5} maxLength={MAX_VIDEO_SCENE_TEXT_LENGTH} required={index === 0} placeholder={english ? "Describe what should appear and be said... Long scripts are accepted." : "Descreve o que deve aparecer e ser dito... Roteiros longos são aceites."} />
      <small className="muted scene-text-counter">{scene.text.length.toLocaleString()} / {MAX_VIDEO_SCENE_TEXT_LENGTH.toLocaleString()} {english ? "characters" : "caracteres"}</small>
      <div className="scene-grid-two"><label>{english ? "Duration (seconds)" : "Duração (segundos)"}<input type="number" min={1} max={MAX_VIDEO_SCENE_DURATION_SECONDS} step={0.5} value={scene.duration_seconds} onChange={(event) => updateScene(scene.id, { duration_seconds: Math.min(MAX_VIDEO_SCENE_DURATION_SECONDS, Math.max(1, Number(event.target.value) || 1)) })} /><small className="muted">{english ? `Suggested for this text: ${estimateSceneDuration(scene.text)}s` : `Sugestão para este texto: ${estimateSceneDuration(scene.text)}s`}</small></label><label>{english ? "Visual mode" : "Modo visual"}<select value={scene.visual_mode || "ai_media"} onChange={(event) => updateScene(scene.id, { visual_mode: event.target.value as VideoVisualMode })}><option value="avatar_ai">{english ? "AI Avatar / Spokesperson" : "Avatar AI / Porta-Voz"}</option><option value="upload_media">{english ? "Upload Media" : "Upload de Mídia"}</option><option value="ai_media">{english ? "Generate Media with AI" : "Gerar Mídia por IA"}</option></select></label></div>
      {scene.visual_mode === "avatar_ai" && <div className="scene-option-panel"><label>{english ? "Avatar ID" : "ID do avatar"}<input value={scene.avatar_id || ""} onChange={(event) => updateScene(scene.id, { avatar_id: event.target.value })} placeholder={english ? "Configured HeyGen avatar ID" : "ID do avatar HeyGen configurado"} /></label><small className="muted">{english ? "Requires HEYGEN_API_KEY and an approved avatar in the Video Worker." : "Requer HEYGEN_API_KEY e um avatar aprovado no Video Worker."}</small></div>}
      {scene.visual_mode === "upload_media" && <div className={`scene-dropzone ${draggingScene === scene.id ? "is-dragging" : ""}`} role="button" tabIndex={0} aria-label={english ? "Upload scene video or image" : "Carregar vídeo ou imagem da cena"} onClick={() => mediaInputRefs.current[scene.id]?.click()} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); mediaInputRefs.current[scene.id]?.click(); } }} onDragEnter={(event) => handleDragEnter(scene.id, event)} onDragOver={(event) => handleDragOver(scene.id, event)} onDragLeave={(event) => handleDragLeave(scene.id, event)} onDrop={(event) => handleDrop(scene.id, event)}><UploadCloud size={19} /><strong>{uploading === `${scene.id}:media` ? (english ? "Uploading..." : "A carregar...") : scene.media?.file_name || (english ? "Drop a video or image here" : "Arrasta um vídeo ou imagem para aqui")}</strong><small>{scene.media ? formatVideoBytes(scene.media.size_bytes) : (english ? "or click to choose · MP4, MOV, WEBM, PNG, JPG" : "ou clica para seleccionar · MP4, MOV, WEBM, PNG, JPG")}</small><input ref={(element) => { mediaInputRefs.current[scene.id] = element; }} type="file" accept={mediaAccept} disabled={uploading === `${scene.id}:media`} onClick={(event) => event.stopPropagation()} onChange={(event) => { const file = event.target.files?.[0]; if (file) void uploadForScene(scene.id, file, "media"); event.currentTarget.value = ""; }} /></div>}
      {scene.visual_mode === "ai_media" && <div className="scene-option-hint"><Sparkles size={16} />{english ? "The worker generates a vertical AI background from this scene text, with Pexels fallback." : "O worker gera um fundo vertical por IA a partir do texto, com fallback Pexels."}</div>}
      <div className="scene-grid-two"><label>{english ? "Voice" : "Voz"}<select value={scene.voice || ""} onChange={(event) => updateScene(scene.id, { voice: event.target.value || undefined })}><option value="">{english ? "Default voice" : "Voz padrão"}</option>{VIDEO_VOICES.map((voice) => <option key={voice.value} value={voice.value}>{english ? voice.en : voice.pt}</option>)}</select></label><label className="toggle-field"><span>{english ? "Animated subtitles" : "Legendas dinâmicas"}<small>{english ? "Show word-level captions" : "Mostrar legendas sincronizadas"}</small></span><input type="checkbox" checked={scene.subtitles !== false} onChange={(event) => updateScene(scene.id, { subtitles: event.target.checked })} /></label></div>
      <label className="scene-upload-inline"><span><FileUp size={15} />{scene.voiceSample?.file_name || (english ? "Clone voice with MP3/WAV sample" : "Clonar voz com amostra MP3/WAV")}</span><input type="file" accept={voiceAccept} disabled={uploading === `${scene.id}:voice`} onChange={(event) => { const file = event.target.files?.[0]; if (file) void uploadForScene(scene.id, file, "voice"); event.currentTarget.value = ""; }} /></label>
      {scene.voiceSample && <small className="muted">{english ? "Voice sample attached" : "Amostra de voz associada"} · {formatVideoBytes(scene.voiceSample.size_bytes)}</small>}
    </div>;
  }
  return <div className="content-stack"><ModuleHeader eyebrow="VÍDEOS CURTOS" title="Cria vídeos verticais com IA" description="Transforma um roteiro em cenas 9:16 e acompanha a renderização no worker persistente." action={<div className="live-pill"><span className="status-dot" /> Fila assíncrona</div>} />{error && <ErrorBox message={error} />}{notice && <SuccessBox message={notice} />}<div className="module-grid two"><section className="data-panel"><div className="panel-heading"><div><span className="eyebrow">NOVO VÍDEO</span><h3>Roteiro por cenas</h3></div><Video size={19} /></div><form className="stack-form compact-form" onSubmit={create}><label>Título<input value={title} onChange={(event) => setTitle(event.target.value)} required minLength={2} maxLength={160} placeholder="Oferta especial de agosto" /></label><div className="scene-grid-two"><label>Idioma<select value={language} onChange={(event) => setLanguage(event.target.value)}><option value="pt-MZ">Português de Moçambique</option><option value="en">English</option></select></label><label>{english ? "Scene transition" : "Transição entre cenas"}<select value={transition} onChange={(event) => setTransition(event.target.value as "cut" | "fade")}><option value="fade">{english ? "Soft fade" : "Fade suave"}</option><option value="cut">{english ? "Quick cut" : "Corte rápido"}</option></select></label></div><fieldset className="scene-list"><legend>{english ? "Scenes" : "Cenas"}</legend><small className="muted">{english ? "Choose the visual source, voice and animated subtitles for every scene." : "Escolhe a fonte visual, a voz e as legendas animadas de cada cena."}</small>{scenes.map(renderSceneOptions)}<button type="button" className="secondary-button compact" onClick={addScene}><Plus size={15} />{english ? "Add new scene" : "Adicionar nova cena"}</button></fieldset><small className="muted">{(() => { const characters = scenes.reduce((total, scene) => total + scene.text.length, 0); const seconds = scenes.reduce((total, scene) => total + estimateSceneDuration(scene.text), 0); return english ? `${characters.toLocaleString()} characters · estimated narration ${seconds.toFixed(1)}s. Final duration follows the generated audio; narration is not cut.` : `${characters.toLocaleString()} caracteres · narração estimada em ${seconds.toFixed(1)}s. A duração final segue o áudio gerado; a narração não é cortada.`; })()}</small><small className="muted">{assetsBusy ? (english ? "Loading your media library..." : "A carregar a tua biblioteca de media...") : `${assets.length} ${english ? "media assets available for this tenant." : "media disponíveis para este tenant."}`}</small><button className="primary-button" disabled={saving || Boolean(uploading)} type="submit">{saving ? (english ? "Queueing..." : "A colocar na fila...") : (english ? "Render video" : "Renderizar vídeo")}</button></form></section><section className="data-panel"><div className="panel-heading"><div><span className="eyebrow">ESTADO DO JOB</span><h3>{job?.title || "Nenhum job ativo"}</h3></div><Video size={19} /></div>{job ? <div className="content-stack"><div className="stat-card blue"><div className="stat-top"><span>Estado</span><span className="status-badge">{job.status || "queued"}</span></div><strong>{job.progress || 0}%</strong><small>{english ? "Scene-by-scene rendering progress" : "Progresso da renderização por cenas"}</small></div>{job.error && <ErrorBox message={job.error} />}{job.status === "completed" && job.output_available !== false && <div className="video-preview-card"><div className="video-preview-heading"><div><span className="eyebrow">{english ? "PREVIEW" : "PRÉ-VISUALIZAÇÃO"}</span><strong>{english ? "Watch your video" : "Visualiza o teu vídeo"}</strong></div><Video size={18} /></div><video className="video-preview" controls playsInline preload="metadata" src={api.client.videoPreviewUrl(job.id)} aria-label={english ? "Generated video preview" : "Pré-visualização do vídeo gerado"} onError={() => setPreviewError(true)} />{previewError && <p className="muted">{english ? "The preview could not be loaded. Try again or download the video." : "Não foi possível carregar a pré-visualização. Tenta novamente ou baixa o vídeo."}</p>}</div>}{job.status === "completed" && <div className="payment-instruction"><div className="quick-icon"><CheckCircle2 size={20} /></div><div><strong>{english ? "Video ready" : "Vídeo pronto"}</strong><p>{english ? "Download the file to your device before publishing. The temporary server copy is deleted after a complete transfer." : "Baixa o ficheiro para o teu dispositivo antes de publicar. A cópia temporária é eliminada depois da transferência completa."}</p><div className="row-actions"><button className="primary-button compact" type="button" onClick={() => void downloadVideo()} disabled={job.output_available === false}><Download size={16} />{english ? "Download video" : "Baixar vídeo"}</button><button className="ghost-button" type="button" onClick={() => void deleteVideo()} disabled={job.output_available === false}><Trash2 size={16} />{english ? "Delete from server" : "Apagar do servidor"}</button></div></div></div>}{job.status === "deleted" && <div className="payment-instruction"><div className="quick-icon"><CheckCircle2 size={20} /></div><div><strong>{english ? "Server copy deleted" : "Cópia do servidor eliminada"}</strong><p>{english ? "Use the copy saved on your device to publish on your social networks." : "Usa a cópia guardada no teu dispositivo para publicar nas tuas redes sociais."}</p></div></div>}{job.status !== "completed" && job.status !== "deleted" && job.status !== "failed" && <div className="loading-box"><Loader2 size={18} className="spin" /> {english ? "Processing on the server..." : "A processar no servidor..."}</div>}</div> : <div className="empty-state">{english ? "Create a script to start rendering." : "Cria um roteiro para iniciar a renderização."}</div>}</section></div></div>;
}
