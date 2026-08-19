import { useEffect, useState } from "react";
import { CheckCircle2, HelpCircle, Loader2, MessageCircle, Plus, RefreshCw, Save, ShieldCheck, Users, XCircle } from "lucide-react";
import { api, type GroupKeyword, type WhatsAppGroup } from "../lib/api";
import { usePlatformLanguage } from "../lib/platformLanguage";

function ErrorBox({ message }: { message: string }) { return <div className="alert error"><XCircle size={16} />{message}</div>; }
function SuccessBox({ message }: { message: string }) { return <div className="alert success"><CheckCircle2 size={16} />{message}</div>; }
function LoadingBox() { return <div className="loading-box"><Loader2 size={18} className="spin" /> A carregar grupos...</div>; }

function groupStatus(group: WhatsAppGroup, english: boolean) {
  if (!group.admin_verified || !group.bot_is_admin) return english ? "Blocked: this WhatsApp is not an administrator" : "Bloqueado: esta instância não é administradora";
  if (!group.automation_enabled) return english ? "Verified, automation is off" : "Verificado, automação desligada";
  return english ? "Active and managed by your WhatsApp" : "Activo e administrado pelo teu WhatsApp";
}

export function GroupsPage() {
  const { language } = usePlatformLanguage();
  const english = language === "en";
  const [groups, setGroups] = useState<WhatsAppGroup[]>([]);
  const [busy, setBusy] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [saving, setSaving] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [keywordDrafts, setKeywordDrafts] = useState<Record<string, { trigger: string; response: string }>>({});

  async function load() {
    setBusy(true); setError("");
    try { const result = await api.client.groups(); setGroups(result.groups || []); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível carregar os grupos."); }
    finally { setBusy(false); }
  }
  useEffect(() => { void load(); }, []);

  async function sync() {
    setSyncing(true); setError(""); setNotice("");
    try { const result = await api.client.syncGroups(); setGroups(result.groups || []); setNotice(`${result.verified} grupo(s) verificado(s) como administrado(s). ${result.total} grupo(s) foram encontrados.`); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível sincronizar grupos."); }
    finally { setSyncing(false); }
  }

  async function update(group: WhatsAppGroup, fields: Parameters<typeof api.client.updateGroup>[1], success = "Configuração do grupo guardada.") {
    setSaving(group.id); setError(""); setNotice("");
    try { const result = await api.client.updateGroup(group.id, fields); setGroups((current) => current.map((item) => item.id === group.id ? { ...item, ...result.changes } : item)); setNotice(success); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível guardar o grupo."); }
    finally { setSaving(null); }
  }

  function addKeyword(group: WhatsAppGroup) {
    const draft = keywordDrafts[group.id] || { trigger: "", response: "" };
    if (!draft.trigger.trim() || !draft.response.trim()) return;
    const keywords = [...(group.keywords || []), { trigger: draft.trigger.trim(), response: draft.response.trim() }];
    setKeywordDrafts((current) => ({ ...current, [group.id]: { trigger: "", response: "" } }));
    void update(group, { keywords });
  }

  function removeKeyword(group: WhatsAppGroup, index: number) {
    void update(group, { keywords: (group.keywords || []).filter((_, itemIndex) => itemIndex !== index) });
  }

  return <div className="content-stack">
    <div className="module-header"><div><span className="eyebrow">WHATSAPP · GRUPOS PRÓPRIOS</span><h1>Gestão e automação em grupos</h1><p>Só podes activar automação em grupos onde a instância conectada foi confirmada como administradora. Grupos de terceiros permanecem bloqueados.</p></div><button className="secondary-button compact" onClick={() => void sync()} disabled={syncing}><RefreshCw size={16} className={syncing ? "spin" : ""} /> {syncing ? "A sincronizar..." : "Sincronizar grupos"}</button></div>
    {error && <ErrorBox message={error} />}{notice && <SuccessBox message={notice} />}
    <section className="data-panel group-safety-banner"><ShieldCheck size={24} /><div><strong>Regra de segurança activa</strong><p>A plataforma consulta os participantes na Evolution API e só aceita um grupo quando o teu WhatsApp aparece com `isAdmin` ou `isSuperAdmin`. A lista de membros nunca é convertida em contactos de marketing.</p></div></section>
    {busy ? <LoadingBox /> : groups.length ? <div className="group-management-grid">{groups.map((group) => { const draft = keywordDrafts[group.id] || { trigger: "", response: "" }; const verified = Boolean(group.admin_verified && group.bot_is_admin && group.status === "active"); return <article className={`data-panel group-card ${verified ? "verified" : "rejected"}`} key={group.id}><div className="panel-heading"><div><span className="eyebrow">{verified ? "GRUPO PRÓPRIO VERIFICADO" : "GRUPO BLOQUEADO"}</span><h3>{group.name || "Grupo WhatsApp"}</h3><small>{group.group_jid} · {group.participant_count || 0} participantes</small></div><div className="group-status-icon">{verified ? <ShieldCheck size={21} /> : <XCircle size={21} />}</div></div><p className="group-status-text">{groupStatus(group, english)}</p>{!verified && <details className="group-help"><summary><HelpCircle size={15} />{english ? "How to give Admin permission on WhatsApp" : "Como dar permissão de Admin no WhatsApp"}</summary><ol><li>{english ? "Open the group on WhatsApp and tap the group name." : "Abre o grupo no WhatsApp e toca no nome do grupo."}</li><li>{english ? "Open Group permissions or Group settings." : "Abre as permissões ou definições do grupo."}</li><li>{english ? "Promote the connected NEGOBOT number to administrator, then sync groups again." : "Promove o número NEGOBOT ligado a administrador e sincroniza os grupos novamente."}</li></ol></details>}{verified ? <><label className="check-card"><input type="checkbox" checked={Boolean(group.automation_enabled)} disabled={saving === group.id} onChange={(event) => void update(group, { automation_enabled: event.target.checked }, event.target.checked ? "Automação activada neste grupo próprio." : "Automação desligada neste grupo.")} />Activar automação neste grupo</label><label className="check-card"><input type="checkbox" checked={group.mention_required !== false} disabled={saving === group.id} onChange={(event) => void update(group, { mention_required: event.target.checked })} />Exigir menção `@Bot` ou comando directo</label><label className="check-card"><input type="checkbox" checked={Boolean(group.welcome_enabled)} disabled={saving === group.id} onChange={(event) => void update(group, { welcome_enabled: event.target.checked })} />Enviar boas-vindas quando entram novos membros</label><label>Mensagem de boas-vindas<textarea rows={3} value={group.welcome_message || ""} disabled={saving === group.id} onChange={(event) => setGroups((current) => current.map((item) => item.id === group.id ? { ...item, welcome_message: event.target.value } : item))} onBlur={() => void update(group, { welcome_message: group.welcome_message || "" })} placeholder="Bem-vindo(a)! Escreve @Bot para pedir ajuda." /></label><div className="keyword-section"><div className="panel-heading"><div><span className="eyebrow">KEYWORDS</span><strong>Respostas rápidas</strong></div><MessageCircle size={18} /></div>{(group.keywords || []).map((keyword: GroupKeyword, index: number) => <div className="keyword-row" key={`${keyword.trigger}-${index}`}><span><b>{keyword.trigger}</b><small>{keyword.response}</small></span><button title="Remover keyword" onClick={() => removeKeyword(group, index)}>×</button></div>)}<div className="keyword-form"><input value={draft.trigger} onChange={(event) => setKeywordDrafts((current) => ({ ...current, [group.id]: { ...draft, trigger: event.target.value } }))} placeholder="Ex.: preço" /><input value={draft.response} onChange={(event) => setKeywordDrafts((current) => ({ ...current, [group.id]: { ...draft, response: event.target.value } }))} placeholder="Resposta curta e segura" /><button className="secondary-button compact" type="button" disabled={saving === group.id} onClick={() => addKeyword(group)}><Plus size={15} /> Adicionar</button></div></div><button className="secondary-button compact" type="button" disabled={saving === group.id} onClick={() => void update(group, { welcome_message: group.welcome_message || "" })}><Save size={15} /> Guardar alterações</button></> : <div className="alert warning"><XCircle size={16} />Este grupo não pode receber automação. Sincroniza novamente depois de ligares a instância num grupo onde ela seja administradora.</div>}</article>; })}</div> : <section className="data-panel empty-state"><Users size={24} /><p>Ainda não existem grupos sincronizados.</p><button className="primary-button" onClick={() => void sync()} disabled={syncing}>Encontrar grupos próprios</button></section>}
  </div>;
}
