import { useEffect, useState, type FormEvent } from "react";
import { ArrowRight, Building2, CheckCircle2, Globe2, Loader2, QrCode, Send, ShieldCheck } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { usePlatformLanguage } from "../lib/platformLanguage";
import { api, type BusinessProfile } from "../lib/api";

type TrialChannel = "whatsapp" | "telegram" | "instagram" | "facebook";

type ChannelOption = { id: TrialChannel; pt: string; en: string; descriptionPt: string; descriptionEn: string; available: boolean; icon: typeof QrCode };

const emptyProfile: BusinessProfile = {
  empresa_nome: "",
  nicho: "",
  email_corporativo: "",
  redes_sociais: { facebook: "", instagram: "", twitter_x: "", tiktok: "", telegram: "", linkedin: "" },
  billing_region: "mozambique",
  selected_plan: "basico",
  preferred_trial_channel: "whatsapp",
};

const channelOptions: ChannelOption[] = [
  { id: "whatsapp", pt: "WhatsApp", en: "WhatsApp", descriptionPt: "Lê um QR Code e começa o teste quando ficar ligado.", descriptionEn: "Scan a QR Code and start the trial when it is connected.", available: true, icon: QrCode },
  { id: "telegram", pt: "Telegram", en: "Telegram", descriptionPt: "Liga o teu bot com o token do BotFather.", descriptionEn: "Connect your bot with the BotFather token.", available: true, icon: Send },
  { id: "instagram", pt: "Instagram", en: "Instagram", descriptionPt: "Disponível após autorização da Meta.", descriptionEn: "Available after Meta authorisation.", available: false, icon: Globe2 },
  { id: "facebook", pt: "Facebook", en: "Facebook", descriptionPt: "Disponível após autorização da Meta.", descriptionEn: "Available after Meta authorisation.", available: false, icon: Globe2 },
];

