import { useEffect, useMemo, useState } from "react";
import { AlertCircle, CheckCircle2, Clock3, Link2, Power, RefreshCw } from "lucide-react";
import { FaLinkedin } from "react-icons/fa";
import { SiFacebook, SiGmail, SiInstagram, SiTelegram, SiTiktok, SiWhatsapp, SiX } from "react-icons/si";
import type { IconType } from "react-icons";
import { api, type ClientChannel } from "../lib/api";

const icons: Record<string, IconType> = {
  whatsapp: SiWhatsapp,
  instagram: SiInstagram,
  facebook: SiFacebook,
  telegram: SiTelegram,
  tiktok: SiTiktok,
  linkedin: FaLinkedin,
  x: SiX,
  email: SiGmail,
};

const statusLabels: Record<ClientChannel["status"], string> = {
  connected: "Ligado",
  not_configured: "Ainda não configurado",
  pending_authorization: "A aguardar autorização",
  pending_review: "A aguardar aprovação",
  disabled: "Desligado",
  error: "Precisa de atenção",
};

function statusTone(status: ClientChannel["status"]): string {
  if (status === "connected") return "active";
  if (status === "error") return "error";
  if (status === "pending_review" || status === "pending_authorization") return "pending";
  return "neutral";
}

function channelDescription(channel: ClientChannel): string {
  if (channel.key === "whatsapp") return "Atendimento, QR Code e assistente Negobot através da Evolution API.";
  if (channel.key === "telegram") return "Mensagens através de um bot Telegram próprio do teu negócio.";
  if (channel.key === "email") return "Entrada e envio de email através de SMTP ou fornecedor transaccional.";
  if (channel.requires_review) return `Disponível mediante autorização e revisão do ${channel.provider}.`;
  return `Integração através de ${channel.provider}.`;
}

export function ChannelsPage() {
  const [channels, setChannels] = useState<ClientChannel[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const result = await api.client.channels();
      setChannels(result.channels || []);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Não foi possível carregar os canais.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, []);

  const connectedCount = useMemo(() => channels.filter((channel) => channel.status === "connected").length, [channels]);

  async function handleAction(channel: ClientChannel) {
    setError("");
    setNotice("");
    if (channel.key === "whatsapp") {
      window.location.assign("/plataforma/whatsapp");
      return;
    }
    if (channel.status === "connected") {
      setBusy(channel.key);
      try {
        await api.client.updateChannel(channel.key, "disabled");
        setNotice(`${channel.label} foi desligado neste tenant.`);
        await load();
      } catch (reason) {
        setError(reason instanceof Error ? reason.message : `Não foi possível desligar ${channel.label}.`);
      } finally {
        setBusy(null);
      }
      return;
    }
    if (channel.requires_review) {
      setNotice(`${channel.label} requer autorização e aprovação do fornecedor antes de receber mensagens.`);
      return;
    }
    setNotice(`A ligação de ${channel.label} será activada quando as credenciais do fornecedor forem configuradas com segurança.`);
  }

  return <div className="content-stack">
    <section className="module-header">
      <div>
        <span className="eyebrow">CENTRAL OMNICHANNEL</span>
        <h1>Canais</h1>
        <p>Consulta as ligações do teu tenant num só lugar. Um canal pendente não bloqueia o WhatsApp nem os restantes canais.</p>
      </div>
      <button className="secondary-button" onClick={() => void load()} disabled={loading}><RefreshCw size={16} /> Actualizar</button>
    </section>
    {error && <div className="alert error"><AlertCircle size={16} />{error}</div>}
    {notice && <div className="alert success"><CheckCircle2 size={16} />{notice}</div>}
    <section className="stat-grid">
      <article className="stat-card green"><div className="stat-top"><span>Canais ligados</span><CheckCircle2 size={17} /></div><strong>{loading ? "—" : connectedCount}</strong><small>Integrações activas neste espaço</small></article>
      <article className="stat-card blue"><div className="stat-top"><span>Canais disponíveis</span><Link2 size={17} /></div><strong>{loading ? "—" : channels.length}</strong><small>Catálogo preparado para evolução</small></article>
      <article className="stat-card violet"><div className="stat-top"><span>Isolamento</span><Power size={17} /></div><strong>Tenant</strong><small>Credenciais e eventos separados por cliente</small></article>
    </section>
    <section className="data-panel">
      <div className="panel-heading"><div><span className="eyebrow">ESTADO DAS INTEGRAÇÕES</span><h3>Os teus canais</h3></div><span className="muted">{connectedCount} ligado{connectedCount === 1 ? "" : "s"}</span></div>
      {loading ? <div className="loading-box">A carregar canais...</div> : <div className="channel-grid">{channels.map((channel) => {
        const Icon = icons[channel.key] || Link2;
        const label = statusLabels[channel.status] || channel.status;
        return <article className="channel-card" key={channel.key}>
          <div className="channel-card-top"><span className="channel-brand"><Icon size={24} /><strong>{channel.label}</strong></span><span className={`status-badge ${statusTone(channel.status)}`}>{label}</span></div>
          <p>{channelDescription(channel)}</p>
          <div className="channel-meta"><span>{channel.provider}</span>{channel.last_event_at && <span>Último evento: {new Date(channel.last_event_at).toLocaleString()}</span>}</div>
          {channel.last_error && <div className="channel-error"><AlertCircle size={14} />{channel.last_error}</div>}
          <button className={channel.status === "connected" ? "secondary-button" : "primary-button"} onClick={() => void handleAction(channel)} disabled={busy === channel.key}>
            {busy === channel.key ? "A actualizar..." : channel.status === "connected" ? "Desligar canal" : channel.key === "whatsapp" ? "Abrir ligação WhatsApp" : channel.requires_review ? "Ver requisitos" : "Preparar ligação"}
          </button>
        </article>;
      })}</div>}
    </section>
    <section className="data-panel channel-note"><div className="panel-heading"><div><span className="eyebrow">SEGURANÇA</span><h3>Uma integração não vê outra</h3></div><Clock3 size={19} /></div><p>Tokens, eventos e conversas são associados ao tenant autenticado. A plataforma não mostra segredos no frontend e os canais com aprovação pendente permanecem claramente identificados.</p></section>
  </div>;
}
