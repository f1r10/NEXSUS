"use client";
import { useCallback, useEffect, useMemo, useState } from "react";

type Person = { id: string; display_name: string; entity_type: string };
type Case = { id: string; name: string; classification: number; workspace_id: string };
type Workspace = { id: string; name: string };
type Evidence = { id: string; title: string; content: string; sha256: string; source_uri?: string };
type Account = { id: string; platform: string; username: string; identity_status: string; attributed_entity_id?: string };
type Follow = { id: string; follower_id: string; followed_id: string; evidence_id: string; observed_at: string };
type GraphData = { nodes: Person[]; edges: { id: string; source: string; target: string; label: string; status: string }[]; truncated: boolean };
type Auth = { id: string; display_name: string; is_admin: boolean; csrf_token: string };
type View = "overview" | "people" | "graph" | "social" | "evidence" | "transform" | "settings";
const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const nav: { id: View; label: string; glyph: string; description: string }[] = [
  { id: "overview", label: "İdarə paneli", glyph: "▦", description: "Araşdırma icmalı" },
  { id: "people", label: "İnsan axtarışı", glyph: "⌕", description: "Şəxslər və identiklik" },
  { id: "graph", label: "Əlaqə qrafı", glyph: "◎", description: "Qraf və analitik əlaqələr" },
  { id: "social", label: "Sosial şəbəkələr", glyph: "@", description: "Hesablar və izləmələr" },
  { id: "evidence", label: "Sübutlar", glyph: "▤", description: "Mənbələr və istinadlar" },
  { id: "transform", label: "Transform Engine", glyph: "⇄", description: "Lokal genişləndirmə" },
  { id: "settings", label: "İdarəetmə", glyph: "⚙", description: "Workspace və istifadəçilər" },
];

function shortId(id: string) { return id.slice(0, 8); }
function Card({ title, children, extra }: { title: string; children: React.ReactNode; extra?: React.ReactNode }) {
  return <section className="panel"><div className="panel-title"><h3>{title}</h3>{extra}</div>{children}</section>;
}
function Empty({ children }: { children: React.ReactNode }) { return <div className="empty">{children}</div>; }
function InlineStatus({ children }: { children: React.ReactNode }) { return <span className="chip">{children}</span>; }