export function OnboardingPage() {
  const navigate = useNavigate();
  const { language } = usePlatformLanguage();
  const english = language === "en";
  const copy = (pt: string, en: string) => english ? en : pt;
  const [profile, setProfile] = useState<BusinessProfile>(emptyProfile);
  const [preferredChannel, setPreferredChannel] = useState<TrialChannel>("whatsapp");
  const [busy, setBusy] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    let cancelled = false;
    api.client.profile().then((result) => {
      if (cancelled) return;
      const merged = { ...emptyProfile, ...result, redes_sociais: { ...emptyProfile.redes_sociais, ...(result.redes_sociais || {}) } };
      setProfile(merged);
      if (["whatsapp", "telegram", "instagram", "facebook"].includes(String(result.preferred_trial_channel))) {
        setPreferredChannel(result.preferred_trial_channel as TrialChannel);
      }
    }).catch((reason) => {
      if (!cancelled) setError(reason instanceof Error ? reason.message : copy("Não foi possível carregar o onboarding.", "We could not load onboarding."));
    }).finally(() => { if (!cancelled) setBusy(false); });
    return () => { cancelled = true; };
  }, [english]);

  async function save(event: FormEvent) {
    event.preventDefault();
    if (profile.empresa_nome.trim().length < 2) {
      setError(copy("Indica o nome da empresa ou do projecto.", "Enter your company or project name."));
      return;
    }
    setSaving(true); setError(""); setNotice("");
    try {
      await api.client.updateProfile({
        empresa_nome: profile.empresa_nome.trim(),
        nicho: profile.nicho.trim(),
        billing_region: profile.billing_region as "mozambique" | "international",
        selected_plan: profile.selected_plan,
        preferred_trial_channel: preferredChannel,
      });
      const destination = preferredChannel === "whatsapp" ? "/whatsapp" : "/canais";
      setNotice(preferredChannel === "whatsapp"
        ? copy("Perfil guardado. Liga o WhatsApp para começar a demonstração.", "Profile saved. Connect WhatsApp to start your trial.")
        : copy("Perfil guardado. Liga o canal escolhido para começar a demonstração.", "Profile saved. Connect the selected channel to start your trial."));
      window.setTimeout(() => navigate(destination), 900);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : copy("Não foi possível guardar o perfil.", "We could not save your profile."));
    } finally { setSaving(false); }
  }

  if (busy) return <div className="content-stack"><div className="loading-box"><Loader2 size={18} className="spin" /> {copy("A preparar o teu espaço...", "Preparing your workspace...")}</div></div>;

  const selectedChannel = channelOptions.find((channel) => channel.id === preferredChannel);
  const nextTitle = preferredChannel === "whatsapp" ? "WhatsApp" : preferredChannel === "telegram" ? "Telegram" : copy("Autorização", "Authorisation");

  return <div className="content-stack onboarding-page">
    <div className="module-header"><div><span className="eyebrow">{copy("PRIMEIROS PASSOS", "GETTING STARTED")}</span><h1>{copy("Vamos preparar o teu espaço", "Let’s set up your workspace")}</h1><p>{copy("São só alguns dados para personalizar a plataforma. Podes completar as redes sociais mais tarde.", "Just a few details personalise the platform. You can add social profiles later.")}</p></div><div className="onboarding-progress" aria-label={copy("Progresso do onboarding", "Onboarding progress")}><span className="onboarding-step active">1</span><span /><span className="onboarding-step active">2</span><span /><span className="onboarding-step">3</span></div></div>
    {error && <div className="alert error" role="alert">{error}</div>}{notice && <div className="alert success" role="status"><CheckCircle2 size={16} />{notice}</div>}
    <div className="onboarding-grid"><form className="data-panel stack-form compact-form" onSubmit={save}><div className="panel-heading"><div><span className="eyebrow">{copy("PASSO 1 DE 3", "STEP 1 OF 3")}</span><h3>{copy("Conta e negócio", "Account and business")}</h3></div><Building2 size={20} /></div><label>{copy("Nome da empresa ou projecto", "Company or project name")}<input value={profile.empresa_nome} onChange={(event) => setProfile({ ...profile, empresa_nome: event.target.value })} placeholder={copy("Ex.: Maputo Digital, Lda.", "e.g. Maputo Digital Ltd.")} autoFocus required /></label><label>{copy("Área de negócio", "Business area")}<small className="muted">{copy("Opcional; ajuda o assistente a responder melhor.", "Optional; it helps the assistant answer better.")}</small><input value={profile.nicho} onChange={(event) => setProfile({ ...profile, nicho: event.target.value })} placeholder={copy("Ex.: comércio, restauração, serviços", "e.g. retail, hospitality, services")} /></label><label>{copy("Onde vais pagar?", "Where will you pay from?")}<select value={profile.billing_region || "mozambique"} onChange={(event) => setProfile({ ...profile, billing_region: event.target.value as "mozambique" | "international" })}><option value="mozambique">{copy("Moçambique · M-Pesa / AutoPay", "Mozambique · M-Pesa / AutoPay")}</option><option value="international">{copy("Outro país · USD / Lemon Squeezy", "Other country · USD / Lemon Squeezy")}</option></select></label><label>{copy("Plano de interesse", "Plan of interest")}<small className="muted">{copy("Podes mudar de plano antes do pagamento.", "You can change the plan before payment.")}</small><select value={profile.selected_plan || "basico"} onChange={(event) => setProfile({ ...profile, selected_plan: event.target.value })}><option value="basico">{copy("Básico", "Basic")} · {profile.billing_region === "international" ? "USD 8" : "500 MT"}</option><option value="medio">{copy("Médio", "Standard")} · {profile.billing_region === "international" ? "USD 16" : "1.000 MT"}</option><option value="premium">Premium · {profile.billing_region === "international" ? "USD 24" : "1.500 MT"}</option></select></label><button className="primary-button" disabled={saving} type="submit">{saving ? copy("A guardar...", "Saving...") : copy("Guardar e continuar", "Save and continue")} <ArrowRight size={16} /></button></form><aside className="onboarding-side"><section className="data-panel onboarding-channel-card"><div className="panel-heading"><div><span className="eyebrow">{copy("PASSO 2 DE 3", "STEP 2 OF 3")}</span><h3>{copy("Qual canal queres testar primeiro?", "Which channel do you want to test first?")}</h3></div><Globe2 size={19} /></div><div className="channel-choice-grid">{channelOptions.map(({ id, pt, en, descriptionPt, descriptionEn, available, icon: Icon }) => <button key={id} type="button" disabled={!available} aria-pressed={preferredChannel === id} className={`channel-choice ${preferredChannel === id ? "selected" : ""} ${!available ? "disabled" : ""}`} onClick={() => available && setPreferredChannel(id)}><span className="channel-choice-icon"><Icon size={18} /></span><span><strong>{english ? en : pt}</strong><small>{english ? descriptionEn : descriptionPt}</small></span>{!available && <em>{copy("Em breve", "Coming soon")}</em>}</button>)}</div></section><section className="data-panel onboarding-trial-card"><div className="onboarding-icon"><ShieldCheck size={22} /></div><span className="eyebrow">{copy("DEMONSTRAÇÃO PARA TODOS", "TRIAL FOR EVERYONE")}</span><h3>{copy("2 dias Premium, uma só vez", "2 Premium days, once per account")}</h3><p>{copy("O relógio começa quando o primeiro canal ficar ligado. Os restantes canais partilham o tempo que sobrar; não existe um trial separado por canal.", "The clock starts when the first channel is connected. Other channels share the remaining time; there is no separate trial per channel.")}</p><div className="onboarding-fact"><CheckCircle2 size={15} /> {copy("Não começa no registo", "It does not start at registration")}</div><div className="onboarding-fact"><CheckCircle2 size={15} /> {copy("Primeiro canal inicia o relógio", "The first channel starts the clock")}</div><div className="onboarding-fact"><CheckCircle2 size={15} /> {copy("Não pode ser reiniciado", "It cannot be restarted")}</div></section><section className="data-panel onboarding-next-card"><div className="panel-heading"><div><span className="eyebrow">{copy("PASSO 3", "STEP 3")}</span><h3>{nextTitle}</h3></div><QrCode size={19} /></div><p>{preferredChannel === "whatsapp" ? copy("Depois de guardar, lê o QR Code. Quando a Evolution confirmar open, a Conta Central recebe os 2 dias Premium.", "After saving, scan the QR Code. When Evolution confirms open, the Central Account receives the 2 Premium days.") : preferredChannel === "telegram" ? copy("Depois de guardar, abre Canais e liga o bot com o token que obtiveste no BotFather. A ligação inicia o mesmo trial central.", "After saving, open Channels and connect the bot with the token from BotFather. This starts the same central trial.") : copy("Este canal ainda depende da aprovação e autorização do fornecedor. A escolha fica guardada no teu espaço.", "This channel still depends on provider approval and authorisation. Your choice is saved in your workspace.")}</p><button className="secondary-button" type="button" onClick={() => navigate(preferredChannel === "whatsapp" ? "/whatsapp" : "/canais")}>{copy("Abrir ligação", "Open connection")} <ArrowRight size={15} /></button></section></aside></div>
    {selectedChannel && <p className="muted" style={{ marginTop: 0 }}>{copy("Canal seleccionado:", "Selected channel:")} {english ? selectedChannel.en : selectedChannel.pt}</p>}
  </div>;
}
