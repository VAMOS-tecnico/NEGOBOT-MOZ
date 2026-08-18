import { useMemo, useState } from "react";
import { AlertTriangle, CalendarClock, CheckCircle2, ChevronRight, Clock3, Filter, History, MessageCircle, Pause, Play, RefreshCw, Search, Send, ShieldCheck, UserRound, X } from "lucide-react";

type RenewalStatus = "scheduled" | "sent" | "paused" | "opted_out" | "failed";
type RenewalRegion = "mozambique" | "international";

type RenewalRecord = {
  id: string;
  tenant: string;
  phone: string;
  plan: string;
  region: RenewalRegion;
  renewalDate: string;
  nextNotice: string;
  status: RenewalStatus;
  language: "pt" | "en";
  noticesSent: number;
  lastNotice?: string;
  failure?: string;
};

const INITIAL_RENEWALS: RenewalRecord[] = [
  { id: "ren-001", tenant: "Maputo Digital, Lda.", phone: "+258 84 123 4567", plan: "Médio", region: "mozambique", renewalDate: "2026-09-01", nextNotice: "2026-08-18", status: "scheduled", language: "pt", noticesSent: 1, lastNotice: "2026-08-11" },
  { id: "ren-002", tenant: "Norte Criativo", phone: "+258 86 987 1122", plan: "Básico", region: "mozambique", renewalDate: "2026-08-26", nextNotice: "2026-08-19", status: "scheduled", language: "pt", noticesSent: 0 },
  { id: "ren-003", tenant: "Kaya Commerce", phone: "+351 912 444 870", plan: "Premium", region: "international", renewalDate: "2026-08-23", nextNotice: "2026-08-18", status: "sent", language: "en", noticesSent: 2, lastNotice: "2026-08-16" },
  { id: "ren-004", tenant: "Marracuene Serviços", phone: "+258 82 556 4433", plan: "Médio", region: "mozambique", renewalDate: "2026-09-08", nextNotice: "2026-08-25", status: "paused", language: "pt", noticesSent: 1, lastNotice: "2026-08-11" },
  { id: "ren-005", tenant: "Coastal Labs", phone: "+44 7700 900145", plan: "Premium", region: "international", renewalDate: "2026-08-21", nextNotice: "2026-08-18", status: "failed", language: "en", noticesSent: 1, lastNotice: "2026-08-14", failure: "Evolution API não confirmou a entrega" },
  { id: "ren-006", tenant: "Bela Casa", phone: "+258 84 765 3300", plan: "Básico", region: "mozambique", renewalDate: "2026-09-12", nextNotice: "2026-08-29", status: "opted_out", language: "pt", noticesSent: 0 },
];

const statusLabels: Record<RenewalStatus, string> = { scheduled: "Agendado", sent: "Enviado", paused: "Pausado", opted_out: "Opt-out", failed: "Falhou" };
const statusClasses: Record<RenewalStatus, string> = { scheduled: "scheduled", sent: "sent", paused: "paused", opted_out: "opted-out", failed: "failed" };

function formatDate(value: string) { return new Intl.DateTimeFormat("pt-PT", { day: "2-digit", month: "short", year: "numeric" }).format(new Date(`${value}T12:00:00`)); }
function daysUntil(value: string) { const today = new Date("2026-08-18T12:00:00"); const date = new Date(`${value}T12:00:00`); return Math.ceil((date.getTime() - today.getTime()) / 86400000); }
function regionLabel(region: RenewalRegion) { return region === "mozambique" ? "Moçambique · M-Pesa" : "Internacional · Lemon Squeezy"; }

function RenewalStatusBadge({ status }: { status: RenewalStatus }) { return <span className={`renewal-status ${statusClasses[status]}`}><span className="status-dot" />{statusLabels[status]}</span>; }

