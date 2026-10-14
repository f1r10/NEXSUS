"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import type { ApiClient } from "./person-intelligence";

type Account = { id: string; platform: string; username: string; identity_status: string };
type Person = { id: string; display_name: string; entity_type: string };
type Evidence = { id: string; title: string };
type Post = { id: string; author_account_id: string; platform_post_id: string; content: string; evidence_id: string; published_at: string | null };
type Comment = { id: string; post_id: string; author_account_id: string; content: string; evidence_id: string };
type Attribution = { id: string; account_id: string; entity_id: string; evidence_id: string; review_status: string };
type SocialGraph = { nodes: { id: string; display_name: string }[]; edges: { id: string; source: string; target: string; label: string; evidence_id: string }[]; truncated: boolean };

export default function SocialInvestigation({ caseId, api, accounts, people, evidence, revision, onUpdated }: {
  caseId: string;
  api: ApiClient;
  accounts: Account[];
  people: Person[];
  evidence: Evidence[];
  revision: number;
  onUpdated: () => Promise<void>;
}) {
  const [posts, setPosts] = useState<Post[]>([]);
  const [comments, setComments] = useState<Comment[]>([]);
  const [proposals, setProposals] = useState<Attribution[]>([]);
  const [socialGraph, setSocialGraph] = useState<SocialGraph>({ nodes: [], edges: [], truncated: false });
  const [accountId, setAccountId] = useState("");
  const [postId, setPostId] = useState("");
  const [personId, setPersonId] = useState("");
  const [sourceId, setSourceId] = useState("");
  const [platformId, setPlatformId] = useState("");
  const [content, setContent] = useState("");
  const [commentContent, setCommentContent] = useState("");
  const [commentPlatformId, setCommentPlatformId] = useState("");
  const [commentAccountId, setCommentAccountId] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [saving, setSaving] = useState(false);
  const [showGraph, setShowGraph] = useState(false);

  const load = useCallback(async () => {
    const [p, c, a, g] = await Promise.all([
      api<Post[]>(`/cases/${caseId}/social/posts`),
      api<Comment[]>(`/cases/${caseId}/social/comments`),
      api<Attribution[]>(`/cases/${caseId}/social/attributions`),
      api<SocialGraph>(`/cases/${caseId}/social/graph`),
    ]);
    setPosts(p); setComments(c); setProposals(a); setSocialGraph(g);
  }, [api, caseId]);
  useEffect(() => { let active = true; void load().catch((e: unknown) => { if(active) setError(e instanceof Error ? e.message : "Sosial qeydlər yüklənmədi"); }); return () => { active = false; }; }, [load, revision]);

  async function submit(action: () => Promise<unknown>, success: string) {
    setError(""); setMessage(""); setSaving(true);
    try { await action(); await onUpdated(); await load(); setMessage(success); }
    catch (e) { setError(e instanceof Error ? e.message : "Əməliyyat yerinə yetirilmədi"); }
    finally { setSaving(false); }
  }
  const coords = useMemo(() => Object.fromEntries(socialGraph.nodes.map((node, i) => [node.id, {
    x: 250 + 185 * Math.cos(i * 2 * Math.PI / Math.max(1, socialGraph.nodes.length)),
    y: 145 + 98 * Math.sin(i * 2 * Math.PI / Math.max(1, socialGraph.nodes.length)),
  }])), [socialGraph.nodes]);
  const username = (id: string) => accounts.find(a => a.id === id)?.username || id.slice(0,8);
  return <section className="social-intelligence">
    <div className="social-intelligence-head">
      <div><h2>Sosial fəaliyyət və uyğunlaşdırma</h2><p>Mənbəyə əsaslanan müşahidələr · Case izolyasiyası · İnsan təsdiqi</p></div>
      <button className="secondary" onClick={() => setShowGraph(x => !x)}>{showGraph ? "Siyahıya qayıt" : "Sosial qrafı göstər"}</button>
    </div>
    {error && <p role="alert" className="notice error">{error}</p>}
    {message && <p role="status" className="notice">{message}</p>}
    {showGraph && <div className="panel social-graph"><h3>Hesablararası istiqamətli qraf</h3>
      {socialGraph.nodes.length === 0 ? <p className="muted">Sosial hesab yoxdur.</p> : <svg viewBox="0 0 500 290" role="img" aria-label="Hesabların sosial qrafı">
        <defs><marker id="social-arrow" markerWidth="8" markerHeight="8" refX="20" refY="3" orient="auto"><path d="M0 0 L6 3 L0 6" fill="none" stroke="#237768" strokeWidth="1.4" /></marker></defs>
        {socialGraph.edges.map(e => coords[e.source] && coords[e.target] ? <g key={e.id}>
          <line x1={coords[e.source].x} y1={coords[e.source].y} x2={coords[e.target].x} y2={coords[e.target].y} stroke="#237768" strokeWidth="2" markerEnd="url(#social-arrow)" />
          <text x={(coords[e.source].x+coords[e.target].x)/2} y={(coords[e.source].y+coords[e.target].y)/2-8} textAnchor="middle" fontSize="10" fill="#50677e">İzləyir</text>
        </g> : null)}
        {socialGraph.nodes.map(n => <g key={n.id}><circle cx={coords[n.id].x} cy={coords[n.id].y} r="35" fill="#263f5c" /><text x={coords[n.id].x} y={coords[n.id].y+3} textAnchor="middle" fill="#fff" fontSize="10">{n.display_name.slice(-13)}</text></g>)}
      </svg>}
      {socialGraph.truncated && <p className="warning-note">Qraf nəticələri limitə görə qısaldılıb.</p>}
      <p className="muted">Ox izləyən hesabdan izlənilən hesaba yönəlir. Bu qraf şəxs–şəxs əlaqəsi təsdiqləmir.</p>
    </div>}
    <div className="two-column">
      <div className="panel"><h3>Paylaşımlar və şərhlər</h3>
        {posts.length === 0 && <p className="muted">Mənbəyə bağlı paylaşım əlavə edilməyib.</p>}
        {posts.map(p => <article key={p.id} className="activity-record"><strong>@{username(p.author_account_id)}</strong>
          <p>{p.content}</p><small>{p.published_at || "Tarix məlum deyil"} · Mənbə {p.evidence_id.slice(0,8)}</small>
          {comments.filter(c => c.post_id === p.id).map(c => <div className="activity-comment" key={c.id}><b>@{username(c.author_account_id)}</b>: {c.content}<small>Mənbə {c.evidence_id.slice(0,8)}</small></div>)}
        </article>)}
      </div>
      <div className="panel"><h3>Yeni paylaşım müşahidəsi</h3><form className="form vertical" onSubmit={e => {e.preventDefault();void submit(async () => {
        await api(`/cases/${caseId}/social/posts`, "POST", {author_account_id:accountId,platform_post_id:platformId,content,evidence_id:sourceId});
        setPlatformId("");setContent("");}, "Paylaşım sübutla qeydə alındı");}}>
        <label>Sosial hesab<select required value={accountId} onChange={e=>setAccountId(e.target.value)}><option value="">Seçin</option>{accounts.map(a=><option key={a.id} value={a.id}>{a.platform}: @{a.username}</option>)}</select></label>
        <label>Paylaşımın platforma ID-si<input required value={platformId} onChange={e=>setPlatformId(e.target.value)} /></label>
        <label>Paylaşım mətni<textarea required value={content} onChange={e=>setContent(e.target.value)} rows={3} /></label>
        <label>Mənbə sübutu<select required value={sourceId} onChange={e=>setSourceId(e.target.value)}><option value="">Seçin</option>{evidence.map(ev=><option key={ev.id} value={ev.id}>{ev.title}</option>)}</select></label>
        <button className="primary" disabled={saving}>Paylaşım əlavə et</button>
      </form><h3 className="section-divider">Yeni şərh müşahidəsi</h3><form className="form vertical" onSubmit={e=>{e.preventDefault();void submit(async()=>{
        await api(`/cases/${caseId}/social/comments`,"POST",{post_id:postId,author_account_id:commentAccountId,platform_comment_id:commentPlatformId,content:commentContent,evidence_id:sourceId});
        setCommentPlatformId("");setCommentContent("");}, "Şərh sübutla qeydə alındı");}}>
        <label>Paylaşım<select required value={postId} onChange={e=>setPostId(e.target.value)}><option value="">Seçin</option>{posts.map(p=><option key={p.id} value={p.id}>@{username(p.author_account_id)} · {p.content.slice(0,40)}</option>)}</select></label>
        <label>Şərh müəllifi<select required value={commentAccountId} onChange={e=>setCommentAccountId(e.target.value)}><option value="">Seçin</option>{accounts.map(a=><option key={a.id} value={a.id}>@{a.username}</option>)}</select></label>
        <label>Şərhin platforma ID-si<input required value={commentPlatformId} onChange={e=>setCommentPlatformId(e.target.value)}/></label>
        <label>Şərh mətni<textarea required value={commentContent} onChange={e=>setCommentContent(e.target.value)} rows={2}/></label>
        <button className="primary" disabled={saving||!sourceId}>Şərh əlavə et (seçilmiş mənbə)</button>
      </form></div>
    </div>
    <div className="two-column">
      <div className="panel"><h3>Hesab–şəxs uyğunluğu üçün təklif</h3><p className="muted">Təklif yalnız mövcud sübuta əsaslanır. Reviewer təsdiqi olmadan şəxs profilinə aid edilmir.</p>
        <form className="form vertical" onSubmit={e=>{e.preventDefault();void submit(()=>api(`/cases/${caseId}/social/attributions`,"POST",{account_id:accountId,entity_id:personId,evidence_id:sourceId}),"Uyğunluq təsdiqə göndərildi");}}>
          <label>Hesab<select required value={accountId} onChange={e=>setAccountId(e.target.value)}><option value="">Seçin</option>{accounts.map(a=><option key={a.id} value={a.id}>@{a.username}</option>)}</select></label>
          <label>Şəxs<select required value={personId} onChange={e=>setPersonId(e.target.value)}><option value="">Seçin</option>{people.filter(p=>p.entity_type==="person").map(p=><option key={p.id} value={p.id}>{p.display_name}</option>)}</select></label>
          <label>Mənbə<select required value={sourceId} onChange={e=>setSourceId(e.target.value)}><option value="">Seçin</option>{evidence.map(ev=><option key={ev.id} value={ev.id}>{ev.title}</option>)}</select></label>
          <button className="primary" disabled={saving}>Uyğunluğu təklif et</button>
        </form>
      </div>
      <div className="panel"><h3>İdentiklik yoxlamaları</h3>
        {proposals.length === 0 ? <p className="muted">Uyğunluq təklifi yoxdur.</p> : proposals.map(p => <div className="identity-review" key={p.id}>
          <div><strong>@{username(p.account_id)} → {people.find(x=>x.id===p.entity_id)?.display_name || "Şəxs"}</strong><small>{p.review_status} · Mənbə {p.evidence_id.slice(0,8)}</small></div>
          {p.review_status === "proposed" && <div className="row-actions">
            <button disabled={saving} onClick={()=>void submit(()=>api(`/cases/${caseId}/social/attributions/${p.id}/review`,"POST",{decision:"approved"}),"Uyğunluq təsdiq edildi")}>Təsdiq</button>
            <button disabled={saving} onClick={()=>void submit(()=>api(`/cases/${caseId}/social/attributions/${p.id}/review`,"POST",{decision:"rejected"}),"Uyğunluq rədd edildi")}>Rədd</button>
          </div>}
        </div>)}
      </div>
    </div>
  </section>;
}
