import { FormEvent, useCallback, useEffect, useState } from "react";
import { ArrowLeft, Check, RefreshCw, Search, UserPlus, X } from "lucide-react";
import { useNavigate } from "react-router-dom";
import {
  AdmissionEnquiry,
  FeeSession,
  convertAdmission,
  createAdmission,
  getAdmissionsSummary,
  getFeeSessions,
  listAdmissions,
  setAdmissionStatus,
} from "../lib/api";

const inputClass = "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-violet-500 focus:ring-2 focus:ring-violet-100";
const buttonClass = "rounded-lg bg-violet-700 px-4 py-2 text-sm font-semibold text-white hover:bg-violet-800 disabled:cursor-not-allowed disabled:opacity-50";
const secondaryButtonClass = "rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50";
const statuses: AdmissionEnquiry["status"][] = ["enquiry", "applied", "shortlisted", "offered", "admitted", "rejected", "withdrawn"];
const statusColors: Record<AdmissionEnquiry["status"], string> = {
  enquiry: "bg-slate-100 text-slate-700",
  applied: "bg-blue-100 text-blue-700",
  shortlisted: "bg-amber-100 text-amber-700",
  offered: "bg-violet-100 text-violet-700",
  admitted: "bg-emerald-100 text-emerald-700",
  rejected: "bg-red-100 text-red-700",
  withdrawn: "bg-slate-200 text-slate-600",
};
const errorMessage = (error: unknown, fallback: string) => error instanceof Error ? error.message : fallback;

type Tab = "pipeline" | "new";
type FormState = {
  applicant_name: string; grade_applying: string; date_of_birth: string; gender: string;
  parent_name: string; parent_phone: string; parent_email: string; address: string;
  previous_school: string; source: string; notes: string; session_id: string;
};
const emptyForm: FormState = {
  applicant_name: "", grade_applying: "", date_of_birth: "", gender: "", parent_name: "",
  parent_phone: "", parent_email: "", address: "", previous_school: "", source: "", notes: "", session_id: "",
};