export default function Home() {
  const [auth, setAuth] = useState<Auth | null>(null);
  const [initializing, setInitializing] = useState(true);
  const [setupRequired, setSetupRequired] = useState(false);
  const [authMode, setAuthMode] = useState<"login" | "bootstrap">("login");
  const [email, setEmail] = useState(""); const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState(""); const [bootstrapToken, setBootstrapToken] = useState("");
  const [busy, setBusy] = useState(false); const [message, setMessage] = useState("");
  const [view, setView] = useState<View>("overview");
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [cases, setCases] = useState<Case[]>([]); const [caseId, setCaseId] = useState("");
  const [people, setPeople] = useState<Person[]>([]); const [query, setQuery] = useState("");
  const [evidence, setEvidence] = useState<Evidence[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]); const [follows, setFollows] = useState<Follow[]>([]);
  const [graph, setGraph] = useState<GraphData>({ nodes: [], edges: [], truncated: false });
  const [selected, setSelected] = useState<string | null>(null);
  const [graphFilter, setGraphFilter] = useState("all");
  const [newPerson, setNewPerson] = useState(""); const [personType, setPersonType] = useState("person");
  const [newWorkspace, setNewWorkspace] = useState(""); const [newCase, setNewCase] = useState("");
  const [newEmail, setNewEmail] = useState(""); const [newDisplay, setNewDisplay] = useState(""); const [newPassword, setNewPassword] = useState("");
  const [memberEmail, setMemberEmail] = useState(""); const [memberRole, setMemberRole] = useState("analyst");
  const [sourceId, setSourceId] = useState(""); const [targetId, setTargetId] = useState("");
  const [relationshipType, setRelationshipType] = useState("KNOWS"); const [relationshipEvidence, setRelationshipEvidence] = useState("");
  const [evTitle, setEvTitle] = useState(""); const [evText, setEvText] = useState("");
  const [platform, setPlatform] = useState("example"); const [username, setUsername] = useState(""); const [externalId, setExternalId] = useState("");
  const [followerId, setFollowerId] = useState(""); const [followedId, setFollowedId] = useState(""); const [followEvidence, setFollowEvidence] = useState("");
  const [transformResult, setTransformResult] = useState<string | null>(null);

  const api = useCallback(async <T,>(path: string, method = "GET", data?: unknown, customHeaders: Record<string, string> = {}): Promise<T> => {
    const headers: Record<string, string> = { ...customHeaders };
    if (data !== undefined) headers["Content-Type"] = "application/json";
    if (!["GET", "HEAD"].includes(method) && auth?.csrf_token) headers["X-CSRF-Token"] = auth.csrf_token;
    const response = await fetch(`${API}/api/v1${path}`, {
      method, headers, credentials: "include", cache: "no-store",
      body: data === undefined ? undefined : JSON.stringify(data),
    });
    const json = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(typeof json.detail === "string" ? json.detail : `HTTP ${response.status}`);
    return json as T;
  }, [auth?.csrf_token]);

  const initialize = useCallback(async () => {
    try {
      const r = await api<Auth>("/auth/me"); setAuth(r);
    } catch {
      try {
        const r = await api<{required: boolean}>("/auth/setup-required");
        setSetupRequired(r.required); setAuthMode(r.required ? "bootstrap" : "login");
      } catch { setMessage("API serverinə qoşulmaq mümkün olmadı. Backend-in işlədiyini yoxlayın."); }
    } finally { setInitializing(false); }
  }, [api]);
  useEffect(() => { void initialize(); /* run once on app mount */ /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, []);

  const reloadScope = useCallback(async () => {
    if (!auth) return;
    try {
      const [w, c] = await Promise.all([api<Workspace[]>("/workspaces"), api<Case[]>("/cases")]);
      setWorkspaces(w); setCases(c);
      setCaseId(old => c.some(x => x.id === old) ? old : (c[0]?.id ?? ""));
    } catch (e) { setMessage(String(e)); }
  }, [auth, api]);
  useEffect(() => { void reloadScope(); }, [reloadScope]);

  const reloadCase = useCallback(async () => {
    if (!auth || !caseId) { setPeople([]); setEvidence([]); setAccounts([]); setFollows([]); setGraph({ nodes: [], edges: [], truncated: false }); return; }
    try {
      const [p, e, a, f, g] = await Promise.all([
        api<Person[]>(`/cases/${caseId}/entities`), api<Evidence[]>(`/cases/${caseId}/evidence`),
        api<Account[]>(`/cases/${caseId}/social/accounts`), api<Follow[]>(`/cases/${caseId}/social/follows`),
        api<GraphData>(`/cases/${caseId}/graph`),
      ]);
      setPeople(p); setEvidence(e); setAccounts(a); setFollows(f); setGraph(g);
    } catch (e) { setMessage(String(e)); }
  }, [auth, caseId, api]);
  useEffect(() => { void reloadCase(); }, [reloadCase]);

  async function run(action: () => Promise<unknown>, success: string, reload = true) {
    setBusy(true); setMessage("");
    try { await action(); setMessage(success); if (reload) await reloadCase(); }
    catch (e) { setMessage(e instanceof Error ? e.message : "Əməliyyat uğursuz oldu"); }
    finally { setBusy(false); }
  }

  async function authenticate(e: React.FormEvent) {
    e.preventDefault(); setBusy(true); setMessage("");
    try {
      const bootstrap = authMode === "bootstrap";
      const r = await api<Auth>(bootstrap ? "/auth/bootstrap" : "/auth/login", "POST",
        bootstrap ? { email, password, display_name: displayName } : { email, password },
        bootstrap ? { "X-Bootstrap-Token": bootstrapToken } : {});
      setAuth(r); setPassword(""); setBootstrapToken("");
    } catch (e) { setMessage(e instanceof Error ? e.message : "Giriş xətası"); }
    finally { setBusy(false); }
  }

  async function logout() {
    await run(() => api("/auth/logout", "POST"), "Çıxış edildi", false);
    setAuth(null); setCases([]); setCaseId(""); setMessage("");
  }

  const activeCase = cases.find(c => c.id === caseId);
  const filteredPeople = people.filter(p => `${p.display_name} ${p.entity_type}`.toLocaleLowerCase("az").includes(query.toLocaleLowerCase("az")));
  const selectedEntity = people.find(x => x.id === selected);
  const graphEdges = graph.edges.filter(x => graphFilter === "all" || x.status === graphFilter);
  const positions = useMemo(() => {
    const count = graph.nodes.length;
    return Object.fromEntries(graph.nodes.map((n, i) => [n.id, { x: 410 + 260 * Math.cos(2 * Math.PI * i / Math.max(count, 1)), y: 245 + 175 * Math.sin(2 * Math.PI * i / Math.max(count, 1)) }]));
  }, [graph.nodes]);

  if (initializing) return <div className="loading">NEXUS iş mühiti açılır...</div>;
  if (!auth) return <main className="auth-screen"><div className="auth-card">
    <div className="auth-brand"><span className="brand-mark">N</span><div><strong>NEXUS</strong><p>Intelligence Platform</p></div></div>
    <div className="auth-divider"/><div className="eyebrow">TƏHLÜKƏSİZ GİRİŞ</div>
    <h1>{authMode === "bootstrap" ? "İlkin quraşdırma" : "Hesabınıza daxil olun"}</h1>
    <p className="muted">{authMode === "bootstrap" ? "Sistemin ilk administrator hesabını yaradın. Serverdəki bootstrap açarı tələb olunur." : "Araşdırma mühitinə yalnız səlahiyyətli istifadəçilər daxil ola bilər."}</p>
    <form onSubmit={authenticate} className="form vertical">
      {authMode === "bootstrap" && <label>Ad və soyad<input required value={displayName} onChange={e => setDisplayName(e.target.value)} placeholder="Sistem administratoru" /></label>}
      <label>Email<input required type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="name@example.local" /></label>
      <label>Şifrə<input required minLength={12} type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="Minimum 12 simvol" /></label>
      {authMode === "bootstrap" && <label>İlkin quraşdırma açarı<input required type="password" value={bootstrapToken} onChange={e => setBootstrapToken(e.target.value)} placeholder="NEXUS_BOOTSTRAP_TOKEN" /></label>}
      <button className="primary full" type="submit" disabled={busy}>{busy ? "Yoxlanılır..." : authMode === "bootstrap" ? "İlkin sistemi qur" : "Daxil ol"}</button>
    </form>
    {setupRequired && <button className="text-button" type="button" onClick={() => setAuthMode(authMode === "login" ? "bootstrap" : "login")}>{authMode === "login" ? "İlkin quraşdırma" : "Giriş səhifəsinə keç"}</button>}
    {message && <p className="notice error">{message}</p>}
    <p className="auth-foot">Case əsaslı icazələr · Mənbəyə bağlı analiz · Audit</p>
  </div></main>;

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="sidebar-brand"><span className="brand-mark">N</span><div><strong>NEXUS</strong><small>INTELLIGENCE</small></div></div>
      <div className="side-label">İŞ MÜHİTİ</div>
      <nav aria-label="Əsas menyu">{nav.map(n => <button key={n.id} title={n.description} className={`nav-item ${view === n.id ? "active" : ""}`} onClick={() => setView(n.id)}><span className="nav-glyph">{n.glyph}</span>{n.label}</button>)}</nav>
      <div className="side-footer"><div className="user-avatar">{auth.display_name.slice(0, 1).toLocaleUpperCase("az")}</div><div><strong>{auth.display_name}</strong><small>{auth.is_admin ? "Administrator" : "İstifadəçi"}</small></div><button title="Çıxış" className="logout" onClick={() => void logout()}>↪</button></div>
    </aside>
    <main className="main-content">
      <header className="topbar"><div><span className="eyebrow">NEXUS / {nav.find(n => n.id === view)?.label}</span><h1>{nav.find(n => n.id === view)?.label}</h1></div><div className="top-actions"><label className="case-picker">Aktiv araşdırma<select value={caseId} onChange={e => { setCaseId(e.target.value); setSelected(null); }}><option value="">Araşdırma seçin</option>{cases.map(c => <option key={c.id} value={c.id}>{c.name} · L{c.classification}</option>)}</select></label><span className="online"><span/> Daxili mühit</span></div></header>
      {message && <div role="status" className="notice"><span>{message}</span><button onClick={() => setMessage("")}>×</button></div>}
      {!caseId && view !== "settings" ? <div className="welcome"><div className="welcome-icon">▦</div><h2>İlk araşdırmanızı yaradın</h2><p>İdarəetmə bölməsindən Workspace və Case yaradın. Yalnız üzv olduğunuz araşdırmalar göstərilir.</p><button className="primary" onClick={() => setView("settings")}>İdarəetməyə keç →</button></div> : null}
      {caseId && view === "overview" && <div className="content"><div className="overview-heading"><div><h2>{activeCase?.name}</h2><p>Case ID: {shortId(caseId)} · Məlumat təsnifatı: L{activeCase?.classification}</p></div><InlineStatus>İcazəli araşdırma</InlineStatus></div><div className="stat-grid">
        {[{value: people.length, label: "Obyektlər", icon: "◇"},{value: graph.edges.length, label: "Əlaqələr", icon: "◎"},{value: accounts.length, label: "Sosial hesablar", icon: "@"},{value: evidence.length, label: "Sübutlar", icon: "▤"}].map(x => <div className="stat" key={x.label}><div className="stat-icon">{x.icon}</div><strong>{x.value}</strong><span>{x.label}</span></div>)}
      </div><div className="two-column"><Card title="Son əlavə edilmiş obyektlər" extra={<button className="text-button" onClick={() => setView("people")}>Hamısına bax →</button>}>{people.length === 0 ? <Empty>Hələ obyekt yaradılmayıb.</Empty> : people.slice(-5).reverse().map(p => <div className="list-row" key={p.id}><span className="object-symbol">◇</span><div><strong>{p.display_name}</strong><small>{p.entity_type}</small></div><button onClick={() => {setSelected(p.id);setView("people");}}>Aç →</button></div>)}</Card><Card title="Analitik iş axını"><div className="workflow"><div><span>01</span><p>Şəxs və obyektləri qeyd edin</p></div><div><span>02</span><p>Orijinal mənbə əlavə edin</p></div><div><span>03</span><p>Əlaqələri təklif və təsdiq edin</p></div><div><span>04</span><p>Qraf və lokal Transform-ları işlədin</p></div></div></Card></div></div>}
      {caseId && view === "people" && <div className="content two-column wide-left"><Card title="Şəxs və obyekt axtarışı" extra={<InlineStatus>Case daxilində</InlineStatus>}><div className="search-box"><span>⌕</span><input value={query} onChange={e => setQuery(e.target.value)} placeholder="Ad, təşkilat və ya obyekt axtarın..." /></div><div className="list-area">{filteredPeople.length === 0 ? <Empty>Bu sorğuya uyğun nəticə yoxdur.</Empty> : filteredPeople.map(p => <button className={`person-row ${selected === p.id ? "selected" : ""}`} key={p.id} onClick={() => setSelected(p.id)}><span className="object-symbol">{p.entity_type === "person" ? "♙" : "◇"}</span><span><strong>{p.display_name}</strong><small>{p.entity_type} · {shortId(p.id)}</small></span><span className="row-arrow">›</span></button>)}</div></Card><div className="stack"><Card title="Obyekt profili">{selectedEntity ? <div><div className="profile-header"><div className="large-avatar">{selectedEntity.display_name.slice(0,1)}</div><div><h3>{selectedEntity.display_name}</h3><p>{selectedEntity.entity_type} · {shortId(selectedEntity.id)}</p></div></div><p className="muted">Yalnız bu araşdırma daxilində səlahiyyətli məlumatlar göstərilir. İdentiklik namizədləri avtomatik təsdiqlənmir.</p><button className="secondary" onClick={() => setView("graph")}>Əlaqə qrafında bax →</button></div> : <Empty>Profilə baxmaq üçün soldan obyekt seçin.</Empty>}</Card><Card title="Yeni obyekt"><form className="form vertical" onSubmit={e => {e.preventDefault(); void run(async () => {await api(`/cases/${caseId}/entities`, "POST", {display_name: newPerson, entity_type: personType});setNewPerson("");}, "Obyekt yaradıldı");}}><label>Ad / təsvir<input required value={newPerson} onChange={e=>setNewPerson(e.target.value)} placeholder="Məsələn: Əli Məmmədov" /></label><label>Obyekt tipi<select value={personType} onChange={e=>setPersonType(e.target.value)}>{["person","organization","device","digital_account","location","vehicle","event","document","other"].map(t=><option key={t} value={t}>{t}</option>)}</select></label><button className="primary" disabled={busy}>+ Obyekt əlavə et</button></form></Card></div></div>}
      {caseId && view === "graph" && <div className="content"><div className="graph-toolbar"><div><h2>Knowledge Graph</h2><p>Əlaqələr ilkin olaraq təklif statusunda yaradılır; təsdiq üçün mənbə lazımdır.</p></div><select value={graphFilter} onChange={e=>setGraphFilter(e.target.value)}><option value="all">Bütün əlaqələr</option><option value="proposed">Təklif olunan</option><option value="approved">Təsdiqlənmiş</option><option value="rejected">Rədd edilən</option></select></div><div className="graph-layout"><div className="graph-canvas">{graph.nodes.length ? <svg viewBox="0 0 820 490" role="img" aria-label="Əlaqələr qrafı">{graphEdges.map(edge => positions[edge.source] && positions[edge.target] && <g key={edge.id}><line x1={positions[edge.source].x} y1={positions[edge.source].y} x2={positions[edge.target].x} y2={positions[edge.target].y} stroke={edge.status === "approved" ? "#237768" : "#a6aebb"} strokeWidth="2" strokeDasharray={edge.status === "approved" ? "0" : "5 5"}/><text x={(positions[edge.source].x+positions[edge.target].x)/2} y={(positions[edge.source].y+positions[edge.target].y)/2-5} textAnchor="middle" fontSize="11" fill="#627084">{edge.label}</text></g>)}{graph.nodes.map(node => <g key={node.id} role="button" tabIndex={0} onClick={()=>setSelected(node.id)} onKeyDown={e=>{if(e.key === "Enter")setSelected(node.id);}} style={{cursor:"pointer"}}><circle cx={positions[node.id].x} cy={positions[node.id].y} r={selected===node.id?36:31} fill={node.entity_type === "person" ? "#263f5c" : "#467b7f"} stroke={selected===node.id?"#d6a850":"#fff"} strokeWidth="3"/><text x={positions[node.id].x} y={positions[node.id].y+4} textAnchor="middle" fill="white" fontSize="11" fontWeight="600">{node.display_name.slice(0,11)}</text></g>)}</svg> : <Empty>Əlaqə qrafı boşdur. Əvvəl obyekt yaradın.</Empty>}{graph.truncated && <p className="notice">Nəticələr limitə görə qısaldılıb (maksimum 200 düyün, 500 əlaqə).</p>}</div><div className="graph-inspector"><Card title="Əlaqə yarat"><form className="form vertical" onSubmit={e=>{e.preventDefault();void run(async()=>{await api(`/cases/${caseId}/relationships`,"POST",{source_id:sourceId,target_id:targetId,relation_type:relationshipType,evidence_id:relationshipEvidence||null});},"Əlaqə yoxlama üçün əlavə edildi");}}><label>Başlanğıc obyekt<select required value={sourceId} onChange={e=>setSourceId(e.target.value)}><option value="">Seçin</option>{people.map(p=><option key={p.id} value={p.id}>{p.display_name}</option>)}</select></label><label>Hədəf obyekt<select required value={targetId} onChange={e=>setTargetId(e.target.value)}><option value="">Seçin</option>{people.map(p=><option key={p.id} value={p.id}>{p.display_name}</option>)}</select></label><label>Əlaqə tipi<input required value={relationshipType} onChange={e=>setRelationshipType(e.target.value)} /></label><label>Sübut (təsdiq üçün)<select value={relationshipEvidence} onChange={e=>setRelationshipEvidence(e.target.value)}><option value="">Sübut seçilməyib</option>{evidence.map(x=><option key={x.id} value={x.id}>{x.title}</option>)}</select></label><button className="primary" disabled={busy}>+ Əlaqə təklif et</button></form></Card><Card title="Təkliflər və qərarlar">{graph.edges.length === 0 ? <Empty>Əlaqə yoxdur.</Empty> : graph.edges.map(x=><div className="relation-row" key={x.id}><div><strong>{x.label}</strong><small>{x.status} · {shortId(x.id)}</small></div>{x.status === "proposed" && <div className="row-actions"><button onClick={()=>void run(()=>api(`/cases/${caseId}/relationships/${x.id}/review`,"POST",{decision:"approved"}),"Qərar tətbiq olundu")}>Təsdiq</button><button onClick={()=>void run(()=>api(`/cases/${caseId}/relationships/${x.id}/review`,"POST",{decision:"rejected"}),"Rədd edildi")}>Rədd</button></div>}</div>)}</Card></div></div></div>}
      {caseId && view === "evidence" && <div className="content two-column"><Card title="Mənbə və sübut qeydləri">{evidence.length===0?<Empty>Bu araşdırmaya mətn sübutu əlavə edilməyib.</Empty>:evidence.map(x=><div key={x.id} className="evidence-row"><div className="evidence-icon">▤</div><div><strong>{x.title}</strong><p>{x.content.slice(0,220)}{x.content.length>220?"...":""}</p><small>SHA-256: {shortId(x.sha256)}... · {x.source_uri||"Daxili qeyd"}</small></div></div>)}</Card><Card title="Mətn sübutu əlavə et"><p className="muted">Bu ilkin versiya mətn qeydlərini dəstəkləyir. PDF, OCR və media pipeline növbəti mərhələyə aiddir.</p><form className="form vertical" onSubmit={e=>{e.preventDefault();void run(async()=>{await api(`/cases/${caseId}/evidence/text`,"POST",{title:evTitle,content:evText});setEvTitle("");setEvText("");},"Mənbə qeydi saxlanıldı");}}><label>Mənbə adı<input required value={evTitle} onChange={e=>setEvTitle(e.target.value)}/></label><label>Mətn<textarea required value={evText} onChange={e=>setEvText(e.target.value)} rows={8} placeholder="Orijinal mənbədən icazəli mətn fraqmenti..." /></label><button className="primary" disabled={busy}>+ Sübut əlavə et</button></form></Card></div>}
      {caseId && view === "social" && <div className="content"><div className="two-column"><Card title="Sosial hesablar"><p className="muted">Platforma hesabları Case daxilində saxlanılır. Eyni username şəxs identikliyini sübut etmir.</p>{accounts.length===0?<Empty>Hesab yoxdur.</Empty>:accounts.map(a=><div className="list-row" key={a.id}><span className="object-symbol">@</span><div><strong>{a.username}</strong><small>{a.platform} · {a.identity_status}</small></div></div>)}</Card><Card title="Sosial hesab əlavə et"><form className="form vertical" onSubmit={e=>{e.preventDefault();void run(async()=>{await api(`/cases/${caseId}/social/accounts`,"POST",{platform,external_id:externalId,username});setExternalId("");setUsername("");},"Hesab əlavə olundu");}}><label>Platforma<input required value={platform} onChange={e=>setPlatform(e.target.value.toLowerCase())} /></label><label>Platformanın sabit hesab ID-si<input required value={externalId} onChange={e=>setExternalId(e.target.value)}/></label><label>İstifadəçi adı<input required value={username} onChange={e=>setUsername(e.target.value)}/></label><button className="primary" disabled={busy}>+ Hesab əlavə et</button></form></Card></div><div className="two-column"><Card title="İstiqamətli izləmə əlaqələri"><p className="muted">A → B: A hesabı B hesabını izləyir. API snapshot və ya sənəd mənbəsi tələb olunur.</p>{follows.length===0?<Empty>İzləmə müşahidəsi yoxdur.</Empty>:follows.map(f=><div className="list-row" key={f.id}><span className="object-symbol">⇢</span><div><strong>{accounts.find(a=>a.id===f.follower_id)?.username||shortId(f.follower_id)} → {accounts.find(a=>a.id===f.followed_id)?.username||shortId(f.followed_id)}</strong><small>{f.observed_at.slice(0,19).replace("T"," ")}</small></div></div>)}</Card><Card title="İzləmə müşahidəsi əlavə et"><form className="form vertical" onSubmit={e=>{e.preventDefault();void run(()=>api(`/cases/${caseId}/social/follows`,"POST",{follower_id:followerId,followed_id:followedId,evidence_id:followEvidence}),"İzləmə müşahidəsi qeyd edildi");}}><label>İzləyən hesab<select required value={followerId} onChange={e=>setFollowerId(e.target.value)}><option value="">Seçin</option>{accounts.map(a=><option key={a.id} value={a.id}>{a.platform}: {a.username}</option>)}</select></label><label>İzlənən hesab<select required value={followedId} onChange={e=>setFollowedId(e.target.value)}><option value="">Seçin</option>{accounts.map(a=><option key={a.id} value={a.id}>{a.platform}: {a.username}</option>)}</select></label><label>Mənbə sübutu<select required value={followEvidence} onChange={e=>setFollowEvidence(e.target.value)}><option value="">Seçin</option>{evidence.map(x=><option key={x.id} value={x.id}>{x.title}</option>)}</select></label><button className="primary" disabled={busy}>+ Müşahidə əlavə et</button></form></Card></div></div>}
      {caseId && view === "transform" && <div className="content two-column"><Card title="Transform Engine"><p className="muted">Hazırda yalnız lokal qraf genişləndirməsi aktivdir. Xarici RapidAPI connector-ları credentials, təhlükəsizlik yoxlaması və provider müqavilələri olmadan işləmir.</p><div className="transform-card"><span className="object-symbol">⇄</span><div><strong>graph.neighbors</strong><small>Lokal · Şəbəkə çıxışı tələb etmir</small><p>Seçilmiş obyektin bu Case-dəki birbaşa əlaqələrini tapır.</p></div></div><form className="form vertical" onSubmit={e=>{e.preventDefault();void run(async()=>{const r=await api<{result:{neighbors:string[];truncated:boolean}}>(`/cases/${caseId}/transforms`,"POST",{transform_name:"graph.neighbors",input_entity_id:selected});setTransformResult(JSON.stringify(r.result,null,2));},"Lokal Transform tamamlandı",false);}}><label>Obyekt<select required value={selected||""} onChange={e=>setSelected(e.target.value)}><option value="">Obyekt seçin</option>{people.map(p=><option key={p.id} value={p.id}>{p.display_name}</option>)}</select></label><button disabled={busy||!selected} className="primary">Transform-u işə sal →</button></form>{transformResult && <pre className="result-json">{transformResult}</pre>}</Card><Card title="Connector statusu"><div className="connector"><span>RapidAPI / sosial provayderlər</span><InlineStatus>Konfiqurasiya edilməyib</InlineStatus></div><div className="connector"><span>PDF/OCR processing</span><InlineStatus>Növbəti mərhələ</InlineStatus></div><div className="connector"><span>Lokal Graph Transform</span><InlineStatus>Aktiv</InlineStatus></div><p className="muted">OSINT icazələri və API limitləri ayrıca konfiqurasiya ediləcək. Uydurma nəticələr yaradılmır.</p></Card></div>}
      {view === "settings" && <div className="content"><div className="two-column"><Card title="Workspace yarat"><form className="form vertical" onSubmit={e=>{e.preventDefault();void run(async()=>{await api("/workspaces","POST",{name:newWorkspace});setNewWorkspace("");await reloadScope();},"Workspace yaradıldı",false);}}><label>Workspace adı<input required minLength={2} value={newWorkspace} onChange={e=>setNewWorkspace(e.target.value)} /></label><button className="primary" disabled={busy||!auth.is_admin}>+ Workspace yarat</button></form><div className="mini-list">{workspaces.map(w=><div key={w.id}>▦ {w.name}</div>)}</div></Card><Card title="Araşdırma yarat"><form className="form vertical" onSubmit={e=>{e.preventDefault();void run(async()=>{const wid=workspaces[0]?.id;if(!wid)throw new Error("Əvvəl Workspace yaradın");await api(`/workspaces/${wid}/cases`,"POST",{name:newCase,classification:2});setNewCase("");await reloadScope();},"Case yaradıldı",false);}}><p className="muted">İlkin versiyada yeni Case ilk Workspace altında yaradılır, L2 təsnifatı və disabled qlobal görünürlüklə başlayır.</p><label>Case adı<input required minLength={2} value={newCase} onChange={e=>setNewCase(e.target.value)} /></label><button className="primary" disabled={busy||!auth.is_admin}>+ Case yarat</button></form></Card></div><div className="two-column"><Card title="İstifadəçi hesabı yarat"><form className="form vertical" onSubmit={e=>{e.preventDefault();void run(async()=>{await api("/users","POST",{email:newEmail,display_name:newDisplay,password:newPassword});setNewEmail("");setNewDisplay("");setNewPassword("");},"İstifadəçi yaradıldı",false);}}><label>Ad və soyad<input required value={newDisplay} onChange={e=>setNewDisplay(e.target.value)}/></label><label>Email<input required type="email" value={newEmail} onChange={e=>setNewEmail(e.target.value)}/></label><label>İlkin şifrə<input required minLength={12} type="password" value={newPassword} onChange={e=>setNewPassword(e.target.value)}/></label><button className="primary" disabled={busy||!auth.is_admin}>+ İstifadəçi yarat</button></form></Card><Card title="Case-ə üzv əlavə et"><p className="muted">Case Manager səlahiyyəti tələb olunur. Üzvlük yalnız seçilmiş Case-ə tətbiq olunur.</p><form className="form vertical" onSubmit={e=>{e.preventDefault();void run(async()=>{await api(`/cases/${caseId}/members`,"POST",{email:memberEmail,role:memberRole});setMemberEmail("");},"Üzv əlavə edildi",false);}}><label>İstifadəçinin emaili<input required type="email" value={memberEmail} onChange={e=>setMemberEmail(e.target.value)}/></label><label>Case rolu<select value={memberRole} onChange={e=>setMemberRole(e.target.value)}><option value="viewer">Viewer</option><option value="analyst">Analyst</option><option value="reviewer">Reviewer</option><option value="case_manager">Case Manager</option></select></label><button className="primary" disabled={busy||!caseId}>+ Üzv əlavə et</button></form></Card></div></div>}
      <footer className="footer">NEXUS v0.1 · Case-scoped access · Offline-first foundation <span>İlkin inkişaf versiyası — production üçün hazır deyil</span></footer>
    </main>
  </div>;
}
