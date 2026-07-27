import { FormEvent, useEffect, useState } from "react";
import { ArrowLeft, Check, IndianRupee, Pencil, Plus, Printer, RefreshCw, Search, Send, X } from "lucide-react";
import { useNavigate } from "react-router-dom";
import {
  collectPayment, createFeeHead, createFeeStructure, FeeHead, FeeSession, FeeStructure,
  generateInvoices, getErpStudents, getFeeDues, getFeeHeads, getFeeSessions, getFeeStructures,
  getFeeSummary, getStudentFees, publishFeeStructure, StudentFeeSummary, updateFeeStructure,
  upsertFeePlan,
} from "../lib/api";

const money = (paise: number) => new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR" }).format((paise || 0) / 100);
type Tab = "overview" | "setup" | "invoices" | "payments" | "dues";
type Frequency = FeeStructure["frequency"];
interface GradeSummary { grade: string; billed: number; collected: number; concession: number }
interface FeeSummary { billed: number; collected: number; concession: number; outstanding: number; by_grade: GradeSummary[] }
interface StudentRow { id: number; full_name: string; grade: string; admission_number: string; status: string }
interface InvoicePreview { id?: number; student_id: number; invoice_number?: string; gross_paise: number; concession_paise: number; net_paise: number }
interface Receipt { receipt_number: string; amount_paise: number; method: string; allocations: Array<{ invoice_id: number; amount_paise: number }> }
interface DraftItem { fee_head_id: number; amount_rupees: string; is_optional: boolean }
const inputClass = "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100";
const buttonClass = "rounded-lg bg-blue-700 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-50";
const secondaryButtonClass = "rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50";
const toPaise = (rupees: string) => { const value = Number(rupees); return Number.isFinite(value) && value >= 0 ? Math.round(value * 100) : 0; };
const errorMessage = (error: unknown, fallback: string) => error instanceof Error ? error.message : fallback;