export default function Admissions() {
  const navigate = useNavigate();
  const [tab, setTab] = useState<Tab>("pipeline");
  const [sessions, setSessions] = useState<FeeSession[]>([]);
  const [grades, setGrades] = useState<string[]>([]);
  const [items, setItems] = useState<AdmissionEnquiry[]>([]);
  const [summary, setSummary] = useState<{ by_status: Array<{ status: string; count: number }>; by_grade: Array<{ grade: string; count: number }> } | null>(null);
  const [status, setStatus] = useState("");
  const [grade, setGrade] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [form, setForm] = useState(emptyForm);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const load = useCallback(async () => {
    const [data, summaryData] = await Promise.all([
      listAdmissions({ status, grade, search, page, limit: 50 }),
      getAdmissionsSummary(),
    ]);
    setItems(data.items || []);
    setTotal(data.total || 0);
    setSummary(summaryData);
  }, [grade, page, search, status]);

  useEffect(() => {
    getFeeSessions().then((data) => {
      const sessionRows: FeeSession[] = data.sessions || [];
      setSessions(sessionRows);
      const current = sessionRows.find((session) => session.is_current) || sessionRows[0];
      if (current) setForm((previous) => ({ ...previous, session_id: String(current.id) }));
    }).catch((loadError: unknown) => setError(errorMessage(loadError, "Unable to load sessions")));
  }, []);

  useEffect(() => {
    getAdmissionsSummary().then((data) => {
      const values = data.by_grade || [];
      setGrades(values.map((item: { grade: string }) => item.grade).filter(Boolean));
    }).catch(() => undefined);
  }, []);

  useEffect(() => {
    load().catch((loadError: unknown) => setError(errorMessage(loadError, "Unable to load admissions")));
  }, [load]);

  const refresh = () => {
    load().catch((loadError: unknown) => setError(errorMessage(loadError, "Unable to load admissions")));
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setSaving(true);
    try {
      await createAdmission({
        applicant_name: form.applicant_name,
        grade_applying: form.grade_applying,
        date_of_birth: form.date_of_birth,
        gender: form.gender,
        parent_name: form.parent_name,
        parent_phone: form.parent_phone,
        parent_email: form.parent_email,
        address: form.address,
        previous_school: form.previous_school,
        source: form.source,
        notes: form.notes,
        session_id: form.session_id ? Number(form.session_id) : undefined,
      });
      setForm({ ...emptyForm, session_id: form.session_id });
      setNotice("Admission enquiry created.");
      setTab("pipeline");
      await load();
    } catch (saveError) {
      setError(errorMessage(saveError, "Admission enquiry could not be created"));
    } finally {
      setSaving(false);
    }
  };

  const updateStatus = async (id: number, nextStatus: AdmissionEnquiry["status"]) => {
    try {
      await setAdmissionStatus(id, nextStatus);
      setNotice("Admission status updated.");
      await load();
    } catch (statusError) {
      setError(errorMessage(statusError, "Status could not be updated"));
    }
  };

  const convert = async (id: number) => {
    try {
      const result = await convertAdmission(id);
      setNotice(`Converted to student #${result.student_id}.`);
      await load();
    } catch (convertError) {
      setError(errorMessage(convertError, "Admission could not be converted"));
    }
  };

  return <div className="min-h-screen bg-slate-50 text-slate-900">
    <header className="border-b border-slate-200 bg-white"><div className="mx-auto flex max-w-7xl items-center gap-3 px-4 py-4 sm:px-6 lg:px-8">
      <button onClick={() => navigate("/erp")} className="rounded-lg p-2 hover:bg-slate-100" aria-label="Back to ERP"><ArrowLeft size={20} /></button>
      <UserPlus className="text-violet-700" /><div><p className="text-xs font-semibold uppercase tracking-widest text-violet-700">School ERP</p><h1 className="text-xl font-bold">Admissions</h1></div>
      <button onClick={refresh} className="ml-auto rounded-lg p-2 text-slate-500 hover:bg-slate-100" aria-label="Refresh"><RefreshCw size={18} /></button>
    </div></header>
    <main className="mx-auto max-w-7xl px-4 py-7 sm:px-6 lg:px-8">
      <div className="mb-6"><h2 className="text-2xl font-bold">Admissions pipeline</h2><p className="text-sm text-slate-500">Track enquiries from first contact through admission.</p></div>
      {error && <div className="mb-4 flex items-center justify-between rounded-lg bg-red-50 p-3 text-sm text-red-700"><span>{error}</span><button onClick={() => setError("")}><X size={16} /></button></div>}
      {notice && <div className="mb-4 rounded-lg bg-emerald-50 p-3 text-sm text-emerald-700">{notice}</div>}
      <nav className="mb-6 flex gap-1 rounded-xl border border-slate-200 bg-white p-1">{([["pipeline", "Pipeline"], ["new", "New enquiry"]] as Array<[Tab, string]>).map(([value, label]) => <button key={value} onClick={() => setTab(value)} className={`rounded-lg px-4 py-2 text-sm font-semibold ${tab === value ? "bg-violet-700 text-white" : "text-slate-600 hover:bg-slate-100"}`}>{label}</button>)}</nav>
      {tab === "pipeline" && <Pipeline items={items} total={total} page={page} setPage={setPage} status={status} setStatus={(value) => { setStatus(value); setPage(1); }} grade={grade} setGrade={(value) => { setGrade(value); setPage(1); }} search={search} setSearch={(value) => { setSearch(value); setPage(1); }} grades={grades} summary={summary} onStatus={updateStatus} onConvert={convert} />}
      {tab === "new" && <NewEnquiry form={form} setForm={setForm} sessions={sessions} grades={grades} onSubmit={submit} saving={saving} />}
    </main>
  </div>;
}

