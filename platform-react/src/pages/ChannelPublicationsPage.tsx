import { useEffect, useState, type FormEvent } from "react";
import { AlertTriangle, CalendarClock, ExternalLink, Link2, Megaphone, RefreshCw, Send, ShieldCheck, XCircle } from "lucide-react";
import { api, type ChannelPublication, type WhatsAppChannelCapability } from "../lib/api";

function formatDate(value?: string | number | null) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString("pt-MZ", { dateStyle: "medium", timeStyle: "short" });
}

function statusLabel(publication: ChannelPublication) {
  if (publication.delivery_status === "outbound_adapter_not_configured") return "Bloqueada com segurança";
  if (publication.status === "scheduled") return "Agendada";
  if (publication.status === "published") return "Publicada";
  if (publication.status === "cancelled") return "Cancelada";
  return "Rascunho";
}

export function ChannelPublicationsPage() {
  const [capability, setCapability] = useState<WhatsAppChannelCapability | null>(null);
  const [publications, setPublications] = useState<ChannelPublication[]>([]);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [channelJid, setChannelJid] = useState("");
  const [channelName, setChannelName] = useState("");
  const [ctaUrl, setCtaUrl] = useState("");
  const [ctaLabel, setCtaLabel] = useState("Saber mais");
  const [scheduledAt, setScheduledAt] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    const result = await api.client.channelPublications();
    setCapability(result.capability);
    setPublications(result.publications);
  }
  useEffect(() => { void load().catch((reason) => setError(reason instanceof Error ? reason.message : "Não foi possível carregar as publicações.")); }, []);

  async function submit(event: FormEvent) {
    event.preventDefault(); setError(""); setNotice(""); setBusy(true);
    try {
      const result = await api.client.createChannelPublication({ title, body, channel_jid: channelJid || undefined, channel_name: channelName || undefined, cta_url: ctaUrl || undefined, cta_label: ctaUrl ? ctaLabel : undefined, scheduled_at: scheduledAt ? new Date(scheduledAt).toISOString() : undefined, timezone: "Africa/Maputo" });
      setNotice(result.publication.status === "scheduled" ? "Publicação colocada na agenda. A entrega ficará bloqueada até existir um adaptador de Channels autorizado." : "Rascunho guardado com sucesso.");
      setTitle(""); setBody(""); setChannelJid(""); setChannelName(""); setCtaUrl(""); setScheduledAt("");
      await load();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível guardar a publicação."); }
    finally { setBusy(false); }
  }

  async function action(id: string, operation: "cancel" | "retry") {
    setError("");
    try { await api.client.channelPublicationAction(id, operation); await load(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível actualizar a publicação."); }
  }

  return <div className="content-stack">
    <section className="hero-panel"><div><span className="eyebrow">WHATSAPP CHANNELS</span><h1>Publicações para o teu canal</h1><p>Prepara anúncios, promoções e conteúdos informativos com CTA para atendimento privado ou checkout.</p></div><div className="hero-orb"><Megaphone size={54} /></div></section>
    <section className="alert warning"><AlertTriangle size={18} /><div><strong>Entrega nativa ainda não autorizada</strong><span>{capability?.reason || "A Evolution API actual ainda não confirma publicação em WhatsApp Channels."} O editor e a agenda estão preparados, mas nenhuma publicação será enviada para um JID <code>@newsletter</code> sem verificação de administrador e adaptador compatível.</span></div></section>
    {error && <div className="alert error"><XCircle size={17} />{error}</div>}
    {notice && <div className="alert success"><ShieldCheck size={17} />{notice}</div>}
    <section className="two-column-grid">
      <article className="panel-card"><div className="section-heading compact"><div><span className="eyebrow">EDITOR</span><h3>Nova publicação</h3></div><Send size={20} /></div><form className="stack-form" onSubmit={submit}>
        <label>Título<input value={title} onChange={(event) => setTitle(event.target.value)} minLength={2} maxLength={160} required placeholder="Promoção desta semana" /></label>
        <label>Nome do canal<input value={channelName} onChange={(event) => setChannelName(event.target.value)} placeholder="Canal da minha empresa" /></label>
        <label>JID do canal <small>(termina em @newsletter; opcional no rascunho)</small><input value={channelJid} onChange={(event) => setChannelJid(event.target.value)} placeholder="1203...@newsletter" /></label>
        <label>Conteúdo<textarea value={body} onChange={(event) => setBody(event.target.value)} rows={7} maxLength={4000} required placeholder="Escreve a publicação que os seguidores vão receber." /></label>
        <div className="form-grid-two"><label>Link CTA<input value={ctaUrl} onChange={(event) => setCtaUrl(event.target.value)} placeholder="https://negobotmoz.duckdns.org/" /></label><label>Texto CTA<input value={ctaLabel} onChange={(event) => setCtaLabel(event.target.value)} disabled={!ctaUrl} placeholder="Saber mais" /></label></div>
        <label>Data e hora <small>(deixa vazio para guardar rascunho)</small><input type="datetime-local" value={scheduledAt} onChange={(event) => setScheduledAt(event.target.value)} /></label>
        <button className="primary-button" disabled={busy} type="submit"><CalendarClock size={17} />{busy ? "A guardar..." : scheduledAt ? "Agendar publicação" : "Guardar rascunho"}</button>
      </form></article>
      <article className="panel-card"><div className="section-heading compact"><div><span className="eyebrow">PRÉ-VISUALIZAÇÃO</span><h3>{title || "Título da publicação"}</h3></div><Link2 size={20} /></div><div className="channel-preview"><strong>{channelName || "O teu canal"}</strong><p>{body || "O conteúdo da tua publicação aparecerá aqui."}</p>{ctaUrl && <a href={ctaUrl} target="_blank" rel="noreferrer">{ctaLabel || "Saber mais"} <ExternalLink size={14} /></a>}</div><div className="helper-box"><ShieldCheck size={17} /><span>Os seguidores recebem a publicação no modo de transmissão. O CTA deve encaminhar para o atendimento privado ou para um site.</span></div></article>
    </section>
    <section className="panel-card"><div className="section-heading compact"><div><span className="eyebrow">HISTÓRICO</span><h3>Rascunhos e agenda</h3></div><button className="ghost-button" onClick={() => void load()}><RefreshCw size={15} /> Actualizar</button></div>{publications.length === 0 ? <div className="empty-state">Ainda não existem publicações. Guarda um rascunho ou prepara uma agenda.</div> : <div className="table-list">{publications.map((publication) => <div className="table-row" key={publication.id}><div><strong>{publication.title}</strong><small>{publication.channel_name || publication.channel_jid || "Canal ainda não identificado"} · {formatDate(publication.scheduled_at || publication.created_at)}</small></div><span className={`status-badge ${publication.status === "blocked" ? "warning" : publication.status === "published" ? "success" : ""}`}>{statusLabel(publication)}</span><div className="row-actions">{publication.status !== "cancelled" && publication.status !== "published" && <button className="ghost-button" onClick={() => void action(publication.id, "cancel")}>Cancelar</button>}{publication.status === "blocked" && <button className="ghost-button" onClick={() => void action(publication.id, "retry")}>Recolocar</button>}</div></div>)}</div>}</section>
  </div>;
}
