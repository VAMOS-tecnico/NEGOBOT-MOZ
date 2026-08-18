import { useEffect, useState, type FormEvent } from "react";
import { ArrowRight, Building2, CheckCircle2, Globe2, Loader2, QrCode, ShieldCheck } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { api, type BusinessProfile } from "../lib/api";

const emptyProfile: BusinessProfile = {
  empresa_nome: "",
  nicho: "",
  email_corporativo: "",
  redes_sociais: { facebook: "", instagram: "", twitter_x: "", tiktok: "", telegram: "", linkedin: "" },
  billing_region: "mozambique",
  selected_plan: "basico",
};

export function OnboardingPage() {
  const navigate = useNavigate();
  const [profile, setProfile] = useState<BusinessProfile>(emptyProfile);
  const [busy, setBusy] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    api.client.profile().then((result) => setProfile({ ...emptyProfile, ...result, redes_sociais: { ...emptyProfile.redes_sociais, ...(result.redes_sociais || {}) } })).catch((reason) => setError(reason instanceof Error ? reason.message : "Não foi possível carregar o onboarding.")).finally(() => setBusy(false));
  }, []);

  async function save(event: FormEvent) {
    event.preventDefault();
    if (profile.empresa_nome.trim().length < 2) { setError("Indica o nome da empresa ou do projecto."); return; }
    setSaving(true); setError(""); setNotice("");
    try {
      await api.client.updateProfile({ empresa_nome: profile.empresa_nome, nicho: profile.nicho, billing_region: profile.billing_region as "mozambique" | "international", selected_plan: profile.selected_plan });
      setNotice("Perfil guardado. O próximo passo é ligar o WhatsApp para começar a demonstração de 2 dias.");
      window.setTimeout(() => navigate("/whatsapp"), 900);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível guardar o perfil."); }
    finally { setSaving(false); }
  }

  if (busy) return <div className="content-stack"><div className="loading-box"><Loader2 size={18} className="spin" /> A preparar o teu espaço...</div></div>;

  return <div className="content-stack onboarding-page">
    <div className="module-header"><div><span className="eyebrow">PRIMEIROS PASSOS</span><h1>Vamos preparar o teu espaço</h1><p>São só alguns dados para personalizar a plataforma. Podes completar as redes sociais mais tarde.</p></div><div className="onboarding-progress"><span className="onboarding-step active">1</span><span /><span className="onboarding-step">2</span><span /><span className="onboarding-step">3</span></div></div>
    {error && <div className="alert error">{error}</div>}{notice && <div className="alert success"><CheckCircle2 size={16} />{notice}</div>}
    <div className="onboarding-grid"><form className="data-panel stack-form compact-form" onSubmit={save}><div className="panel-heading"><div><span className="eyebrow">PASSO 1 DE 3</span><h3>Conta e negócio</h3></div><Building2 size={20} /></div><label>Nome da empresa ou projecto<input value={profile.empresa_nome} onChange={(event) => setProfile({ ...profile, empresa_nome: event.target.value })} placeholder="Ex.: Maputo Digital, Lda." autoFocus required /></label><label>Área de negócio<small className="muted">Opcional; ajuda o assistente a responder melhor.</small><input value={profile.nicho} onChange={(event) => setProfile({ ...profile, nicho: event.target.value })} placeholder="Ex.: comércio, restauração, serviços" /></label><label>Onde vais pagar?<select value={profile.billing_region || "mozambique"} onChange={(event) => setProfile({ ...profile, billing_region: event.target.value as "mozambique" | "international" })}><option value="mozambique">Moçambique · M-Pesa / AutoPay</option><option value="international">Outro país · USD / Lemon Squeezy</option></select></label><label>Plano de interesse<small className="muted">Podes mudar de plano antes do pagamento.</small><select value={profile.selected_plan || "basico"} onChange={(event) => setProfile({ ...profile, selected_plan: event.target.value })}><option value="basico">Básico · {profile.billing_region === "international" ? "USD 8" : "500 MT"}</option><option value="medio">Médio · {profile.billing_region === "international" ? "USD 16" : "1.000 MT"}</option><option value="premium">Premium · {profile.billing_region === "international" ? "USD 24" : "1.500 MT"}</option></select></label><button className="primary-button" disabled={saving} type="submit">{saving ? "A guardar..." : "Guardar e ligar WhatsApp"} <ArrowRight size={16} /></button></form><aside className="onboarding-side"><section className="data-panel onboarding-trial-card"><div className="onboarding-icon"><ShieldCheck size={22} /></div><span className="eyebrow">DEMONSTRAÇÃO PARA TODOS</span><h3>2 dias sem compromisso</h3><p>O contador só começa quando o WhatsApp ficar ligado pela primeira vez. A região e o plano escolhido não alteram este benefício.</p><div className="onboarding-fact"><CheckCircle2 size={15} /> Não começa no registo</div><div className="onboarding-fact"><CheckCircle2 size={15} /> Não pode ser reiniciado</div><div className="onboarding-fact"><CheckCircle2 size={15} /> Moçambique e internacional</div></section><section className="data-panel onboarding-next-card"><div className="panel-heading"><div><span className="eyebrow">PASSO 2</span><h3>WhatsApp</h3></div><QrCode size={19} /></div><p>Depois de guardar o perfil, vais para a área do QR Code. Quando a Evolution confirmar o estado <strong>open</strong>, os 2 dias começam automaticamente.</p><button className="secondary-button" type="button" onClick={() => navigate("/whatsapp")}>Ver área WhatsApp <QrCode size={15} /></button></section></aside></div>
  </div>;
}