export function RenewalsPage() {
  const [renewals, setRenewals] = useState(INITIAL_RENEWALS);
  const [selectedId, setSelectedId] = useState<string | null>(INITIAL_RENEWALS[0].id);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | RenewalStatus>("all");
  const [regionFilter, setRegionFilter] = useState<"all" | RenewalRegion>("all");
  const [notice, setNotice] = useState("");

  const filtered = useMemo(() => renewals.filter((item) => {
    const query = search.trim().toLowerCase();
    const matchesSearch = !query || `${item.tenant} ${item.phone} ${item.plan}`.toLowerCase().includes(query);
    return matchesSearch && (statusFilter === "all" || item.status === statusFilter) && (regionFilter === "all" || item.region === regionFilter);
  }), [renewals, search, statusFilter, regionFilter]);
  const selected = renewals.find((item) => item.id === selectedId) || filtered[0] || null;
  const dueSoon = renewals.filter((item) => item.status !== "opted_out" && daysUntil(item.renewalDate) <= 14).length;
  const sent = renewals.filter((item) => item.status === "sent").length;
  const optedOut = renewals.filter((item) => item.status === "opted_out").length;
  const failed = renewals.filter((item) => item.status === "failed").length;

  function updateStatus(id: string, status: RenewalStatus, message: string) {
    setRenewals((current) => current.map((item) => item.id === id ? { ...item, status } : item));
    setNotice(message);
    window.setTimeout(() => setNotice(""), 3500);
  }

  function simulateResend(item: RenewalRecord) {
    setRenewals((current) => current.map((entry) => entry.id === item.id ? { ...entry, status: "sent", noticesSent: entry.noticesSent + 1, lastNotice: "2026-08-18", failure: undefined } : entry));
    setNotice(`Aviso reenviado para ${item.tenant}. O envio real será ligado ao worker na próxima fase.`);
    window.setTimeout(() => setNotice(""), 4500);
  }

  return <div className="content-stack renewal-page">
    <div className="module-header"><div><span className="eyebrow">OPERAÇÃO COMERCIAL</span><h1>Gestão de renovações</h1><p>Acompanha a transição dos clientes antigos e prepara cada aviso antes da próxima renovação.</p></div><button className="secondary-button" onClick={() => setNotice("A sincronização real será ligada ao endpoint de renovações.")}><RefreshCw size={16} /> Sincronizar</button></div>
    <div className="renewal-preview-banner"><div className="renewal-preview-icon"><ShieldCheck size={21} /></div><div><strong>Pré-visualização operacional</strong><span>Os dados apresentados são de demonstração. O envio permanece bloqueado até o worker e os endpoints administrativos estarem ligados.</span></div><button aria-label="Fechar aviso" onClick={() => setNotice("A pré-visualização continua disponível nesta sessão.")}><X size={16} /></button></div>
    {notice && <div className="alert info"><CheckCircle2 size={16} />{notice}</div>}
    <section className="stat-grid renewal-stats"><article className="stat-card amber"><div className="stat-top"><span>Próximos 14 dias</span><span className="icon-chip"><CalendarClock size={17} /></span></div><strong>{dueSoon}</strong><small>Clientes que precisam de atenção</small></article><article className="stat-card blue"><div className="stat-top"><span>Avisos enviados</span><span className="icon-chip"><Send size={17} /></span></div><strong>{sent}</strong><small>Este ciclo de transição</small></article><article className="stat-card violet"><div className="stat-top"><span>Opt-out</span><span className="icon-chip"><Pause size={17} /></span></div><strong>{optedOut}</strong><small>Clientes que não recebem avisos</small></article><article className="stat-card red"><div className="stat-top"><span>Com falha</span><span className="icon-chip"><AlertTriangle size={17} /></span></div><strong>{failed}</strong><small>Aguardam nova tentativa</small></article></section>
    <section className="renewal-command-bar"><div className="renewal-search"><Search size={16} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Pesquisar cliente, número ou plano" /></div><div className="renewal-filter"><Filter size={15} /><select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as "all" | RenewalStatus)}><option value="all">Todos os estados</option>{Object.entries(statusLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></div><div className="renewal-filter"><select value={regionFilter} onChange={(event) => setRegionFilter(event.target.value as "all" | RenewalRegion)}><option value="all">Todas as regiões</option><option value="mozambique">Moçambique</option><option value="international">Internacional</option></select></div></section>
    <div className="renewal-layout"><section className="data-panel renewal-list-panel"><div className="panel-heading"><div><span className="eyebrow">CLIENTES ANTIGOS</span><h3>Fila de transição <span className="count-pill">{filtered.length}</span></h3></div><History size={19} /></div>{filtered.length ? <div className="renewal-list">{filtered.map((item) => <div key={item.id} className={`renewal-list-row ${selected?.id === item.id ? "selected" : ""}`} role="button" tabIndex={0} onClick={() => setSelectedId(item.id)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") setSelectedId(item.id); }}><div className="avatar renewal-avatar">{item.tenant.slice(0, 1).toUpperCase()}</div><div className="row-main"><strong>{item.tenant}</strong><small>{item.plan} · {regionLabel(item.region)}</small></div><div className="renewal-row-date"><small>Renova em</small><strong>{daysUntil(item.renewalDate) <= 0 ? "Hoje" : `${daysUntil(item.renewalDate)} dias`}</strong></div><RenewalStatusBadge status={item.status} /><ChevronRight size={16} className="renewal-chevron" /></div>)}</div> : <div className="empty-state"><UserRound size={17} />Nenhum cliente corresponde aos filtros.</div>}</section>
      <aside className="renewal-side-column"><section className="data-panel renewal-calendar"><div className="panel-heading"><div><span className="eyebrow">CALENDÁRIO DE AVISOS</span><h3>Próximos disparos</h3></div><Clock3 size={19} /></div><div className="notice-calendar"><div className="notice-day"><span className="notice-day-number">14</span><div><strong>Primeiro aviso</strong><small>Explica a mudança de regras</small></div><span className="tag">Preparado</span></div><div className="notice-day"><span className="notice-day-number">7</span><div><strong>Lembrete</strong><small>Apresenta opções de renovação</small></div><span className="tag">Preparado</span></div><div className="notice-day"><span className="notice-day-number">1</span><div><strong>Aviso final</strong><small>Confirma data e pagamento</small></div><span className="tag">Preparado</span></div></div><div className="renewal-calendar-footer"><span><span className="status-dot" /> Diário · 09:00 Africa/Maputo</span><span>Redis Queue</span></div></section><section className="data-panel renewal-policy"><div className="panel-heading"><div><span className="eyebrow">POLÍTICA ACTUAL</span><h3>Transição protegida</h3></div><ShieldCheck size={19} /></div><p>Clientes sem <code>plan_rules_version</code> mantêm as condições antigas até à renovação. Depois do pagamento confirmado, entram nas regras <strong>2026-08-v2</strong>.</p><div className="policy-row"><span>Idioma local</span><strong>PT-MZ</strong></div><div className="policy-row"><span>Internacional</span><strong>EN</strong></div><div className="policy-row"><span>Duplicados</span><strong>Bloqueados</strong></div></section></aside>
    </div>
    {selected && <section className="data-panel renewal-detail"><div className="panel-heading"><div><span className="eyebrow">DETALHE DO CLIENTE</span><h3>{selected.tenant}</h3></div><RenewalStatusBadge status={selected.status} /></div><div className="renewal-detail-grid"><div className="renewal-detail-meta"><div><span>Contacto WhatsApp</span><strong>{selected.phone}</strong></div><div><span>Plano actual</span><strong>{selected.plan}</strong></div><div><span>Data de renovação</span><strong>{formatDate(selected.renewalDate)}</strong></div><div><span>Próximo aviso</span><strong>{formatDate(selected.nextNotice)}</strong></div><div><span>Pagamento</span><strong>{regionLabel(selected.region)}</strong></div><div><span>Avisos enviados</span><strong>{selected.noticesSent}</strong></div></div><div className="message-preview"><div className="message-preview-header"><span><MessageCircle size={15} /> Pré-visualização · {selected.language === "pt" ? "Português" : "English"}</span><small>WhatsApp</small></div><div className="whatsapp-bubble">{selected.language === "pt" ? <>Olá, <strong>{selected.tenant}</strong>. O teu plano <strong>{selected.plan}</strong> continua válido até <strong>{formatDate(selected.renewalDate)}</strong>. Na próxima renovação, aplicam-se as novas regras da NEGOBOT-MOZ. Responde <strong>RENOVAR</strong> para falar com a equipa ou <strong>PARAR</strong> para deixar de receber avisos.</> : <>Hello, <strong>{selected.tenant}</strong>. Your <strong>{selected.plan}</strong> plan renews on <strong>{formatDate(selected.renewalDate)}</strong>. The new NEGOBOT-MOZ plan rules will apply at renewal. Reply <strong>RENEW</strong> for help or <strong>STOP</strong> to opt out.</>}<span className="message-time">09:00 ✓✓</span></div>{selected.failure && <div className="channel-error"><AlertTriangle size={14} />{selected.failure}</div>}</div></div><div className="renewal-detail-actions"><div>{selected.status === "paused" ? <button className="secondary-button" onClick={() => updateStatus(selected.id, "scheduled", "A sequência de avisos foi retomada.")}><Play size={15} /> Retomar avisos</button> : selected.status !== "opted_out" && <button className="secondary-button" onClick={() => updateStatus(selected.id, "paused", "A sequência de avisos foi pausada.")}><Pause size={15} /> Pausar avisos</button>}{selected.status !== "opted_out" && <button className="secondary-button danger-soft" onClick={() => updateStatus(selected.id, "opted_out", "O cliente foi marcado como opt-out.")}><X size={15} /> Marcar opt-out</button>}</div><button className="primary-button" onClick={() => simulateResend(selected)} disabled={selected.status === "opted_out"}><Send size={15} /> Reenviar pré-visualização</button></div></section>}
  </div>;
}
