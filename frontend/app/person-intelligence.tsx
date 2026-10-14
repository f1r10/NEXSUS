"use client";

import { useEffect, useState } from "react";

export type ApiClient = <T,>(path: string, method?: string, data?: unknown, headers?: Record<string, string>) => Promise<T>;

type Person = { id: string; entity_type: string; display_name: string };
type Profile = {
  person: Person;
  assertions: { id: string; attribute: string; value: string; review_status: string; evidence_id: string | null }[];
  relationships: { id: string; source_id: string; target_id: string; relation_type: string; review_status: string; evidence_id: string | null }[];
  accounts: { id: string; platform: string; username: string; identity_status: string }[];
  account_candidates: { id: string; account_id: string; evidence_id: string; status: string }[];
  posts: { id: string; content: string; evidence_id: string; published_at: string | null; observed_at: string }[];
  data_scope: string;
};

export default function PersonIntelligence({ caseId, person, api, revision, onOpenGraph }: {
  caseId: string;
  person: Person | null;
  api: ApiClient;
  revision: number;
  onOpenGraph: () => void;
}) {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!person) { setProfile(null); setError(""); return; }
    let alive = true;
    setLoading(true);
    setProfile(null);
    setError("");
    api<Profile>(`/cases/${caseId}/people/${person.id}/profile`)
      .then(data => { if (alive) setProfile(data); })
      .catch((e: unknown) => { if (alive) setError(e instanceof Error ? e.message : "Profil açıla bilmədi"); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [api, caseId, person?.id, revision]);

  if (!person) return <div className="intelligence-empty">Profilə baxmaq üçün soldan şəxs seçin.</div>;
  return <div className="person-detail">
    <div className="profile-header">
      <div className="large-avatar">{person.display_name.slice(0, 1)}</div>
      <div><h3>{person.display_name}</h3><p>Case daxilində təsdiqə əsaslanan profil</p></div>
    </div>
    {error && <p role="alert" className="notice error">{error}</p>}
    {loading && <p className="muted">Profil məlumatları yüklənir...</p>}
    {profile && <>
      <div className="intelligence-metrics">
        <div><b>{profile.assertions.length}</b><small>Atribut</small></div>
        <div><b>{profile.accounts.length}</b><small>Təsdiqli hesab</small></div>
        <div><b>{profile.relationships.length}</b><small>Əlaqə</small></div>
        <div><b>{profile.posts.length}</b><small>Paylaşım</small></div>
      </div>
      <div className="intelligence-section"><h4>Atributlar və mənbələr</h4>
        {profile.assertions.length ? profile.assertions.map(x => <div className="intelligence-record" key={x.id}>
          <strong>{x.attribute}</strong><span>{x.value}</span>
          <small>{x.review_status === "approved" ? "Təsdiqlənmiş" : "Yoxlama tələb olunur"} · Mənbə: {x.evidence_id?.slice(0,8) || "göstərilməyib"}</small>
        </div>) : <p className="muted">Bu şəxs üçün atribut qeyd edilməyib.</p>}
      </div>
      <div className="intelligence-section"><h4>Sosial hesablar</h4>
        {profile.accounts.length ? profile.accounts.map(a => <div className="intelligence-record" key={a.id}>
          <strong>@{a.username}</strong><small>{a.platform} · İnsan tərəfindən təsdiqlənmiş uyğunluq</small>
        </div>) : <p className="muted">Təsdiqlənmiş sosial hesab yoxdur.</p>}
        {profile.account_candidates.length > 0 && <p className="warning-note">{profile.account_candidates.length} hesab uyğunluğu yoxlanılma mərhələsindədir. Bu hesablar şəxsə aid hesab edilmir.</p>}
      </div>
      <div className="intelligence-section"><h4>Əlaqələr və fəaliyyət</h4>
        {profile.relationships.slice(0,8).map(r => <div className="intelligence-record" key={r.id}>
          <strong>{r.relation_type}</strong><small>{r.review_status} · {r.evidence_id ? `Mənbə ${r.evidence_id.slice(0,8)}` : "Sübut göstərilməyib"}</small>
        </div>)}
        {profile.posts.slice(0,5).map(p => <div className="intelligence-record" key={p.id}>
          <span>{p.content}</span><small>Paylaşım · {p.published_at || p.observed_at} · Mənbə {p.evidence_id.slice(0,8)}</small>
        </div>)}
        {!profile.relationships.length && !profile.posts.length && <p className="muted">Təsdiqlənmiş hesablar üzrə fəaliyyət qeydləri mövcud deyil.</p>}
      </div>
    </>}
    <button type="button" className="secondary" onClick={onOpenGraph}>Əlaqə qrafını aç →</button>
    <p className="muted">Məlumat yalnız seçilmiş Case-dən alınır. İzləmə və şərh faktları şəxsi tanışlıq sübutu deyil.</p>
  </div>;
}