export default function Fees() {
  const navigate = useNavigate();
  const [tab, setTab] = useState<Tab>("overview");
  const [sessions, setSessions] = useState<FeeSession[]>([]);
  const [sessionId, setSessionId] = useState<number>();
  const [summary, setSummary] = useState<FeeSummary | null>(null);
  const [heads, setHeads] = useState<FeeHead[]>([]);
  const [structures, setStructures] = useState<FeeStructure[]>([]);
  const [grades, setGrades] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const load = async (id: number) => {
    try {
      const [summaryData, headData, structureData, studentData] = await Promise.all([
        getFeeSummary(id), getFeeHeads(), getFeeStructures({ session_id: id }), getErpStudents({ status: "active", limit: 200 }),
      ]);
      setSummary(summaryData);
      setHeads(headData.fee_heads || []);
      setStructures(structureData.fee_structures || []);
      setGrades(studentData.grades || []);
      setError("");
    } catch (loadError) { setError(errorMessage(loadError, "Unable to load fee data")); }
  };

  useEffect(() => {
    getFeeSessions().then((data) => {
      const rows: FeeSession[] = data.sessions || [];
      setSessions(rows);
      const current = rows.find((session) => session.is_current) || rows[0];
      if (current) { setSessionId(current.id); void load(current.id); }
    }).catch((loadError: unknown) => setError(errorMessage(loadError, "Unable to load sessions")));
  }, []);

  const changeSession = (value: string) => { const id = Number(value); setSessionId(id); void load(id); };
  const refresh = () => { if (sessionId) void load(sessionId); };
  return <div className="min-h-screen bg-slate-50 text-slate-900">
    <header className="border-b border-slate-200 bg-white"><div className="mx-auto flex max-w-7xl items-center gap-3 px-4 py-4 sm:px-6 lg:px-8">
      <button onClick={() => navigate("/erp")} className="rounded-lg p-2 hover:bg-slate-100" aria-label="Back to ERP"><ArrowLeft size={20} /></button>
      <IndianRupee className="text-blue-700" /><div><p className="text-xs font-semibold uppercase tracking-widest text-blue-700">School ERP</p><h1 className="text-xl font-bold">Fees &amp; payments</h1></div>
      <button onClick={refresh} className="ml-auto rounded-lg p-2 text-slate-500 hover:bg-slate-100" aria-label="Refresh"><RefreshCw size={18} /></button>
    </div></header>
    <main className="mx-auto max-w-7xl px-4 py-7 sm:px-6 lg:px-8">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4"><div><h2 className="text-2xl font-bold">Fee management</h2><p className="text-sm text-slate-500">Configure, bill, collect and review school fees.</p></div>
        <label className="text-sm font-medium text-slate-600">Academic session<select value={sessionId || ""} onChange={(event) => changeSession(event.target.value)} className={`${inputClass} mt-1 min-w-44`}>{sessions.map((session) => <option key={session.id} value={session.id}>{session.name}</option>)}</select></label>
      </div>
      {error && <div className="mb-4 flex items-center justify-between rounded-lg bg-red-50 p-3 text-sm text-red-700"><span>{error}</span><button onClick={() => setError("")}><X size={16} /></button></div>}
      {notice && <div className="mb-4 rounded-lg bg-emerald-50 p-3 text-sm text-emerald-700">{notice}</div>}
      <nav className="mb-6 flex gap-1 overflow-x-auto rounded-xl border border-slate-200 bg-white p-1">{([
        ["overview", "Overview"], ["setup", "Fee setup"], ["invoices", "Generate invoices"], ["payments", "Collect payment"], ["dues", "Defaulters / dues"],
      ] as Array<[Tab, string]>).map(([value, label]) => <button key={value} onClick={() => setTab(value)} className={`whitespace-nowrap rounded-lg px-4 py-2 text-sm font-semibold ${tab === value ? "bg-blue-700 text-white" : "text-slate-600 hover:bg-slate-100"}`}>{label}</button>)}</nav>
      {tab === "overview" && <OverviewTab summary={summary} />}
      {tab === "setup" && sessionId && <SetupTab sessionId={sessionId} grades={grades} heads={heads} structures={structures} onRefresh={refresh} onNotice={setNotice} onError={setError} />}
      {tab === "invoices" && sessionId && <InvoiceTab sessionId={sessionId} grades={grades} onError={setError} onNotice={setNotice} />}
      {tab === "payments" && sessionId && <PaymentTab sessionId={sessionId} structures={structures} onError={setError} onNotice={setNotice} />}
      {tab === "dues" && sessionId && <DuesTab sessionId={sessionId} grades={grades} onError={setError} />}
      {!sessions.length && <p className="rounded-xl border border-slate-200 bg-white p-8 text-center text-slate-500">No academic session is available.</p>}
    </main>
  </div>;
}

function OverviewTab({ summary }: { summary: FeeSummary | null }) {
  const cards: Array<[string, number]> = [["Billed", summary?.billed || 0], ["Collected", summary?.collected || 0], ["Concession", summary?.concession || 0], ["Outstanding", summary?.outstanding || 0]];
  return <section><div className="grid gap-4 sm:grid-cols-4">{cards.map(([label, value]) => <div key={label} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><p className="text-sm text-slate-500">{label}</p><p className="mt-2 text-2xl font-bold">{money(value)}</p></div>)}</div>
    <div className="mt-7 rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><h3 className="mb-4 font-semibold">Grade-wise collections</h3><div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr className="border-b text-slate-500"><th className="px-3 py-2">Grade</th><th className="px-3 py-2">Billed</th><th className="px-3 py-2">Collected</th><th className="px-3 py-2">Outstanding</th></tr></thead><tbody>{(summary?.by_grade || []).map((row) => <tr key={row.grade} className="border-b last:border-0"><td className="px-3 py-3 font-medium">{row.grade}</td><td className="px-3 py-3">{money(row.billed)}</td><td className="px-3 py-3">{money(row.collected)}</td><td className="px-3 py-3">{money(row.billed - row.concession - row.collected)}</td></tr>)}</tbody></table></div></div>
  </section>;
}

