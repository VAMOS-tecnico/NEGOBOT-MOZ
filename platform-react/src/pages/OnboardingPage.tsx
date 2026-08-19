import { useEffect, useState, type FormEvent } from "react";
import { ArrowRight, Building2, CheckCircle2, Globe2, Loader2, QrCode, Send, ShieldCheck } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { api, type BusinessProfile } from "../lib/api";

type TrialChannel = "whatsapp" | "telegram" | "instagram" | "facebook";

const emptyProfile: BusinessProfile = {
  empresa_nome: "",
  nicho: "",
  email_corporativo: "",
  redes_sociais: { facebook: "", instagram: "", twitter_x: "", tiktok: "", telegram: "", linkedin: "" },
  billing_region: "mozambique",
  selected_plan: "basico",
  preferred_trial_channel: "whatsapp",
};

const channelOptions: Array<{ id: TrialChannel; label: string; description: string; available: boolean; icon: typeof QrCode }> = [
  { id: "whatsapp", label: "WhatsApp", description: "Lê um QR Code e começa o teste quando ficar ligado.", available: true, icon: QrCode },
  { id: "telegram", label: "Telegram", description: "Liga o teu bot com o token do BotFather.", available: true, icon: Send },
  { id: "instagram", label: "Instagram", description: "Disponível após autorização da Meta.", available: false, icon: Globe2 },
  { id: "facebook", label: "Facebook", description: "Disponível após autorização da Meta.", available: false, icon: Globe2 },
];

