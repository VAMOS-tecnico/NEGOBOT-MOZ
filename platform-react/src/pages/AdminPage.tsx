import { useEffect, useState } from "react";
import { Activity, CheckCircle2, Database, Server, Settings2, Users } from "lucide-react";
import { api, type Overview, type Tenant } from "../lib/api";

type Health = Record<string, unknown>;

export function AdminPage() {
  const [overview, setOverview] = useState<Overview>({});
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [health, setHealth] = useState<Health>({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(true);

  async function load() {
    setBusy(true); setError("");
    try {
      const [overviewResult, tenantsResult, healthResult] = await Promise.all([api.admin.overview(), api.admin.tenants(), api.admin.health()]);
      setOverview(overviewResult); setTenants(tenantsResult.tenants || []); setHealth(healthResult);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível carregar a área administrativa."); }
    finally { setBusy(false); }
  }
  useEffect(() => { void load(); }, []);

  return <div className="content-stack"><div className="module-header"><div><span className="eyebrow">GESTÃO DA PLATAFORMA</span><h1>Administração</h1><p>Controla clientes, integrações e saúde da infraestrutura com uma visão isolada por permissões.</p></div><button className="secondary-button" onClick={() => void load()}><Activity size={16} /> Atualizar</button></div>{error && <div className="alert error">{error}</div>}<section className="stat-grid"><AdminStat label="Clientes" value={overview.tenants} icon={Users} /><AdminStat label="Utilizadores" value={overview.users} icon={Activity} /><AdminStat label="Ativos" value={overview.active_tenants} icon={CheckCircle2} /></section><div className="module-grid two"><section className="data-panel"><div className="panel-heading"><div><span className="eyebrow">TENANTS</span><h3>Clientes registados</h3></div><Users size={19} /></div>{busy ? <div className="loading-box">A carregar clientes...</div> : tenants.length ? <div className="data-list">{tenants.map((tenant) => <div className="data-row" key={tenant.id}><div className="avatar">{tenant.name.slice(0, 1).toUpperCase()}</div><div className="row-main"><strong>{tenant.name}</strong><small>{tenant.id} · {tenant.plan || "demonstração"}</small></div><span className={`status-badge ${tenant.status || "active"}`}>{tenant.status || "active"}</span></div>)}</div> : <div className="empty-state">Ainda não existem clientes.</div>}</section><section className="data-panel"><div className="panel-heading"><div><span className="eyebrow">INFRAESTRUTURA</span><h3>Estado dos serviços</h3></div><Server size={19} /></div><div className="health-list"><HealthItem label="Backend NEGOBOT" value={health.backend || health.status || "online"} icon={Server} /><HealthItem label="Firebase / Firestore" value={health.firebase || "configured"} icon={Database} /><HealthItem label="Evolution API" value={health.evolution || "online"} icon={Settings2} /></div></section></div></div>;
}

function AdminStat({ label, value, icon: Icon }: { label: string; value?: number; icon: typeof Activity }) { return <article className="stat-card"><div className="stat-top"><span>{label}</span><span className="icon-chip"><Icon size={17} /></span></div><strong>{value ?? "—"}</strong><small>Dados atualizados do Firestore</small></article>; }
function HealthItem({ label, value, icon: Icon }: { label: string; value: unknown; icon: typeof Activity }) { return <div className="health-item"><span className="quick-icon"><Icon size={17} /></span><div className="row-main"><strong>{label}</strong><small>{String(value)}</small></div><span className="status-dot" /></div>; }