function Pipeline({ items, total, page, setPage, status, setStatus, grade, setGrade, search, setSearch, grades, summary, onStatus, onConvert }: { items: AdmissionEnquiry[]; total: number; page: number; setPage: (value: number) => void; status: string; setStatus: (value: string) => void; grade: string; setGrade: (value: string) => void; search: string; setSearch: (value: string) => void; grades: string[]; summary: { by_status: Array<{ status: string; count: number }> } | null; onStatus: (id: number, status: AdmissionEnquiry["status"]) => void; onConvert: (id: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / 50));
  return <section className="space-y-5"><div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{(summary?.by_status || []).map((row) => <div key={row.status} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm"><p className="text-xs font-semibold uppercase text-slate-500">{row.status}</p><p className="mt-1 text-2xl font-bold">{row.count}</p></div>)}</div>
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><div className="mb-4 grid gap-3 md:grid-cols-[1fr_12rem_12rem_auto]"><label className="relative text-sm font-medium"><Search className="absolute left-3 top-9 text-slate-400" size={16} /><span>Search</span><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Name, application or phone" className={`${inputClass} mt-1 pl-9`} /></label><label className="text-sm font-medium">Status<select value={status} onChange={(event) => setStatus(event.target.value)} className={`${inputClass} mt-1`}><option value="">All statuses</option>{statuses.map((item) => <option key={item}>{item}</option>)}</select></label><label className="text-sm font-medium">Grade<select value={grade} onChange={(event) => setGrade(event.target.value)} className={`${inputClass} mt-1`}><option value="">All grades</option>{grades.map((item) => <option key={item}>{item}</option>)}</select></label></div>
      <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr className="border-b text-slate-500"><th className="px-3 py-2">Application</th><th className="px-3 py-2">Applicant</th><th className="px-3 py-2">Grade</th><th className="px-3 py-2">Parent phone</th><th className="px-3 py-2">Status</th><th className="px-3 py-2">Action</th></tr></thead><tbody>{items.map((item) => <tr key={item.id} className="border-b last:border-0"><td className="px-3 py-3 font-medium">{item.application_number}</td><td className="px-3 py-3">{item.applicant_name}</td><td className="px-3 py-3">{item.grade_applying || "—"}</td><td className="px-3 py-3">{item.parent_phone || "—"}</td><td className="px-3 py-3"><select value={item.status} onChange={(event) => onStatus(item.id, event.target.value as AdmissionEnquiry["status"])} className={`rounded-full border-0 px-2 py-1 text-xs font-semibold ${statusColors[item.status]}`}>{statuses.map((option) => <option key={option}>{option}</option>)}</select></td><td className="px-3 py-3">{(item.status === "offered" || item.status === "admitted") && !item.student_id && <button onClick={() => onConvert(item.id)} className={`${secondaryButtonClass} inline-flex items-center gap-1`}><Check size={15} />Convert</button>}{item.student_id && <span className="text-xs text-emerald-700">Student #{item.student_id}</span>}</td></tr>)}</tbody></table>{!items.length && <p className="py-8 text-center text-sm text-slate-500">No admission enquiries found.</p>}</div>
      <div className="mt-4 flex items-center justify-between text-sm text-slate-500"><span>{total} enquiry/enquiries</span><div className="flex gap-2"><button disabled={page <= 1} onClick={() => setPage(page - 1)} className={secondaryButtonClass}>Previous</button><span className="px-2 py-2">Page {page} of {pages}</span><button disabled={page >= pages} onClick={() => setPage(page + 1)} className={secondaryButtonClass}>Next</button></div></div>
    </div>
  </section>;
}

function NewEnquiry({ form, setForm, sessions, grades, onSubmit, saving }: { form: FormState; setForm: (value: FormState) => void; sessions: FeeSession[]; grades: string[]; onSubmit: (event: FormEvent) => void; saving: boolean }) {
  const update = (key: keyof FormState, value: string) => setForm({ ...form, [key]: value });
  return <form onSubmit={onSubmit} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><h3 className="mb-4 font-semibold">Create admission enquiry</h3><div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3"><label className="text-sm font-medium">Applicant name<input required value={form.applicant_name} onChange={(event) => update("applicant_name", event.target.value)} className={`${inputClass} mt-1`} /></label><label className="text-sm font-medium">Grade applying<select value={form.grade_applying} onChange={(event) => update("grade_applying", event.target.value)} className={`${inputClass} mt-1`}><option value="">Select grade</option>{grades.map((item) => <option key={item}>{item}</option>)}</select></label><label className="text-sm font-medium">Academic session<select value={form.session_id} onChange={(event) => update("session_id", event.target.value)} className={`${inputClass} mt-1`}><option value="">Optional</option>{sessions.map((session) => <option key={session.id} value={session.id}>{session.name}</option>)}</select></label><label className="text-sm font-medium">Date of birth<input type="date" value={form.date_of_birth} onChange={(event) => update("date_of_birth", event.target.value)} className={`${inputClass} mt-1`} /></label><label className="text-sm font-medium">Gender<input value={form.gender} onChange={(event) => update("gender", event.target.value)} className={`${inputClass} mt-1`} /></label><label className="text-sm font-medium">Parent name<input value={form.parent_name} onChange={(event) => update("parent_name", event.target.value)} className={`${inputClass} mt-1`} /></label><label className="text-sm font-medium">Parent phone<input value={form.parent_phone} onChange={(event) => update("parent_phone", event.target.value)} className={`${inputClass} mt-1`} /></label><label className="text-sm font-medium">Parent email<input type="email" value={form.parent_email} onChange={(event) => update("parent_email", event.target.value)} className={`${inputClass} mt-1`} /></label><label className="text-sm font-medium">Previous school<input value={form.previous_school} onChange={(event) => update("previous_school", event.target.value)} className={`${inputClass} mt-1`} /></label><label className="text-sm font-medium">Source<input placeholder="Website, referral..." value={form.source} onChange={(event) => update("source", event.target.value)} className={`${inputClass} mt-1`} /></label><label className="text-sm font-medium sm:col-span-2">Address<input value={form.address} onChange={(event) => update("address", event.target.value)} className={`${inputClass} mt-1`} /></label><label className="text-sm font-medium sm:col-span-2 lg:col-span-3">Notes<textarea value={form.notes} onChange={(event) => update("notes", event.target.value)} className={`${inputClass} mt-1`} rows={3} /></label></div><button disabled={saving} className={`${buttonClass} mt-5`}>{saving ? "Saving..." : "Create enquiry"}</button></form>;
}