export function OnboardingPage() {
  const navigate = useNavigate();
  const [profile, setProfile] = useState<BusinessProfile>(emptyProfile);
  const [preferredChannel, setPreferredChannel] = useState<TrialChannel>("whatsapp");
  const [busy, setBusy] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    api.client.profile().then((result) => {
      const merged = { ...emptyProfile, ...result, redes_sociais: { ...emptyProfile.redes_sociais, ...(result.redes_sociais || {}) } };
      setProfile(merged);
      if (["whatsapp", "telegram", "instagram", "facebook"].includes(String(result.preferred_trial_channel))) {
        setPreferredChannel(result.preferred_trial_channel as TrialChannel);
      }
    }).catch((reason) => setError(reason instanceof Error ? reason.message : "Não foi possível carregar o onboarding.")).finally(() => setBusy(false));
  }, []);

  async function save(event: FormEvent) {
    event.preventDefault();
    if (profile.empresa_nome.trim().length < 2) { setError("Indica o nome da empresa ou do projecto."); return; }
    setSaving(true); setError(""); setNotice("");
    try {
      await api.client.updateProfile({
        empresa_nome: profile.empresa_nome,
        nicho: profile.nicho,
        billing_region: profile.billing_region as "mozambique" | "international",
        selected_plan: profile.selected_plan,
        preferred_trial_channel: preferredChannel,
      });
      const destination = preferredChannel === "whatsapp" ? "/whatsapp" : "/canais";
      setNotice(preferredChannel === "whatsapp" ? "Perfil guardado. Liga o WhatsApp para começar a demonstração." : "Perfil guardado. Liga o canal escolhido para começar a demonstração.");
      window.setTimeout(() => navigate(destination), 900);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível guardar o perfil."); }
    finally { setSaving(false); }
  }

  if (busy) return <div className="content-stack"><div className="loading-box"><Loader2 size={18} className="spin" /> A preparar o teu espaço...</div></div>;

  return <div className="content-stack onboarding-page">
    <div className="module-header"><div><span className="eyebrow">PRIMEIROS PASSOS</span><h1>Vamos preparar o teu espaço</h1><p>São só alguns dados para personalizar a plataforma. Podes completar as redes sociais mais tarde.</p></div><div className="onboarding-progress"><span className="onboarding-step active">1</span><span /><span className="onboarding-step active">2</span><span /><span className="onboarding-step">3</span></div></div>
    {error && <div className="alert error">{error}</div>}{notice && <div className="alert success"><CheckCircle2 size={16} />{notice}</div>}
    <div className="onboarding-grid"><form className="data-panel stack-form compact-form" onSubmit={save}><div className="panel-heading"><div><span className="eyebrow">PASSO 1 DE 3</span><h3>Conta e negócio</h3></div><Building2 size={20} /></div><label>Nome da empresa ou projecto<input value={profile.empresa_nome} onChange={(event) => setProfile({ ...profile, empresa_nome: event.target.value })} placeholder="Ex.: Maputo Digital, Lda." autoFocus required /></label><label>Área de negócio<small className="muted">Opcional; ajuda o assistente a responder melhor.</small><input value={profile.nicho} onChange={(event) => setProfile({ ...profile, nicho: event.target.value })} placeholder="Ex.: comércio, restauração, serviços" /></label><label>Onde vais pagar?<select value={profile.billing_region || "mozambique"} onChange={(event) => setProfile({ ...profile, billing_region: event.target.value as "mozambique" | "international" })}><option value="mozambique">Moçambique · M-Pesa / AutoPay</option><option value="international">Outro país · USD / Lemon Squeezy</option></select></label><label>Plano de interesse<small className="muted">Podes mudar de plano antes do pagamento.</small><select value={profile.selected_plan || "basico"} onChange={(event) => setProfile({ ...profile, selected_plan: event.target.value })}><option value="basico">Básico · {profile.billing_region === "international" ? "USD 8" : "500 MT"}</option><option value="medio">Médio · {profile.billing_region === "international" ? "USD 16" : "1.000 MT"}</option><option value="premium">Premium · {profile.billing_region === "international" ? "USD 24" : "1.500 MT"}</option></select></label><button className="primary-button" disabled={saving} type="submit">{saving ? "A guardar..." : "Guardar e continuar"} <ArrowRight size={16} /></button></form><aside className="onboarding-side"><section className="data-panel onboarding-channel-card"><div className="panel-heading"><div><span className="eyebrow">PASSO 2 DE 3</span><h3>Qual canal queres testar primeiro?</h3></div><Globe2 size={19} /></div><div className="channel-choice-grid">{channelOptions.map(({ id, label, description, available, icon: Icon }) => <button key={id} type="button" disabled={!available} className={`channel-choice ${preferredChannel === id ? "selected" : ""} ${!available ? "disabled" : ""}`} onClick={() => available && setPreferredChannel(id)}><span className="channel-choice-icon"><Icon size={18} /></span><span><strong>{label}</strong><small>{description}</small></span>{!available && <em>Em breve</em>}</button>)}</div></section><section className="data-panel onboarding-trial-card"><div className="onboarding-icon"><ShieldCheck size={22} /></div><span className="eyebrow">DEMONSTRAÇÃO PARA TODOS</span><h3>2 dias Premium, uma só vez</h3><p>O relógio começa quando o primeiro canal ficar ligado. Os restantes canais partilham o tempo que sobrar; não existe um trial separado por canal.</p><div className="onboarding-fact"><CheckCircle2 size={15} /> Não começa no registo</div><div className="onboarding-fact"><CheckCircle2 size={15} /> Primeiro canal inicia o relógio</div><div className="onboarding-fact"><CheckCircle2 size={15} /> Não pode ser reiniciado</div></section><section className="data-panel onboarding-next-card"><div className="panel-heading"><div><span className="eyebrow">PASSO 3</span><h3>{preferredChannel === "whatsapp" ? "WhatsApp" : preferredChannel === "telegram" ? "Telegram" : "Autorização"}</h3></div><QrCode size={19} /></div><p>{preferredChannel === "whatsapp" ? "Depois de guardar, lê o QR Code. Quando a Evolution confirmar open, a Conta Central recebe os 2 dias Premium." : preferredChannel === "telegram" ? "Depois de guardar, abre Canais e liga o bot com o token que obtiveste no BotFather. A ligação inicia o mesmo trial central." : "Este canal ainda depende da aprovação e autorização do fornecedor. A escolha fica guardada no teu espaço."}</p><button className="secondary-button" type="button" onClick={() => navigate(preferredChannel === "whatsapp" ? "/whatsapp" : "/canais")}>Abrir ligação <ArrowRight size={15} /></button></section></aside></div>
  </div>;
}
