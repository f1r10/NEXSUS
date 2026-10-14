"use client";
import { useCallback, useEffect, useState } from "react";
import type { ApiClient } from "./person-intelligence";

type StoredFile = { id: string; title: string; filename: string; sha256: string; byte_count: number; media_type: string; created_at: string };

export default function FileEvidence({ caseId, api, revision, csrf, apiBase }: {
  caseId: string;
  api: ApiClient;
  revision: number;
  csrf: string;
  apiBase: string;
}) {
  const [files, setFiles] = useState<StoredFile[]>([]);
  const [chosen, setChosen] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const fetchFiles = useCallback(() => api<StoredFile[]>(`/cases/${caseId}/evidence/files`).then(setFiles), [api, caseId]);
  useEffect(() => { let active = true; void fetchFiles().catch((e: unknown) => { if (active) setError(e instanceof Error ? e.message : "Fayllar yüklənmədi"); }); return () => { active = false; }; }, [fetchFiles, revision]);

  async function upload(e: React.FormEvent) {
    e.preventDefault(); if (!chosen || busy) return;
    if (chosen.size > 20 * 1024 * 1024) { setError("Fayl 20 MB həddini aşır"); return; }
    setBusy(true); setError(""); setInfo("");
    try {
      const form = new FormData();form.append("file",chosen);
      const res = await fetch(`${apiBase}/api/v1/cases/${caseId}/evidence/files`, {
        method:"POST", credentials:"include", headers:{"X-CSRF-Token":csrf}, body:form,
      });
      const result = await res.json().catch(()=>({}));
      if (!res.ok) throw new Error(typeof result.detail === "string" ? result.detail : `HTTP ${res.status}`);
      setInfo("Fayl sübutu qeydə alındı"); setChosen(null);
      await fetchFiles();
    } catch(e) {setError(e instanceof Error ? e.message : "Yükləmə uğursuz oldu");}
    finally {setBusy(false);}
  }

  return <section className="panel file-evidence">
    <div className="social-intelligence-head"><div><h3>Orijinal fayl sübutları</h3><p>MinIO · SHA-256 · Case üzrə giriş</p></div><span className="chip">Maksimum 20 MB</span></div>
    <p className="muted">Fayllar xarici sayta göndərilmir. İlkin versiyada OCR, antivirus yoxlaması və hüquqi saxlanma kilidi hələ yoxdur.</p>
    {error && <p role="alert" className="notice error">{error}</p>}{info && <p role="status" className="notice">{info}</p>}
    <form className="file-upload-bar" onSubmit={upload}>
      <input type="file" aria-label="Fayl seçin" accept=".pdf,.txt,.csv,.json,.docx,.xlsx,.png,.jpg,.jpeg,.zip" onChange={e=>setChosen(e.target.files?.[0]||null)}/>
      <button className="primary" disabled={!chosen||busy}>{busy?"Yüklənir...":"Faylı saxla"}</button>
    </form>
    {files.length===0 ? <p className="muted">Bu araşdırmada fayl sübutu yoxdur.</p> : files.map(f=><div className="identity-review" key={f.id}>
      <div><strong>{f.filename}</strong><small>{(f.byte_count/1024).toFixed(1)} KB · SHA-256: {f.sha256.slice(0,16)}…</small></div>
      <a className="secondary" href={`${apiBase}/api/v1/cases/${caseId}/evidence/files/${f.id}/download`} download={f.filename}>İcazəli yükləmə ↓</a>
    </div>)}
  </section>;
}
