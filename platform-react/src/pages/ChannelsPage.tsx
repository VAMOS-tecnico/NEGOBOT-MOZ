import { useEffect, useMemo, useState } from "react";
import { AlertCircle, CheckCircle2, Clipboard, Clock3, ExternalLink, Eye, EyeOff, Link2, Loader2, Power, RefreshCw, X } from "lucide-react";
import { FaLinkedin } from "react-icons/fa";
import { SiFacebook, SiGmail, SiInstagram, SiTelegram, SiTiktok, SiWhatsapp, SiX } from "react-icons/si";
import type { IconType } from "react-icons";
import { api, type ClientChannel, type TelegramChannelInfo } from "../lib/api";
import { usePlatformLanguage } from "../lib/platformLanguage";

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
const statusLabelsEnglish: Record<ClientChannel["status"], string> = {
  connected: "Connected",
  not_configured: "Not configured yet",
  pending_authorization: "Waiting for authorisation",
  pending_review: "Waiting for review",
  disabled: "Disconnected",
  error: "Needs attention",
};

function statusTone(status: ClientChannel["status"]): string {
  if (status === "connected") return "active";
  if (status === "error") return "error";
  if (status === "pending_review" || status === "pending_authorization") return "pending";
  return "neutral";
}

function channelDescription(channel: ClientChannel, english: boolean): string {
  if (channel.key === "whatsapp") return english ? "Customer care, QR Code and the Negobot assistant through Evolution API." : "Atendimento, QR Code e assistente Negobot através da Evolution API.";
  if (channel.key === "telegram") return english ? "Messages through a Telegram bot owned by your business." : "Mensagens através de um bot Telegram próprio do teu negócio.";
  if (channel.key === "email") return english ? "Inbound and outbound email through SMTP or a transactional provider." : "Entrada e envio de email através de SMTP ou fornecedor transaccional.";
  if (channel.requires_review) return english ? `Available after ${channel.provider} authorisation and review.` : `Disponível mediante autorização e revisão do ${channel.provider}.`;
  return english ? `Integration through ${channel.provider}.` : `Integração através de ${channel.provider}.`;
}

