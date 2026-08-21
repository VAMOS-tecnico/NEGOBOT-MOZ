import { useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { Activity, Bot, Building2, CalendarClock, CheckCircle2, ChevronRight, CircleDollarSign, LayoutDashboard, LogOut, Megaphone, MessageCircle, QrCode, Send, Settings2, Smartphone, Sparkles, Users, Wifi, X } from "lucide-react";
import { api, type AuthState, type ClientPlan, type IntegrationStatus, type Overview, type PlatformUser } from "./lib/api";
import { AdminPage } from "./pages/AdminPage";
import { AssistantPage, BillingPage, BusinessProfilePage, CampaignsPage, ConversationsPage, MetricsPage, SupportPage, TeamPage, VideoPage, WhatsAppPage } from "./pages/ClientPages";
import { PublicAssistantPage, PublicSite } from "./pages/PublicSite";
import { ChannelsPage } from "./pages/ChannelsPage";
import { RenewalsPage } from "./pages/RenewalsPage";
import { OnboardingPage } from "./pages/OnboardingPage";
import { GroupsPage } from "./pages/GroupsPage";
import { LanguageToggle, PlatformLanguageProvider, usePlatformLanguage } from "./lib/platformLanguage";
import { ChannelPublicationsPage } from "./pages/ChannelPublicationsPage";
import { LegalPage } from "./pages/LegalPage";

type AuthContextValue = { auth: AuthState; refresh: () => Promise<void>; logout: () => Promise<void> };
const defaultAuth: AuthState = { authenticated: false, user: null };
const registrationPrices = { basico: { mt: "500 MT", usd: "$8" }, medio: { mt: "1.000 MT", usd: "$16" }, premium: { mt: "1.500 MT", usd: "$24" } } as const;

function LoginPage({ onLogin }: { onLogin: (user: PlatformUser) => void }) {
  const { language } = usePlatformLanguage(); const english = language === "en";
  const [identifier, setIdentifier] = useState(""); const [password, setPassword] = useState(""); const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  const loginPath = window.location.pathname.startsWith("/plataforma-react") ? "/plataforma-react/login" : "/plataforma/login";
  const forgotPath = window.location.pathname.startsWith("/plataforma-react") ? "/plataforma-react/forgot-password" : "/plataforma/forgot-password";
  async function submit(event: FormEvent) { event.preventDefault(); setError(""); setBusy(true); try { const result = await api.auth.login(identifier, password); onLogin(result.user); } catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível iniciar a sessão."); } finally { setBusy(false); } }
  return <main className="auth-shell"><section className="auth-card"><div className="auth-language"><LanguageToggle /></div><div className="brand-mark">N</div><span className="eyebrow">NEGOBOT-MOZ</span><h1>{english ? "WhatsApp automation centre" : "Centro de automação WhatsApp"}</h1><p className="muted">{english ? "Access your management workspace securely." : "Acede ao teu espaço de gestão com segurança."}</p><form onSubmit={submit} className="stack-form"><label>{english ? "Email or identifier" : "Email ou identificador"}<input value={identifier} onChange={(event) => setIdentifier(event.target.value)} placeholder={english ? "email@company.com or admin" : "email@empresa.co.mz ou admin"} autoComplete="username" /></label><label>{english ? "Password" : "Palavra-passe"}<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder={english ? "Enter your password" : "Introduz a palavra-passe"} autoComplete="current-password" /></label><p className="auth-footnote" style={{ textAlign: "right", marginTop: -8 }}><a href={forgotPath} style={{ color: "#8ce7b8" }}>{english ? "Forgot password?" : "Esqueceste a palavra-passe?"}</a></p>{error && <div className="alert error"><X size={16} />{error}</div>}<button className="primary-button" disabled={busy} type="submit">{busy ? (english ? "Signing in..." : "A autenticar...") : (english ? "Sign in to platform" : "Entrar na plataforma")}</button></form><p className="auth-footnote">{english ? "Each customer’s data is isolated by tenant." : "Os dados de cada cliente são isolados por tenant."}</p><p className="auth-footnote">{english ? "New here?" : "Ainda não tens conta?"} <a href="/plataforma/register" style={{ color: "#8ce7b8" }}>{english ? "Start the 2-day trial" : "Começa a demonstração de 2 dias"}</a>.</p></section></main>;
}

function ForgotPasswordPage() {
  const { language } = usePlatformLanguage(); const english = language === "en";
  const [email, setEmail] = useState(""); const [message, setMessage] = useState(""); const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  const loginPath = window.location.pathname.startsWith("/plataforma-react") ? "/plataforma-react/login" : "/plataforma/login";
  async function submit(event: FormEvent) { event.preventDefault(); setError(""); setMessage(""); setBusy(true); try { const result = await api.auth.forgotPassword(email); setMessage(english ? result.message_en : result.message_pt); } catch (reason) { setError(reason instanceof Error ? reason.message : (english ? "We could not process the request." : "Não foi possível processar o pedido.")); } finally { setBusy(false); } }
  return <main className="auth-shell"><section className="auth-card"><div className="auth-language"><LanguageToggle /></div><div className="brand-mark">N</div><span className="eyebrow">NEGOBOT-MOZ</span><h1>{english ? "Forgot password?" : "Esqueceste a palavra-passe?"}</h1><p className="muted">{english ? "Enter your platform email and we will send a secure reset link." : "Introduz o email da plataforma e enviaremos uma ligação segura para a troca."}</p><form onSubmit={submit} className="stack-form"><label>{english ? "Platform email" : "Email da plataforma"}<input type="email" required value={email} onChange={(event) => setEmail(event.target.value)} placeholder="email@company.com" autoComplete="email" /></label>{message && <div className="alert info"><CheckCircle2 size={16} />{message}</div>}{error && <div className="alert error"><X size={16} />{error}</div>}<button className="primary-button" disabled={busy} type="submit">{busy ? (english ? "Sending..." : "A enviar...") : (english ? "Send reset link" : "Enviar ligação de recuperação")}</button></form><p className="auth-footnote"><a href={loginPath} style={{ color: "#8ce7b8" }}>{english ? "Back to sign in" : "Voltar ao login"}</a></p></section></main>;
}

function ResetPasswordPage() {
  const { language } = usePlatformLanguage(); const english = language === "en";
  const token = new URLSearchParams(window.location.search).get("token") || "";
  const [password, setPassword] = useState(""); const [confirmation, setConfirmation] = useState(""); const [message, setMessage] = useState(""); const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  const loginPath = window.location.pathname.startsWith("/plataforma-react") ? "/plataforma-react/login" : "/plataforma/login";
  async function submit(event: FormEvent) { event.preventDefault(); setError(""); setMessage(""); if (!token) { setError(english ? "This reset link is missing its token." : "Esta ligação não tem um token válido."); return; } if (password.length < 8) { setError(english ? "Use at least 8 characters." : "Usa pelo menos 8 caracteres."); return; } if (password !== confirmation) { setError(english ? "The passwords do not match." : "As palavras-passe não coincidem."); return; } setBusy(true); try { const result = await api.auth.resetPassword(token, password); setMessage(english ? result.message_en : result.message_pt); } catch (reason) { setError(reason instanceof Error ? reason.message : (english ? "This reset link is invalid or expired." : "Esta ligação é inválida ou expirou.")); } finally { setBusy(false); } }
  return <main className="auth-shell"><section className="auth-card"><div className="auth-language"><LanguageToggle /></div><div className="brand-mark">N</div><span className="eyebrow">NEGOBOT-MOZ</span><h1>{english ? "Choose a new password" : "Escolhe uma nova palavra-passe"}</h1><p className="muted">{english ? "Your reset link is valid for a limited time and can be used once." : "A ligação de recuperação é temporária e só pode ser usada uma vez."}</p>{message ? <><div className="alert info"><CheckCircle2 size={16} />{message}</div><p className="auth-footnote"><a href={loginPath} style={{ color: "#8ce7b8" }}>{english ? "Go to sign in" : "Ir para o login"}</a></p></> : <form onSubmit={submit} className="stack-form"><label>{english ? "New password" : "Nova palavra-passe"}<input type="password" required minLength={8} value={password} onChange={(event) => setPassword(event.target.value)} placeholder={english ? "At least 8 characters" : "Mínimo de 8 caracteres"} autoComplete="new-password" /></label><label>{english ? "Confirm new password" : "Confirmar nova palavra-passe"}<input type="password" required minLength={8} value={confirmation} onChange={(event) => setConfirmation(event.target.value)} placeholder={english ? "Repeat the password" : "Repete a palavra-passe"} autoComplete="new-password" /></label>{error && <div className="alert error"><X size={16} />{error}</div>}<button className="primary-button" disabled={busy} type="submit">{busy ? (english ? "Saving..." : "A guardar...") : (english ? "Change password" : "Alterar palavra-passe")}</button></form>}</section></main>;
}

function RegisterPage({ onRegister }: { onRegister: (user: PlatformUser) => void }) {
  const { language } = usePlatformLanguage(); const english = language === "en";
  const params = new URLSearchParams(window.location.search);
  const inferredRegion = params.get("region") === "international" || params.get("lang") === "en" ? "international" : "mozambique";
  const inferredPlan = ["basico", "medio", "premium"].includes(params.get("plan") || "") ? params.get("plan") || undefined : undefined;
  const [email, setEmail] = useState(""); const [password, setPassword] = useState(""); const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  const loginPath = window.location.pathname.startsWith("/plataforma-react") ? "/plataforma-react/login" : "/plataforma/login";
  async function submit(event: FormEvent) {
    event.preventDefault(); setError(""); setBusy(true);
    try { const result = await api.auth.register({ email, password, billing_region: inferredRegion, plan_id: inferredPlan }); onRegister(result.user); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível criar a conta."); }
    finally { setBusy(false); }
  }
  return <main className="auth-shell"><section className="auth-card"><div className="auth-language"><LanguageToggle /></div><div className="brand-mark">N</div><span className="eyebrow">{english ? "START WITH NEGOBOT-MOZ" : "COMEÇA COM NEGOBOT-MOZ"}</span><h1>{english ? "Get started in seconds" : "Entra em segundos"}</h1><p className="muted">{english ? "Create access with just your email and password. We will complete your workspace together." : "Cria o acesso com apenas email e palavra-passe. Depois completamos o teu espaço juntos."}</p><form onSubmit={submit} className="stack-form"><label>{english ? "Access email" : "Email de acesso"}<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="email@company.com" autoComplete="email" required /></label><label>{english ? "Password" : "Palavra-passe"}<input type="password" minLength={8} value={password} onChange={(event) => setPassword(event.target.value)} placeholder={english ? "At least 8 characters" : "Mínimo de 8 caracteres"} autoComplete="new-password" required /></label>{error && <div className="alert error"><X size={16} />{error}</div>}<button className="primary-button" disabled={busy} type="submit">{busy ? (english ? "Creating access..." : "A criar o acesso...") : (english ? "Create free access" : "Criar acesso gratuito")}</button></form><div className="alert info"><CheckCircle2 size={16} />{english ? "The 2-day trial is for everyone and starts when you connect WhatsApp." : "A demonstração de 2 dias é para todos e só começa quando ligares o WhatsApp."}</div><p className="auth-footnote">{english ? "After signing in, choose your country, plan and business details. WhatsApp is connected separately through a QR Code." : "Depois da entrada, escolhes país, plano e dados da empresa. O número WhatsApp é ligado separadamente por QR Code."}</p><p className="auth-footnote">{english ? "Already have an account?" : "Já tens conta?"} <a href={loginPath} style={{ color: "#8ce7b8" }}>{english ? "Sign in to platform" : "Entrar na plataforma"}</a>.</p></section></main>;
}
function ProtectedRoute({ auth, children }: { auth: AuthState; children: ReactNode }) { if (!auth.authenticated) return <Navigate to="/login" replace />; return <>{children}</>; }

function AppShell({ user, onLogout, children }: { user: PlatformUser; onLogout: () => void; children: ReactNode }) {
  const location = useLocation();
  const navigate = useNavigate();
  const { language } = usePlatformLanguage();
  const english = language === "en";
  const isAdmin = user.role === "owner" || user.role === "admin";
  const [trialPlan, setTrialPlan] = useState<ClientPlan | null>(null);
  useEffect(() => {
    if (isAdmin) { setTrialPlan(null); return; }
    let cancelled = false;
    api.client.plan().then((result) => { if (!cancelled) setTrialPlan(result); }).catch(() => { if (!cancelled) setTrialPlan(null); });
    return () => { cancelled = true; };
  }, [isAdmin]);
  const trialPending = !isAdmin && trialPlan?.trial_status === "trial_pending_connection";
  const displayName = english && ["Administrador", "Administradora"].includes(user.name) ? "Administrator" : user.name;
  const clientNavigation = [
    { label: english ? "Overview" : "Visão geral", path: "/", icon: LayoutDashboard },
    { label: english ? "Conversations" : "Conversas", path: "/conversas", icon: MessageCircle },
    { label: english ? "Campaigns" : "Campanhas", path: "/campanhas", icon: Send },
    { label: "WhatsApp", path: "/whatsapp", icon: QrCode },
    { label: english ? "Channels" : "Canais", path: "/canais", icon: Smartphone },
    { label: english ? "Publications" : "Publicações", path: "/publicacoes", icon: Megaphone },
    { label: english ? "Own groups" : "Grupos próprios", path: "/grupos", icon: Users },
    { label: english ? "Business & networks" : "Empresa e redes", path: "/empresa", icon: Building2 },
    { label: english ? "Team" : "Equipa", path: "/equipa", icon: Users },
    { label: english ? "Assistant" : "Assistente", path: "/assistente", icon: Bot },
    { label: english ? "Metrics" : "Métricas", path: "/metricas", icon: Activity },
    { label: english ? "Videos" : "Vídeos", path: "/videos", icon: Send },
    { label: english ? "Support" : "Suporte", path: "/suporte", icon: MessageCircle },
    { label: english ? "Plan & billing" : "Plano e pagamentos", path: "/plano", icon: CircleDollarSign },
    { label: english ? "Get started" : "Começar", path: "/onboarding", icon: Sparkles },
  ];
  const adminNavigation = [
    { label: english ? "Overview" : "Visão geral", path: "/", icon: LayoutDashboard },
    { label: english ? "Administration" : "Administração", path: "/admin", icon: Settings2 },
    { label: english ? "Renewals" : "Renovações", path: "/renovacoes", icon: CalendarClock },
  ];
  const navigation = isAdmin ? adminNavigation : clientNavigation;
  return <div className="app-frame"><aside className="sidebar"><button className="brand-lockup" onClick={() => navigate("/")}><span className="brand-mark small">N</span><span><strong>NEGOBOT</strong><small>MOZ PLATFORM</small></span></button><div className="workspace-card"><span className="status-dot" />{isAdmin ? (english ? "Administrator view" : "Visão do administrador") : (english ? "Customer workspace" : "Espaço do cliente")}</div><nav className="sidebar-nav"><span className="nav-heading">{english ? "Platform" : "Plataforma"}</span>{navigation.map(({ label, path, icon: Icon }) => <button key={path} className={`nav-item ${location.pathname === path ? "active" : ""}`} onClick={() => navigate(path)}><Icon size={18} /><span>{label}</span><ChevronRight size={14} className="nav-chevron" /></button>)}</nav><div className="sidebar-bottom"><div className="user-mini"><div className="avatar">{(user.name || "N").slice(0, 1).toUpperCase()}</div><div><strong>{displayName}</strong><small>{english && user.role === "admin" ? "administrator" : english && user.role === "owner" ? "owner" : user.role}</small></div></div><button className="nav-item logout" onClick={onLogout}><LogOut size={18} /><span>{english ? "Sign out" : "Sair"}</span></button></div></aside><div className="main-column"><header className="topbar"><div><span className="eyebrow">{english ? "MANAGEMENT WORKSPACE" : "ESPAÇO DE GESTÃO"}</span><h2>{english ? "Hello" : "Olá"}, {displayName.split(" ")[0]}</h2></div><div className="topbar-actions"><LanguageToggle /><div className="live-pill"><span className="status-dot" />{english ? "System operational" : "Sistema operacional"}</div><div className="avatar large">{(displayName || "N").slice(0, 1).toUpperCase()}</div></div></header>{trialPending && <section className="trial-pending-banner"><div className="trial-pending-icon"><QrCode size={19} /></div><div><span className="eyebrow">{english ? "TRIAL PENDING" : "TRIAL PENDENTE"}</span><strong>{english ? "Connect WhatsApp to activate your 2-day Premium trial" : "Ligue o seu WhatsApp para activar os seus 2 dias de teste Premium"}</strong><small>{english ? "Your trial has not started yet. It begins only after the connected instance is confirmed online." : "O seu teste ainda não começou. Só começa depois de a instância ligada ser confirmada online."}</small></div><button className="primary-button" onClick={() => navigate("/whatsapp")}>{english ? "Connect WhatsApp now" : "Ligar WhatsApp agora"}<ChevronRight size={16} /></button></section>}<main className="page-content">{children}</main></div></div>;
}
function StatCard({ label, value, caption, icon: Icon, tone = "green" }: { label: string; value: string; caption: string; icon: typeof Activity; tone?: string }) { return <article className={`stat-card ${tone}`}><div className="stat-top"><span>{label}</span><span className="icon-chip"><Icon size={17} /></span></div><strong>{value}</strong><small>{caption}</small></article>; }
function OverviewPage({ user }: { user: PlatformUser }) {
  const { language } = usePlatformLanguage();
  const english = language === "en";
  const [overview, setOverview] = useState<Overview>({});
  const [plan, setPlan] = useState<ClientPlan | null>(null);
  const [integration, setIntegration] = useState<IntegrationStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const isAdmin = user.role === "owner" || user.role === "admin";
  const navigate = useNavigate();
  useEffect(() => { let cancelled = false; async function load() { try { if (isAdmin) { const result = await api.admin.overview(); if (!cancelled) setOverview(result); } else { const [overviewResult, planResult, integrationResult] = await Promise.all([api.client.overview(), api.client.plan(), api.client.integrationStatus()]); if (!cancelled) { setOverview(overviewResult); setPlan(planResult); setIntegration(integrationResult); } } } finally { if (!cancelled) setLoading(false); } } void load(); return () => { cancelled = true; }; }, [isAdmin]);
  const status = integration?.state || "disconnected";
  const onboardingIncomplete = !isAdmin && overview.tenant?.profile_completed !== true;
  return <div className="content-stack">
    <section className="hero-panel"><div><span className="eyebrow">{english ? "MAIN DASHBOARD" : "PAINEL PRINCIPAL"}</span><h1>{isAdmin ? (english ? "Central platform control" : "Controlo central da plataforma") : (english ? "Your automation in one place" : "A tua automação num só lugar")}</h1><p>{isAdmin ? (english ? "Monitor customers, integrations and operations from this centre." : "Acompanha clientes, integrações e operação sem sair deste centro.") : (english ? "Manage contacts, campaigns and your WhatsApp assistant in one simple workspace." : "Gere contactos, campanhas e o teu assistente WhatsApp com uma experiência simples.")}</p></div><div className="hero-orb"><Bot size={54} /></div></section>
    <section className="stat-grid">{isAdmin ? <><StatCard label={english ? "Customers" : "Clientes"} value={loading ? "—" : String(overview.tenants || 0)} caption={english ? "Registered tenants" : "Tenants registados"} icon={Users} /><StatCard label={english ? "Users" : "Utilizadores"} value={loading ? "—" : String(overview.users || 0)} caption={english ? "Platform accounts" : "Contas da plataforma"} icon={Activity} tone="blue" /><StatCard label={english ? "Active" : "Ativos"} value={loading ? "—" : String(overview.active_tenants || 0)} caption={english ? "Customers in operation" : "Clientes em operação"} icon={CheckCircle2} tone="violet" /></> : <><StatCard label={english ? "Current plan" : "Plano atual"} value={plan?.plan_name || (english ? "Trial" : "Demonstração")} caption={plan?.status || (english ? "Loading status" : "A carregar estado")} icon={CircleDollarSign} /><StatCard label={english ? "Contacts" : "Contactos"} value={loading ? "—" : String(overview.contacts || 0)} caption={english ? "Contacts with opt-in" : "Contactos com opt-in"} icon={Users} tone="blue" /><StatCard label="WhatsApp" value={status === "open" ? (english ? "Connected" : "Ligado") : (english ? "Not connected" : "Não ligado")} caption={integration?.instance_name || (english ? "Connect your number" : "Liga o teu número")} icon={Wifi} tone={status === "open" ? "blue" : "amber"} /></>}</section>
    {!isAdmin && integration?.services && <section className="data-panel" style={{ marginTop: 18 }}><div className="panel-heading"><div><span className="eyebrow">{english ? "SERVICE CONNECTIONS" : "LIGAÇÕES DO SISTEMA"}</span><h3>{english ? "Your workspace services" : "Serviços do teu espaço"}</h3></div><Activity size={19} /></div><div className="tag-row">{Object.entries(integration.services).map(([key, service]) => <span className={`status-badge ${service.status}`} key={key}>{service.label}: {service.status === "online" || service.status === "configured" ? (english ? "ready" : "pronto") : service.status === "not_configured" ? (english ? "setup needed" : "configuração necessária") : service.status === "offline" ? (english ? "offline" : "offline") : (english ? "checking" : "a verificar")}</span>)}</div></section>}
    {onboardingIncomplete && <section className="onboarding-mini-banner"><div className="onboarding-icon"><Sparkles size={19} /></div><div><span className="eyebrow">{english ? "NEXT STEP" : "PRÓXIMO PASSO"}</span><strong>{english ? "Complete your workspace before connecting WhatsApp" : "Completa o teu espaço antes de ligar o WhatsApp"}</strong><small>{english ? "It takes less than a minute. The 2-day trial starts after the real connection." : "Leva menos de um minuto. A demonstração de 2 dias só começa depois da ligação real."}</small></div><button className="primary-button" onClick={() => navigate("/onboarding")}>{english ? "Get started" : "Começar"} <ArrowRightIcon /></button></section>}
    <section className="section-heading"><div><span className="eyebrow">{english ? "QUICK ACCESS" : "ACESSO RÁPIDO"}</span><h3>{english ? "Continue your work" : "Continua o teu trabalho"}</h3></div></section>
    <section className="quick-grid"><QuickAction icon={MessageCircle} title={english ? "Conversations" : "Conversas"} text={english ? "Monitor and reply to your contacts." : "Acompanha e responde aos teus contactos."} path="/conversas" /><QuickAction icon={QrCode} title={english ? "Connect WhatsApp" : "Ligar WhatsApp"} text={english ? "Generate the QR Code for your instance." : "Gera o QR Code da tua instância."} path="/whatsapp" /><QuickAction icon={Smartphone} title={english ? "Channels" : "Canais"} text={english ? "Connect and monitor your digital channels." : "Liga e acompanha os teus canais digitais."} path="/canais" /><QuickAction icon={CircleDollarSign} title={english ? "Plan & billing" : "Plano e pagamentos"} text={english ? "Review benefits and validate M-Pesa." : "Consulta benefícios e valida M-Pesa."} path="/plano" /></section>
  </div>;
}
function ArrowRightIcon() { return <ChevronRight size={16} />; }
function QuickAction({ icon: Icon, title, text, path }: { icon: typeof MessageCircle; title: string; text: string; path: string }) { const navigate = useNavigate(); return <button className="quick-card" onClick={() => navigate(path)}><span className="quick-icon"><Icon size={22} /></span><span><strong>{title}</strong><small>{text}</small></span><ChevronRight size={17} /></button>; }
function TenantRoute({ user, children }: { user: PlatformUser; children: ReactNode }) {
  const hasTenant = (user.role === "client" || user.role === "operator") && Boolean(user.tenant_id);
  return hasTenant ? <>{children}</> : <Navigate to={user.role === "owner" || user.role === "admin" ? "/admin" : "/login"} replace />;
}

function PlatformRouter({ user, onLogout }: { user: PlatformUser; onLogout: () => void }) { return <AppShell user={user} onLogout={onLogout}><Routes><Route index element={<OverviewPage user={user} />} /><Route path="conversas" element={<TenantRoute user={user}><ConversationsPage /></TenantRoute>} /><Route path="campanhas" element={<TenantRoute user={user}><CampaignsPage /></TenantRoute>} /><Route path="whatsapp" element={<TenantRoute user={user}><WhatsAppPage /></TenantRoute>} /><Route path="empresa" element={<TenantRoute user={user}><BusinessProfilePage /></TenantRoute>} /><Route path="equipa" element={<TenantRoute user={user}><TeamPage /></TenantRoute>} />
  <Route path="assistente" element={<TenantRoute user={user}><AssistantPage /></TenantRoute>} /><Route path="metricas" element={<TenantRoute user={user}><MetricsPage /></TenantRoute>} /><Route path="videos" element={<TenantRoute user={user}><VideoPage /></TenantRoute>} /><Route path="suporte" element={<TenantRoute user={user}><SupportPage /></TenantRoute>} /><Route path="canais" element={<TenantRoute user={user}><ChannelsPage /></TenantRoute>} /><Route path="publicacoes" element={<TenantRoute user={user}><ChannelPublicationsPage /></TenantRoute>} /><Route path="grupos" element={<TenantRoute user={user}><GroupsPage /></TenantRoute>} />

<Route path="plano" element={<TenantRoute user={user}><BillingPage /></TenantRoute>} /><Route path="onboarding" element={(user.role === "client" || user.role === "operator") && user.tenant_id ? <OnboardingPage /> : <Navigate to={user.role === "owner" || user.role === "admin" ? "/admin" : "/"} replace />} /><Route path="admin" element={(user.role === "owner" || user.role === "admin") ? <AdminPage /> : <Navigate to="/" replace />} /><Route path="renovacoes" element={(user.role === "owner" || user.role === "admin") ? <RenewalsPage /> : <Navigate to="/" replace />} /><Route path="*" element={<Navigate to="/" replace />} /></Routes></AppShell>; }

function PlatformApp() {
  return <PlatformLanguageProvider><PlatformAppInner /></PlatformLanguageProvider>;
}

function PlatformAppInner() {
  const { language } = usePlatformLanguage();
  const appBasePath = window.location.pathname.startsWith("/plataforma-react") ? "/plataforma-react" : "/plataforma"; const [auth, setAuth] = useState<AuthState>(defaultAuth); const [loading, setLoading] = useState(true);
  useEffect(() => { let active = true; const timeout = new Promise<AuthState>((resolve) => window.setTimeout(() => resolve(defaultAuth), 8000)); Promise.race([api.auth.me(), timeout]).then((result) => { if (active) setAuth(result); }).catch(() => { if (active) setAuth(defaultAuth); }).finally(() => { if (active) setLoading(false); }); return () => { active = false; }; }, []);
  const authValue = useMemo(() => ({ auth, refresh: async () => setAuth(await api.auth.me()), logout: async () => { await api.auth.logout(); setAuth(defaultAuth); } }), [auth]);
  if (loading) return <main className="loading-shell"><div className="spinner" /><span>{language === "en" ? "Loading platform..." : "A carregar a plataforma..."}</span></main>;
  return <BrowserRouter basename={appBasePath}><Routes><Route path="/login" element={auth.authenticated ? <Navigate to="/" replace /> : <LoginPage onLogin={(user) => setAuth({ authenticated: true, user })} />} /><Route path="/forgot-password" element={auth.authenticated ? <Navigate to="/" replace /> : <ForgotPasswordPage />} /><Route path="/reset-password" element={auth.authenticated ? <Navigate to="/" replace /> : <ResetPasswordPage />} /><Route path="/register" element={auth.authenticated ? <Navigate to="/" replace /> : <RegisterPage onRegister={(user) => setAuth({ authenticated: true, user })} />} /><Route path="/*" element={<ProtectedRoute auth={auth}><PlatformRouter user={authValue.auth.user!} onLogout={() => void authValue.logout()} /></ProtectedRoute>} /></Routes></BrowserRouter>;
}

export default function App() {
  const path = window.location.pathname;
  if (path === "/assistente" || path === "/assistente/") return <PublicAssistantPage />;
  if (path === "/terms" || path === "/terms/") return <LegalPage kind="terms" />;
  if (path === "/privacy" || path === "/privacy/") return <LegalPage kind="privacy" />;
  if (!path.startsWith("/plataforma")) return <PublicSite />;
  return <PlatformApp />;
}
