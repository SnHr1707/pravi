import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import { Alert, useToast } from "../components/ui";
import { Can, useMe } from "../components/StaffLayout";

const LBL: Record<string, string> = { condition: "Condition", criticality: "Criticality", complaints: "Complaints", age: "Age since renewal", repeat: "Repeat repairs" };
const DEF = { condition: 0.3, criticality: 0.25, complaints: 0.2, age: 0.15, repeat: 0.1 };

export default function Settings() {
  const me = useMe().data;
  const qc = useQueryClient();
  const toast = useToast();
  const wq = useQuery({ queryKey: ["weights"], queryFn: () => api<Record<string, number>>("/api/settings/weights") });
  const llm = useQuery({ queryKey: ["llm"], queryFn: () => api<{ provider: string; model: string; last_error: string | null }>("/api/llm/status") });
  const [w, setW] = useState<Record<string, number>>(DEF);
  const [test, setTest] = useState<any>(null);
  const [testing, setTesting] = useState(false);
  useEffect(() => { if (wq.data) setW(wq.data); }, [wq.data]);
  const isEE = me?.role === "ee";

  const save = async (vals: Record<string, number>) => {
    const r = await api<Record<string, number>>("/api/settings/weights", { method: "PUT", json: vals });
    setW(r); qc.invalidateQueries(); toast("Weights saved — priorities recalculated");
  };
  const runTest = async () => {
    setTesting(true); setTest(null);
    try { setTest(await api("/api/llm/test", { method: "POST" })); } finally { setTesting(false); }
  };
  const reset = async () => {
    if (!window.confirm("Reset all demo data?")) return;
    await api("/api/admin/reset-demo", { method: "POST" }); qc.invalidateQueries(); toast("Demo data reset");
  };

  return (
    <>
      <div className="page-head"><div><h1>Settings</h1><p>Priority weights, document reader and demo data.</p></div></div>
      <div className="grid g2">
        <div className="card">
          <h2>Priority weights</h2>
          <p className="small muted">score = 100 × Σ weight × factor. The department sets the weights; they are normalised to 100%.</p>
          {Object.keys(DEF).map((k) => (
            <div key={k} className="grid items-center gap-2.5 my-1.5" style={{ gridTemplateColumns: "170px 1fr 60px" }}>
              <label className="m-0">{LBL[k]}</label>
              <input type="range" min={0} max={100} className="p-0" disabled={!isEE} value={Math.round((w[k] ?? 0) * 100)}
                onChange={(e) => setW({ ...w, [k]: +e.target.value / 100 })} />
              <span className="mono">{Math.round((w[k] ?? 0) * 100)}%</span>
            </div>
          ))}
          {isEE ? (
            <div className="flex gap-2 mt-2.5"><button className="btn-primary" onClick={() => save(w)}>Save weights</button><button onClick={() => save(DEF)}>Defaults</button></div>
          ) : <p className="small muted">Only the Executive Engineer can change weights.</p>}
        </div>
        <div>
          <div className="card">
            <h2>Document reader (LLM)</h2>
            {llm.data && (
              <div className="kv">
                <div>Mode</div><div>{llm.data.provider === "none" ? "Rules only" : `Rules + LLM (${llm.data.provider})`}</div>
                <div>Model</div><div className="mono">{llm.data.model || "—"}</div>
                {llm.data.last_error && <><div>Last error</div><div className="small" style={{ color: "var(--red)" }}>{llm.data.last_error}</div></>}
              </div>
            )}
            <p className="small muted">The rule-based reader (tuned to Gujarat Form B-1 / nprocure formats) always runs. To add an open-source model, set <span className="mono">OPENROUTER_API_KEY</span> (Qwen via OpenRouter) or <span className="mono">LLM_BASE_URL</span> (Ollama / vLLM on a state server).</p>
            <Can roles={["ee"]}><button onClick={runTest} disabled={testing}>{testing ? "Calling the model…" : "Test LLM"}</button></Can>
            {test && (test.ok
              ? <><Alert tone="green">Working — {test.model} answered in {test.seconds}s</Alert><pre className="small whitespace-pre-wrap">{JSON.stringify(test.fields, null, 1)}</pre></>
              : <Alert tone="red">{test.message || test.error || "Failed"}</Alert>)}
          </div>
          <Can roles={["ee"]}>
            <div className="card">
              <h2>Demo data</h2>
              <p className="small muted">Resets every asset, work, complaint and document to the original Vadodara demo data. Use before a demo.</p>
              <button className="btn-danger" onClick={reset}>Reset demo data</button>
            </div>
          </Can>
          <div className="card"><h2>API</h2>
            <p className="small">Everything in the app is available as a REST API — <a href="/docs" target="_blank">open the API docs</a>. Other departments or apps can plug in, the way banks plug into UPI.</p></div>
        </div>
      </div>
    </>
  );
}
