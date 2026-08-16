import { useEffect, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import { CircleDollarSign, Loader2, MessageCircle, Pause, Play, Plus, Send, Users, XCircle } from "lucide-react";
import { api, type Campaign, type ClientPlan, type Contact, type Conversation } from "../lib/api";

function ModuleHeader({ eyebrow, title, description, action }: { eyebrow: string; title: string; description: string; action?: ReactNode }) {
  return <div className="module-header"><div><span className="eyebrow">{eyebrow}</span><h1>{title}</h1><p>{description}</p></div>{action}</div>;
}

function LoadingBox() { return <div className="loading-box"><Loader2 size={18} className="spin" /> A carregar informação...</div>; }
function ErrorBox({ message }: { message: string }) { return <div className="alert error"><XCircle size={16} />{message}</div>; }

export function ConversationsPage() {
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [busy, setBusy] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    setBusy(true); setError("");
    try {
      const [contactResult, conversationResult] = await Promise.all([api.client.contacts(), api.client.conversations()]);
      setContacts(contactResult.contacts || []); setConversations(conversationResult.conversations || []);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível carregar as conversas."); }
    finally { setBusy(false); }
  }
  useEffect(() => { void load(); }, []);

  async function addContact(event: FormEvent) {
    event.preventDefault(); setSaving(true); setError("");
    try { await api.client.createContact(name, phone); setName(""); setPhone(""); await load(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível guardar o contacto."); }
    finally { setSaving(false); }
  }

  return <div className="content-stack"><ModuleHeader eyebrow="CONTACTOS E CONVERSAS" title="Central de conversas" description="Mantém os teus contactos organizados e acompanha as interações do assistente." action={<button className="primary-button compact" onClick={() => document.getElementById("new-contact")?.scrollIntoView({ behavior: "smooth" })}><Plus size={16} /> Novo contacto</button>} />
    {error && <ErrorBox message={error} />}
    <div className="module-grid two"><section className="data-panel"><div className="panel-heading"><div><span className="eyebrow">CONTACTOS</span><h3>{contacts.length} contactos</h3></div><Users size={19} /></div>{busy ? <LoadingBox /> : contacts.length ? <div className="data-list">{contacts.slice(0, 100).map((contact) => <div className="data-row" key={contact.id}><div className="avatar">{contact.name.slice(0, 1).toUpperCase()}</div><div className="row-main"><strong>{contact.name}</strong><small>{contact.phone}</small></div><span className="tag">{contact.opt_in === false ? "Sem opt-in" : "Opt-in"}</span></div>)}</div> : <div className="empty-state">Ainda não existem contactos.</div>}</section>
      <section className="data-panel" id="new-contact"><div className="panel-heading"><div><span className="eyebrow">ADICIONAR</span><h3>Novo contacto</h3></div><Plus size={19} /></div><form className="stack-form compact-form" onSubmit={addContact}><label>Nome<input value={name} onChange={(event) => setName(event.target.value)} placeholder="Nome do contacto" required /></label><label>WhatsApp<input value={phone} onChange={(event) => setPhone(event.target.value)} placeholder="2588..." required /></label><button className="primary-button" disabled={saving} type="submit">{saving ? "A guardar..." : "Guardar contacto"}</button></form></section></div>
    <section className="data-panel"><div className="panel-heading"><div><span className="eyebrow">ATIVIDADE</span><h3>Conversas recentes</h3></div><MessageCircle size={19} /></div>{conversations.length ? <div className="data-list">{conversations.map((conversation) => <div className="data-row" key={conversation.id || conversation.phone}><div className="quick-icon"><MessageCircle size={17} /></div><div className="row-main"><strong>{conversation.name || conversation.phone || "Contacto"}</strong><small>{conversation.last_message || "Sem mensagem recente"}</small></div><small className="muted">{conversation.status || "ativa"}</small></div>)}</div> : <div className="empty-state">As conversas recebidas pelo webhook aparecerão aqui.</div>}</section>
  </div>;
}

export function CampaignsPage() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [name, setName] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  async function load() { setBusy(true); try { setCampaigns((await api.client.campaigns()).campaigns || []); } catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível carregar campanhas."); } finally { setBusy(false); } }
  useEffect(() => { void load(); }, []);
  async function create(event: FormEvent) { event.preventDefault(); setSaving(true); setError(""); try { await api.client.createCampaign(name, message); setName(""); setMessage(""); await load(); } catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível criar a campanha."); } finally { setSaving(false); } }
  async function action(id: string, value: "pause" | "resume" | "cancel") { try { await api.client.campaignAction(id, value); await load(); } catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível atualizar a campanha."); } }
  return <div className="content-stack"><ModuleHeader eyebrow="DISPAROS SEGMENTADOS" title="Campanhas" description="Cria campanhas e acompanha o estado da fila persistente do NEGOBOT." action={<div className="live-pill"><span className="status-dot" /> Redis queue</div>} />{error && <ErrorBox message={error} />}<div className="module-grid two"><section className="data-panel"><div className="panel-heading"><div><span className="eyebrow">NOVA CAMPANHA</span><h3>Preparar disparo</h3></div><Send size={19} /></div><form className="stack-form compact-form" onSubmit={create}><label>Nome da campanha<input value={name} onChange={(event) => setName(event.target.value)} placeholder="Promoção de agosto" required /></label><label>Mensagem<textarea value={message} onChange={(event) => setMessage(event.target.value)} placeholder="Escreve a mensagem da campanha" rows={5} required /></label><button className="primary-button" disabled={saving} type="submit">{saving ? "A preparar..." : "Colocar na fila"}</button></form></section><section className="data-panel"><div className="panel-heading"><div><span className="eyebrow">HISTÓRICO</span><h3>{campaigns.length} campanhas</h3></div><ActivityIcon /></div>{busy ? <LoadingBox /> : campaigns.length ? <div className="data-list">{campaigns.map((campaign) => <div className="data-row" key={campaign.id}><div className="quick-icon"><Send size={16} /></div><div className="row-main"><strong>{campaign.name}</strong><small>{campaign.total || 0} destinatários · {campaign.sent || 0} enviados</small></div><span className={`status-badge ${campaign.status || "queued"}`}>{campaign.status || "queued"}</span><div className="row-actions">{campaign.status === "paused" ? <button title="Retomar" onClick={() => void action(campaign.id, "resume")}><Play size={14} /></button> : <button title="Pausar" onClick={() => void action(campaign.id, "pause")}><Pause size={14} /></button>}<button title="Cancelar" onClick={() => void action(campaign.id, "cancel")}><XCircle size={14} /></button></div></div>)}</div> : <div className="empty-state">Ainda não criaste nenhuma campanha.</div>}</section></div></div>;
}

function ActivityIcon() { return <Send size={19} />; }

export function BillingPage() {
  const [plan, setPlan] = useState<ClientPlan | null>(null);
  const [plans, setPlans] = useState<Array<{ id: string; name: string; price: number; duration_days: number; benefits: string[] }>>([]);
  const [error, setError] = useState("");
  useEffect(() => { Promise.all([api.client.plan(), api.client.plans()]).then(([current, catalog]) => { setPlan(current); setPlans(catalog.plans || []); }).catch((reason) => setError(reason instanceof Error ? reason.message : "Não foi possível carregar os planos.")); }, []);
  return <div className="content-stack"><ModuleHeader eyebrow="PLANO E PAGAMENTOS" title="Escolhe o teu próximo nível" description="Consulta os benefícios, confirma o teu plano e ativa a automação WhatsApp." />{error && <ErrorBox message={error} />}<section className="current-plan"><div><span className="eyebrow">PLANO ATUAL</span><h3>{plan?.plan_name || "Demonstração"}</h3><p>{plan?.status || "A aguardar ativação"}{plan?.expires_at ? ` · expira em ${plan.expires_at}` : ""}</p></div><div className="plan-status"><CircleDollarSign size={20} />{plan?.mass_broadcast ? "Disparos ativos" : "Modo demonstração"}</div></section><section className="plan-grid">{plans.map((item) => <article className={`plan-card ${item.id === plan?.plan ? "selected" : ""}`} key={item.id}><span className="eyebrow">{item.name}</span><strong>{item.price} MT</strong><small>{item.duration_days} dias</small><div className="benefits">{item.benefits.map((benefit) => <span key={benefit}><CheckIcon />{benefit}</span>)}</div><button className="primary-button" onClick={() => window.alert("O fluxo M-Pesa será ligado nesta etapa.")}>{item.id === plan?.plan ? "Plano atual" : "Escolher plano"}</button></article>)}</section></div>;
}
function CheckIcon() { return <span className="check-icon">✓</span>; }