function SetupTab({ sessionId, grades, heads, structures, onRefresh, onNotice, onError }: { sessionId: number; grades: string[]; heads: FeeHead[]; structures: FeeStructure[]; onRefresh: () => void; onNotice: (value: string) => void; onError: (value: string) => void }) {
  const [headForm, setHeadForm] = useState({ code: "", name: "", is_refundable: false });
  const [structureGrade, setStructureGrade] = useState(grades[0] || "");
  const [frequency, setFrequency] = useState<Frequency>("monthly");
  const [items, setItems] = useState<DraftItem[]>([]);
  const [editingId, setEditingId] = useState<number>();
  const [saving, setSaving] = useState(false);
  useEffect(() => { if (!structureGrade && grades[0]) setStructureGrade(grades[0]); }, [grades, structureGrade]);
  const reset = () => { setEditingId(undefined); setStructureGrade(grades[0] || ""); setFrequency("monthly"); setItems([]); };
  const submitHead = async (event: FormEvent) => {
    event.preventDefault(); setSaving(true);
    try { await createFeeHead(headForm); setHeadForm({ code: "", name: "", is_refundable: false }); onNotice("Fee head created."); onRefresh(); }
    catch (submitError) { onError(errorMessage(submitError, "Fee head could not be created")); } finally { setSaving(false); }
  };
  const edit = (structure: FeeStructure) => { setEditingId(structure.id); setStructureGrade(structure.grade); setFrequency(structure.frequency); setItems(structure.items.map((item) => ({ fee_head_id: item.fee_head_id, amount_rupees: String(item.amount_paise / 100), is_optional: Boolean(item.is_optional) }))); };
  const submitStructure = async (event: FormEvent) => {
    event.preventDefault();
    if (!structureGrade || !items.length) { onError("Select a grade and add at least one fee item."); return; }
    setSaving(true);
    try {
      const body = { session_id: sessionId, grade: structureGrade, frequency, items: items.map((item) => ({ fee_head_id: item.fee_head_id, amount_paise: toPaise(item.amount_rupees), is_optional: item.is_optional })) };
      if (editingId) await updateFeeStructure(editingId, body); else await createFeeStructure(body);
      reset(); onNotice(editingId ? "Draft structure updated." : "Draft structure created."); onRefresh();
    } catch (submitError) { onError(errorMessage(submitError, "Fee structure could not be saved")); } finally { setSaving(false); }
  };
  const publish = async (id: number) => { try { await publishFeeStructure(id); onNotice("Fee structure published and locked."); onRefresh(); } catch (publishError) { onError(errorMessage(publishError, "Structure could not be published")); } };
  return <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]"><div className="space-y-6">
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><h3 className="mb-4 font-semibold">Fee heads</h3><form onSubmit={submitHead} className="space-y-3"><div className="grid gap-3 sm:grid-cols-2"><input required placeholder="Code (e.g. TUITION)" value={headForm.code} onChange={(event) => setHeadForm({ ...headForm, code: event.target.value })} className={inputClass} /><input required placeholder="Name" value={headForm.name} onChange={(event) => setHeadForm({ ...headForm, name: event.target.value })} className={inputClass} /></div><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={headForm.is_refundable} onChange={(event) => setHeadForm({ ...headForm, is_refundable: event.target.checked })} /> Refundable</label><button disabled={saving} className={buttonClass}><Plus className="mr-1 inline" size={16} />Create fee head</button></form><div className="mt-5 divide-y border-t">{heads.map((head) => <div key={head.id} className="flex items-center justify-between py-2 text-sm"><span><b>{head.code}</b> · {head.name}</span><span className="text-slate-500">{head.is_refundable ? "Refundable" : "Non-refundable"}</span></div>)}</div></section>
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><h3 className="mb-4 font-semibold">{editingId ? "Edit draft structure" : "New draft structure"}</h3><form onSubmit={submitStructure} className="space-y-3"><div className="grid gap-3 sm:grid-cols-2"><select required value={structureGrade} onChange={(event) => setStructureGrade(event.target.value)} className={inputClass}><option value="">Select grade</option>{grades.map((grade) => <option key={grade}>{grade}</option>)}</select><select value={frequency} onChange={(event) => setFrequency(event.target.value as Frequency)} className={inputClass}>{["monthly", "quarterly", "annual", "one_time"].map((value) => <option key={value}>{value}</option>)}</select></div>
      {items.map((item, index) => <div key={`${item.fee_head_id}-${index}`} className="grid grid-cols-[1fr_7rem_auto_auto] items-center gap-2"><select required value={item.fee_head_id} onChange={(event) => setItems(items.map((current, i) => i === index ? { ...current, fee_head_id: Number(event.target.value) } : current))} className={inputClass}><option value={0}>Select fee head</option>{heads.map((head) => <option key={head.id} value={head.id}>{head.name}</option>)}</select><input required min="0" step="0.01" type="number" placeholder="₹" value={item.amount_rupees} onChange={(event) => setItems(items.map((current, i) => i === index ? { ...current, amount_rupees: event.target.value } : current))} className={inputClass} /><label className="text-xs text-slate-600"><input type="checkbox" checked={item.is_optional} onChange={(event) => setItems(items.map((current, i) => i === index ? { ...current, is_optional: event.target.checked } : current))} /> Optional</label><button type="button" onClick={() => setItems(items.filter((_, i) => i !== index))} className="text-slate-400 hover:text-red-600"><X size={16} /></button></div>)}
      <button type="button" onClick={() => setItems([...items, { fee_head_id: heads[0]?.id || 0, amount_rupees: "", is_optional: false }])} className={secondaryButtonClass}><Plus className="mr-1 inline" size={16} />Add item</button><div className="flex gap-2"><button disabled={saving} className={buttonClass}>{editingId ? "Save draft" : "Create draft"}</button>{editingId && <button type="button" onClick={reset} className={secondaryButtonClass}>Cancel</button>}</div>
    </form></section></div>
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><h3 className="mb-4 font-semibold">Structures for this session</h3><div className="space-y-3">{structures.map((structure) => <div key={structure.id} className="rounded-lg border border-slate-200 p-4"><div className="flex flex-wrap items-center justify-between gap-2"><div><h4 className="font-semibold">{structure.grade} · {structure.frequency}</h4><p className="text-xs uppercase tracking-wide text-slate-500">{structure.status}</p></div>{structure.status === "draft" && <div className="flex gap-2"><button onClick={() => edit(structure)} className={secondaryButtonClass}><Pencil className="mr-1 inline" size={14} />Edit</button><button onClick={() => void publish(structure.id)} className={buttonClass}><Check className="mr-1 inline" size={14} />Publish</button></div>}</div><div className="mt-3 grid gap-2 text-sm sm:grid-cols-2">{structure.items.map((item) => <div key={item.fee_head_id} className="flex justify-between rounded bg-slate-50 px-3 py-2"><span>{item.name || item.code || `Head ${item.fee_head_id}`}{item.is_optional ? " (optional)" : ""}</span><b>{money(item.amount_paise)}</b></div>)}</div></div>)}{!structures.length && <p className="text-sm text-slate-500">No structures created for this session.</p>}</div></section>
  </div>;
}

