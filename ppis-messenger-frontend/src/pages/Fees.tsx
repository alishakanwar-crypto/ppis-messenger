import { useEffect, useState } from "react";
import { ArrowLeft, IndianRupee, RefreshCw } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { getFeeSessions, getFeeSummary } from "../lib/api";

const money = (paise: number) => new Intl.NumberFormat("en-IN", {
  style: "currency", currency: "INR",
}).format((paise || 0) / 100);
interface GradeSummary { grade: string; billed: number; collected: number; concession: number }
interface FeeSummary { billed: number; collected: number; concession: number; outstanding: number; by_grade: GradeSummary[] }

export default function Fees() {
  const navigate = useNavigate();
  const [sessions, setSessions] = useState<Array<{ id: number; name: string }>>([]);
  const [sessionId, setSessionId] = useState<number>();
  const [summary, setSummary] = useState<FeeSummary | null>(null);
  const [error, setError] = useState("");
  const load = async (id: number) => {
    try { setSummary(await getFeeSummary(id)); setError(""); }
    catch (e) { setError(e instanceof Error ? e.message : "Unable to load fee summary"); }
  };
  useEffect(() => { getFeeSessions().then((x) => {
    const rows = x.sessions || []; setSessions(rows);
    if (rows[0]) { setSessionId(rows[0].id); load(rows[0].id); }
  }).catch((e) => setError(e.message)); }, []);
  return <div className="min-h-screen bg-slate-50 text-slate-900">
    <header className="border-b border-slate-200 bg-white"><div className="mx-auto flex max-w-7xl items-center gap-3 px-4 py-4">
      <button onClick={() => navigate("/erp")} className="rounded-lg p-2 hover:bg-slate-100"><ArrowLeft size={20} /></button>
      <IndianRupee className="text-blue-700" /><div><p className="text-xs font-semibold uppercase tracking-widest text-blue-700">School ERP</p><h1 className="text-xl font-bold">Fees &amp; payments</h1></div>
      <RefreshCw onClick={() => sessionId && load(sessionId)} className="ml-auto cursor-pointer text-slate-500" size={18} />
    </div></header>
    <main className="mx-auto max-w-7xl px-4 py-7">
      <div className="mb-6 flex items-center justify-between"><div><h2 className="text-2xl font-bold">Fee overview</h2><p className="text-sm text-slate-500">Billed, collected and outstanding balances in paise-safe accounting.</p></div>
        <select value={sessionId || ""} onChange={(e) => { const id = Number(e.target.value); setSessionId(id); load(id); }} className="rounded-lg border border-slate-300 bg-white px-3 py-2">{sessions.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select>
      </div>
      {error && <p className="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}
      <div className="grid gap-4 sm:grid-cols-4">{[
        ["Billed", summary?.billed], ["Collected", summary?.collected], ["Concession", summary?.concession], ["Outstanding", summary?.outstanding],
      ].map(([label, value]) => <div key={label as string} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><p className="text-sm text-slate-500">{label}</p><p className="mt-2 text-2xl font-bold">{money(value as number)}</p></div>)}</div>
      <section className="mt-7 rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><h3 className="mb-4 font-semibold">Grade-wise collections</h3>
        <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr className="border-b text-slate-500"><th className="px-3 py-2">Grade</th><th className="px-3 py-2">Billed</th><th className="px-3 py-2">Collected</th><th className="px-3 py-2">Outstanding</th></tr></thead><tbody>{(summary?.by_grade || []).map((row) => <tr key={row.grade} className="border-b last:border-0"><td className="px-3 py-3 font-medium">{row.grade}</td><td className="px-3 py-3">{money(row.billed)}</td><td className="px-3 py-3">{money(row.collected)}</td><td className="px-3 py-3">{money(row.billed - row.concession - row.collected)}</td></tr>)}</tbody></table></div>
      </section>
    </main>
  </div>;
}