export function ChannelsPage() {
  const { language } = usePlatformLanguage();
  const english = language === "en";
  const [channels, setChannels] = useState<ClientChannel[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [telegram, setTelegram] = useState<TelegramChannelInfo | null>(null);
  const [telegramOpen, setTelegramOpen] = useState(false);
  const [telegramToken, setTelegramToken] = useState("");
  const [telegramTokenVisible, setTelegramTokenVisible] = useState(false);
  const [telegramBusy, setTelegramBusy] = useState(false);
  const [telegramError, setTelegramError] = useState("");
  const [telegramNotice, setTelegramNotice] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const result = await api.client.channels();
      setChannels(result.channels || []);
      try { setTelegram(await api.client.telegramStatus()); } catch { setTelegram(null); }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Não foi possível carregar os canais.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, []);
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const result = params.get("oauth");
    const channel = params.get("channel");
    if (result === "success") setNotice(english ? `${channel || "Channel"} connected successfully.` : `${channel || "Canal"} ligado com sucesso.`);
    if (result === "error") setError(english ? `Could not complete ${channel || "channel"} authorisation.` : `Não foi possível concluir a autorização de ${channel || "canal"}.`);
    if (result) window.history.replaceState({}, document.title, window.location.pathname);
  }, [english]);

  const connectedCount = useMemo(() => channels.filter((channel) => channel.status === "connected").length, [channels]);

  async function handleAction(channel: ClientChannel) {
    setError("");
    setNotice("");
    if (channel.key === "whatsapp") {
      window.location.assign("/plataforma/whatsapp");
      return;
    }
    if (channel.key === "telegram" && channel.status !== "connected") {
      setTelegramOpen(true); setTelegramError(""); setTelegramNotice(""); return;
    }
    if (channel.status === "connected") {
      setBusy(channel.key);
      try {
        if (channel.key === "telegram") {
          await disconnectTelegram();
        } else if (channel.setup === "oauth" || channel.setup === "partner_oauth") {
          await api.client.disconnectOAuthChannel(channel.key);
          setNotice(english ? `${channel.label} disconnected from this workspace.` : `${channel.label} foi desligado neste tenant.`);
        } else {
          await api.client.updateChannel(channel.key, "disabled");
          setNotice(english ? `${channel.label} disconnected from this workspace.` : `${channel.label} foi desligado neste tenant.`);
        }
        await load();
      } catch (reason) {
        setError(reason instanceof Error ? reason.message : (english ? `Could not disconnect ${channel.label}.` : `Não foi possível desligar ${channel.label}.`));
      } finally {
        setBusy(null);
      }
      return;
    }
    if ((channel.setup === "oauth" || channel.setup === "partner_oauth") && channel.can_connect) {
      setBusy(channel.key);
      try {
        const result = await api.client.authorizeChannel(channel.key);
        window.location.assign(result.authorize_url);
      } catch (reason) {
        setError(reason instanceof Error ? reason.message : (english ? `Could not start ${channel.label} authorisation.` : `Não foi possível iniciar a autorização de ${channel.label}.`));
        setBusy(null);
      }
      return;
    }
    if (channel.requires_review) {
      setNotice(english ? `${channel.label} requires provider authorisation and review before receiving messages.` : `${channel.label} requer autorização e aprovação do fornecedor antes de receber mensagens.`);
      return;
    }
    setNotice(english ? `${channel.label} will be available after secure provider credentials are configured.` : `A ligação de ${channel.label} será activada quando as credenciais do fornecedor forem configuradas com segurança.`);
  }

  async function pasteTelegramToken() {
    try {
      const value = await navigator.clipboard.readText();
      if (value.trim()) setTelegramToken(value.trim());
      else setTelegramError("A área de transferência está vazia.");
    } catch {
      setTelegramError("O navegador não permitiu ler a área de transferência. Cola o token manualmente.");
    }
  }

  async function connectTelegram() {
    const token = telegramToken.trim();
    if (!token) { setTelegramError("Cola o token criado pelo BotFather."); return; }
    setTelegramBusy(true); setTelegramError(""); setTelegramNotice("");
    try {
      const result = await api.client.connectTelegram(token);
      setTelegram({ channel: "telegram", status: "connected", bot: result.bot, webhook_url: result.webhook_url, pending_update_count: result.pending_update_count, has_token: true });
      setTelegramToken(""); setTelegramOpen(false); setTelegramNotice(`Bot @${result.bot.username || result.bot.name || "Telegram"} ligado com sucesso.`);
      await load();
    } catch (reason) { setTelegramError(reason instanceof Error ? reason.message : "Não foi possível ligar o bot Telegram."); }
    finally { setTelegramBusy(false); }
  }

  async function disconnectTelegram() {
    setTelegramBusy(true); setTelegramError("");
    try { await api.client.disconnectTelegram(); setTelegram({ channel: "telegram", status: "disabled", bot: {}, has_token: false }); setTelegramNotice("Bot Telegram desligado neste tenant."); await load(); }
    catch (reason) { setTelegramError(reason instanceof Error ? reason.message : "Não foi possível desligar o bot Telegram."); }
    finally { setTelegramBusy(false); }
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
                  const label = (english ? statusLabelsEnglish[channel.status] : statusLabels[channel.status]) || channel.status;

        return <article className="channel-card" key={channel.key}>
          <div className="channel-card-top"><span className="channel-brand"><Icon size={24} /><strong>{channel.label}</strong></span><span className={`status-badge ${statusTone(channel.status)}`}>{label}</span></div>
          <p>{channelDescription(channel, english)}</p>
          <div className="channel-meta"><span>{channel.provider}</span>{channel.last_event_at && <span>{english ? "Last event" : "Último evento"}: {new Date(channel.last_event_at).toLocaleString()}</span>}</div>
          {channel.last_error && <div className="channel-error"><AlertCircle size={14} />{channel.last_error}</div>}
          <button className={channel.status === "connected" ? "secondary-button" : "primary-button"} onClick={() => void handleAction(channel)} disabled={busy === channel.key}>
            {busy === channel.key ? (english ? "Updating..." : "A actualizar...") : channel.status === "connected" ? (english ? "Disconnect channel" : "Desligar canal") : channel.key === "whatsapp" ? (english ? "Open WhatsApp connection" : "Abrir ligação WhatsApp") : (channel.setup === "oauth" || channel.setup === "partner_oauth") && channel.can_connect ? (english ? `Connect ${channel.label}` : `Ligar ${channel.label}`) : channel.requires_review ? (english ? "View requirements" : "Ver requisitos") : (english ? "Prepare connection" : "Preparar ligação")}
          </button>
        </article>;
      })}</div>}
    </section>
    <section className="data-panel channel-note"><div className="panel-heading"><div><span className="eyebrow">SEGURANÇA</span><h3>Uma integração não vê outra</h3></div><Clock3 size={19} /></div><p>Tokens, eventos e conversas são associados ao tenant autenticado. A plataforma não mostra segredos no frontend e os canais com aprovação pendente permanecem claramente identificados.</p></section>
    {telegramOpen && <div className="modal-backdrop" role="presentation" onClick={() => setTelegramOpen(false)}><section className="channel-modal" role="dialog" aria-modal="true" aria-labelledby="telegram-modal-title" onClick={(event) => event.stopPropagation()}><div className="panel-heading"><div><span className="eyebrow">LIGAÇÃO GUIADA</span><h3 id="telegram-modal-title">Ligar bot Telegram</h3></div><button className="icon-button" type="button" aria-label="Fechar" onClick={() => setTelegramOpen(false)}><X size={18} /></button></div><div className="telegram-steps"><div><span>1</span><p><strong>Criar o bot</strong><small>Abre o BotFather e envia <code>/newbot</code>.</small><a href="https://t.me/BotFather" target="_blank" rel="noreferrer">Abrir BotFather <ExternalLink size={13} /></a></p></div><div><span>2</span><p><strong>Copiar o token</strong><small>Depois de criar o bot, copia o token que o BotFather enviar.</small></p></div><div><span>3</span><p><strong>Colar e ligar</strong><small>A plataforma valida o token e regista o webhook automaticamente.</small></p></div></div><label className="telegram-token-field">Token do BotFather<div className="token-input-wrap"><input type={telegramTokenVisible ? "text" : "password"} value={telegramToken} onChange={(event) => setTelegramToken(event.target.value)} placeholder="123456789:AA..." autoComplete="off" spellCheck={false} /><button type="button" className="token-action" onClick={() => setTelegramTokenVisible((value) => !value)} aria-label={telegramTokenVisible ? "Ocultar token" : "Mostrar token"}>{telegramTokenVisible ? <EyeOff size={16} /> : <Eye size={16} />}</button></div></label><button className="secondary-button paste-token-button" type="button" onClick={() => void pasteTelegramToken()}><Clipboard size={16} /> Colar token da área de transferência</button><p className="security-note"><CheckCircle2 size={14} /> O token é enviado directamente por HTTPS para o backend e não fica guardado no navegador.</p>{telegramError && <div className="alert error"><AlertCircle size={15} />{telegramError}</div>}{telegramNotice && <div className="alert success"><CheckCircle2 size={15} />{telegramNotice}</div>}<div className="modal-actions"><button className="secondary-button" type="button" onClick={() => setTelegramOpen(false)}>Cancelar</button><button className="primary-button" type="button" disabled={telegramBusy || !telegramToken.trim()} onClick={() => void connectTelegram()}>{telegramBusy ? <><Loader2 size={16} className="spin" /> A ligar...</> : "Validar e ligar bot"}</button></div></section></div>}
  </div>;
}