function InvoiceTab({ sessionId, grades, onError, onNotice }: { sessionId: number; grades: string[]; onError: (value: string) => void; onNotice: (value: string) => void }) {
  const [periodCode, setPeriodCode] = useState(""); const [grade, setGrade] = useState(""); const [preview, setPreview] = useState<InvoicePreview[]>([]); const [result, setResult] = useState<{ created: InvoicePreview[]; skipped_existing: number }>(); const [loading, setLoading] = useState(false);
  const body = { session_id: sessionId, period_code: periodCode, ...(grade ? { grade } : {}) };
  const previewInvoices = async (event: FormEvent) => { event.preventDefault(); if (!periodCode) return; setLoading(true); try { const data = await generateInvoices({ ...body, dry_run: true }, crypto.randomUUID()); setPreview(data.created || []); setResult(undefined); onNotice("Preview generated. Confirm to create these invoices."); } catch (error) { onError(errorMessage(error, "Invoice preview failed")); } finally { setLoading(false); } };
  const confirmInvoices = async () => { setLoading(true); try { const data = await generateInvoices({ ...body, dry_run: false }, crypto.randomUUID()); setResult(data); setPreview([]); onNotice(`${data.created?.length || 0} invoice(s) created.`); } catch (error) { onError(errorMessage(error, "Invoice generation failed")); } finally { setLoading(false); } };
  return <section className="space-y-6"><div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><h3 className="mb-4 font-semibold">Preview invoice run</h3><form onSubmit={previewInvoices} className="grid gap-3 md:grid-cols-[1fr_1fr_1fr_auto]"><input required placeholder="Period code (e.g. 2026-04)" value={periodCode} onChange={(event) => setPeriodCode(event.target.value)} className={inputClass} /><select value={grade} onChange={(event) => setGrade(event.target.value)} className={inputClass}><option value="">All grades</option>{grades.map((item) => <option key={item}>{item}</option>)}</select><span className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-500">Session #{sessionId}</span><button disabled={loading} className={buttonClass}>Preview</button></form></div>
    {preview.length > 0 && <div className="rounded-xl border border-blue-200 bg-blue-50 p-5"><div className="mb-4 flex items-center justify-between"><h3 className="font-semibold">Invoice preview ({preview.length})</h3><button onClick={() => void confirmInvoices()} disabled={loading} className={buttonClass}><Send className="mr-1 inline" size={15} />Confirm and create</button></div><PreviewTable rows={preview} /></div>}
    {result && <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-5"><h3 className="font-semibold">Invoice run complete</h3><p className="mt-1 text-sm">{result.created.length} created · {result.skipped_existing} skipped existing</p><PreviewTable rows={result.created} /></div>}
  </section>;
}

function PreviewTable({ rows }: { rows: InvoicePreview[] }) {
  return <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr className="border-b border-blue-200 text-slate-600"><th className="px-3 py-2">Student ID</th><th className="px-3 py-2">Invoice</th><th className="px-3 py-2">Gross</th><th className="px-3 py-2">Concession</th><th className="px-3 py-2">Net</th></tr></thead><tbody>{rows.map((row) => <tr key={`${row.student_id}-${row.invoice_number || "preview"}`} className="border-b border-blue-100 last:border-0"><td className="px-3 py-2">{row.student_id}</td><td className="px-3 py-2">{row.invoice_number || "Preview"}</td><td className="px-3 py-2">{money(row.gross_paise)}</td><td className="px-3 py-2">{money(row.concession_paise)}</td><td className="px-3 py-2 font-semibold">{money(row.net_paise)}</td></tr>)}</tbody></table></div>;
}

function PaymentTab({ sessionId, structures, onError, onNotice }: { sessionId: number; structures: FeeStructure[]; onError: (value: string) => void; onNotice: (value: string) => void }) {
  const [query, setQuery] = useState(""); const [students, setStudents] = useState<StudentRow[]>([]); const [selected, setSelected] = useState<StudentRow>(); const [fees, setFees] = useState<StudentFeeSummary>(); const [amount, setAmount] = useState(""); const [method, setMethod] = useState("cash"); const [reference, setReference] = useState(""); const [bank, setBank] = useState(""); const [saving, setSaving] = useState(false); const [receipt, setReceipt] = useState<Receipt>(); const [structureId, setStructureId] = useState<number>();
  useEffect(() => { const timer = window.setTimeout(() => { getErpStudents({ search: query, status: "active", limit: 25 }).then((data) => setStudents(data.students || [])).catch(() => setStudents([])); }, 200); return () => window.clearTimeout(timer); }, [query]);
  const selectStudent = async (student: StudentRow) => { setSelected(student); setStructureId(structures.find((structure) => structure.grade === student.grade)?.id); try { setFees(await getStudentFees(student.id, sessionId)); } catch (error) { onError(errorMessage(error, "Unable to load student fees")); } };
  const assignStructure = async () => { if (!selected || !structureId) return; try { await upsertFeePlan(selected.id, { session_id: sessionId, structure_id: structureId, transport_opted: false }); await selectStudent(selected); onNotice("Fee structure assigned to student."); } catch (error) { onError(errorMessage(error, "Fee plan could not be assigned")); } };
  const submitPayment = async (event: FormEvent) => { event.preventDefault(); if (!selected || toPaise(amount) <= 0) return; setSaving(true); try { const data = await collectPayment({ student_id: selected.id, session_id: sessionId, amount_paise: toPaise(amount), method, reference_last4: reference, bank_label: bank }, crypto.randomUUID()); setReceipt(data); setFees(await getStudentFees(selected.id, sessionId)); setAmount(""); onNotice("Payment recorded successfully."); } catch (error) { onError(errorMessage(error, "Payment could not be recorded")); } finally { setSaving(false); } };
  const outstanding = fees?.dues || 0; const studentStructures = structures.filter((structure) => structure.grade === selected?.grade);
  return <section className="grid gap-6 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]"><div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><h3 className="mb-4 font-semibold">Select student</h3><div className="relative"><Search className="absolute left-3 top-2.5 text-slate-400" size={16} /><input placeholder="Search by student name" value={query} onChange={(event) => setQuery(event.target.value)} className={`${inputClass} pl-9`} /></div><div className="mt-3 divide-y">{students.map((student) => <button key={student.id} onClick={() => void selectStudent(student)} className={`block w-full px-2 py-3 text-left text-sm hover:bg-slate-50 ${selected?.id === student.id ? "bg-blue-50" : ""}`}><b>{student.full_name}</b><span className="ml-2 text-slate-500">{student.grade}</span></button>)}{query && !students.length && <p className="py-3 text-sm text-slate-500">No students found.</p>}</div></div>
    <div className="space-y-6">{selected && <><div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><h3 className="font-semibold">{selected.full_name}</h3><p className="text-sm text-slate-500">{selected.grade} · Outstanding {money(outstanding)}</p><div className="mt-4 overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr className="border-b text-slate-500"><th className="px-2 py-2">Invoice</th><th className="px-2 py-2">Due date</th><th className="px-2 py-2">Balance</th><th className="px-2 py-2">Status</th></tr></thead><tbody>{(fees?.invoices || []).filter((invoice) => invoice.status !== "cancelled").map((invoice) => <tr key={invoice.id} className="border-b last:border-0"><td className="px-2 py-2">{invoice.invoice_number}</td><td className="px-2 py-2">{invoice.due_date}</td><td className="px-2 py-2">{money(invoice.net_paise - invoice.paid_paise)}</td><td className="px-2 py-2">{invoice.status}</td></tr>)}</tbody></table></div><div className="mt-4 flex flex-wrap gap-2"><select value={structureId || ""} onChange={(event) => setStructureId(Number(event.target.value))} className={`${inputClass} max-w-xs`}><option value="">Assign a fee structure</option>{studentStructures.map((structure) => <option key={structure.id} value={structure.id}>{structure.grade} · {structure.frequency} · {money(structure.items.reduce((total, item) => total + item.amount_paise, 0))}</option>)}</select><button disabled={!structureId} onClick={() => void assignStructure()} className={secondaryButtonClass}>Assign structure</button></div></div>
      <form onSubmit={submitPayment} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><h3 className="mb-4 font-semibold">Record payment</h3><div className="grid gap-3 sm:grid-cols-2"><label className="text-sm font-medium">Amount (rupees)<input required min="0.01" step="0.01" type="number" value={amount} onChange={(event) => setAmount(event.target.value)} className={`${inputClass} mt-1`} /></label><label className="text-sm font-medium">Method<select value={method} onChange={(event) => setMethod(event.target.value)} className={`${inputClass} mt-1`}>{["cash", "cheque", "neft", "upi", "dd", "adjustment"].map((item) => <option key={item}>{item}</option>)}</select></label><label className="text-sm font-medium">Reference last 4<input maxLength={4} value={reference} onChange={(event) => setReference(event.target.value.slice(0, 4))} className={`${inputClass} mt-1`} /></label><label className="text-sm font-medium">Bank label<input value={bank} onChange={(event) => setBank(event.target.value)} className={`${inputClass} mt-1`} /></label></div><button disabled={saving || !selected} className={`${buttonClass} mt-4`}>Record payment</button></form>
      {receipt && <div className="print-receipt rounded-xl border border-emerald-200 bg-white p-5 shadow-sm"><div className="flex items-center justify-between"><h3 className="font-semibold">Receipt {receipt.receipt_number}</h3><button onClick={() => window.print()} className={secondaryButtonClass}><Printer className="mr-1 inline" size={15} />Print</button></div><p className="mt-3 text-2xl font-bold">{money(receipt.amount_paise)}</p><p className="text-sm text-slate-500">Method: {receipt.method}</p><div className="mt-4 text-sm">{receipt.allocations.map((allocation) => <p key={allocation.invoice_id}>Invoice #{allocation.invoice_id}: {money(allocation.amount_paise)}</p>)}</div></div>}</>}</div>
  </section>;
}

function DuesTab({ sessionId, grades, onError }: { sessionId: number; grades: string[]; onError: (value: string) => void }) {
  const [grade, setGrade] = useState(""); const [dues, setDues] = useState<Array<{ id: number; invoice_number: string; full_name: string; grade: string; net_paise: number; paid_paise: number; due_date: string }>>([]);
  useEffect(() => { getFeeDues(sessionId, grade).then((data) => setDues(data.dues || [])).catch((error: unknown) => onError(errorMessage(error, "Unable to load dues"))); }, [sessionId, grade, onError]);
  return <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><div className="mb-4 flex flex-wrap items-center justify-between gap-3"><div><h3 className="font-semibold">Defaulters and dues</h3><p className="text-sm text-slate-500">{dues.length} outstanding invoice(s)</p></div><select value={grade} onChange={(event) => setGrade(event.target.value)} className={`${inputClass} max-w-xs`}><option value="">All grades</option>{grades.map((item) => <option key={item}>{item}</option>)}</select></div><div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr className="border-b text-slate-500"><th className="px-3 py-2">Student</th><th className="px-3 py-2">Grade</th><th className="px-3 py-2">Invoice</th><th className="px-3 py-2">Due date</th><th className="px-3 py-2">Due</th></tr></thead><tbody>{dues.map((row) => <tr key={row.id} className="border-b last:border-0"><td className="px-3 py-3 font-medium">{row.full_name}</td><td className="px-3 py-3">{row.grade}</td><td className="px-3 py-3">{row.invoice_number}</td><td className="px-3 py-3">{row.due_date}</td><td className="px-3 py-3 font-semibold">{money(row.net_paise - row.paid_paise)}</td></tr>)}</tbody></table>{!dues.length && <p className="py-8 text-center text-sm text-slate-500">No outstanding dues found.</p>}</div></section>;
}
