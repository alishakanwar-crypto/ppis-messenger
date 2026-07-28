import { FormEvent, useCallback, useEffect, useState } from "react";
import { ArrowLeft, BriefcaseBusiness, Check, RefreshCw, X } from "lucide-react";
import { useNavigate } from "react-router-dom";
import {
  Payslip,
  PayrollRun,
  StaffMember,
  createPayrollRun,
  createStaff,
  finalizePayroll,
  generatePayroll,
  getPayrollRun,
  getStaffSummary,
  listPayrollRuns,
  listStaff,
  updatePayslip,
  updateStaff,
} from "../lib/api";

const inputClass = "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-rose-500 focus:ring-2 focus:ring-rose-100";
const buttonClass = "rounded-lg bg-rose-600 px-4 py-2 text-sm font-semibold text-white hover:bg-rose-700 disabled:cursor-not-allowed disabled:opacity-50";
const secondaryButtonClass = "rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50";
const errorMessage = (error: unknown, fallback: string) => error instanceof Error ? error.message : fallback;
type Tab = "staff" | "payroll";
type StaffForm = { full_name: string; role: string; department: string; phone: string; email: string; date_of_joining: string; monthly_ctc: string; status: StaffMember["status"] };
const emptyForm: StaffForm = { full_name: "", role: "", department: "", phone: "", email: "", date_of_joining: "", monthly_ctc: "", status: "active" };

export default function Staff() {
  const navigate = useNavigate();
  const [tab, setTab] = useState<Tab>("staff");
  const [staff, setStaff] = useState<StaffMember[]>([]);
  const [departments, setDepartments] = useState<string[]>([]);
  const [summary, setSummary] = useState<{ total_monthly_ctc: number } | null>(null);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [department, setDepartment] = useState("");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [form, setForm] = useState(emptyForm);
  const [editingId, setEditingId] = useState<number>();
  const [runs, setRuns] = useState<PayrollRun[]>([]);
  const [runId, setRunId] = useState<number>();
  const [run, setRun] = useState<PayrollRun | null>(null);
  const [month, setMonth] = useState(new Date().toISOString().slice(0, 7));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const loadStaff = useCallback(async () => {
    const [data, summaryData] = await Promise.all([
      listStaff({ search, status, department, page, limit: 50 }),
      getStaffSummary(),
    ]);
    setStaff(data.items || []);
    setTotal(data.total || 0);
    setSummary(summaryData);
    setDepartments((summaryData.by_department || []).map((item: { department: string }) => item.department).filter(Boolean));
  }, [department, page, search, status]);
  const loadRuns = useCallback(async () => {
    const data = await listPayrollRuns();
    setRuns(data.runs || []);
    if (!runId && data.runs?.length) setRunId(data.runs[0].id);
  }, [runId]);
  const loadRun = useCallback(async (id: number) => setRun(await getPayrollRun(id)), []);

  useEffect(() => { loadStaff().catch((loadError: unknown) => setError(errorMessage(loadError, "Unable to load staff"))); }, [loadStaff]);
  useEffect(() => { loadRuns().catch((loadError: unknown) => setError(errorMessage(loadError, "Unable to load payroll runs"))); }, [loadRuns]);
  useEffect(() => { if (runId) loadRun(runId).catch((loadError: unknown) => setError(errorMessage(loadError, "Unable to load payroll run"))); }, [loadRun, runId]);

  const submitStaff = async (event: FormEvent) => {
    event.preventDefault();
    setSaving(true);
    try {
      const body = { full_name: form.full_name, role: form.role, department: form.department, phone: form.phone, email: form.email, date_of_joining: form.date_of_joining, monthly_ctc: Number(form.monthly_ctc || 0), status: form.status };
      if (editingId) await updateStaff(editingId, body); else await createStaff(body);
      setForm(emptyForm); setEditingId(undefined); setNotice(editingId ? "Staff updated." : "Staff member created."); await loadStaff();
    } catch (saveError) { setError(errorMessage(saveError, "Staff could not be saved")); } finally { setSaving(false); }
  };
  const editStaff = (member: StaffMember) => setForm({ full_name: member.full_name, role: member.role, department: member.department, phone: member.phone, email: member.email, date_of_joining: member.date_of_joining, monthly_ctc: String(member.monthly_ctc), status: member.status });
  const createRun = async (event: FormEvent) => {
    event.preventDefault();
    try { const result = await createPayrollRun(month); setRunId(result.id); setNotice("Payroll run ready."); await loadRuns(); await loadRun(result.id); } catch (runError) { setError(errorMessage(runError, "Payroll run could not be created")); }
  };
  const generate = async () => {
    if (!runId) return;
    try { await generatePayroll(runId); setNotice("Payslips generated."); await loadRun(runId); await loadRuns(); } catch (generateError) { setError(errorMessage(generateError, "Payslips could not be generated")); }
  };
  const editPayslip = async (payslip: Payslip) => {
    const gross = window.prompt("Gross amount (rupees)", String(payslip.gross));
    if (gross === null) return;
    const deductions = window.prompt("Deductions (rupees)", String(payslip.deductions));
    if (deductions === null || !runId) return;
    try { await updatePayslip(payslip.id, { gross: Number(gross), deductions: Number(deductions), remarks: payslip.remarks }); await loadRun(runId); } catch (editError) { setError(errorMessage(editError, "Payslip could not be updated")); }
  };
  const finalize = async () => {
    if (!runId) return;
    try { await finalizePayroll(runId); setNotice("Payroll finalized and locked."); await loadRun(runId); await loadRuns(); } catch (finalizeError) { setError(errorMessage(finalizeError, "Payroll could not be finalized")); }
  };
  const pages = Math.max(1, Math.ceil(total / 50));
  return <div className="min-h-screen bg-slate-50 text-slate-900">
    <header className="border-b border-slate-200 bg-white"><div className="mx-auto flex max-w-7xl items-center gap-3 px-4 py-4 sm:px-6 lg:px-8"><button onClick={() => navigate("/erp")} className="rounded-lg p-2 hover:bg-slate-100" aria-label="Back to ERP"><ArrowLeft size={20} /></button><BriefcaseBusiness className="text-rose-600" /><div><p className="text-xs font-semibold uppercase tracking-widest text-rose-600">School ERP</p><h1 className="text-xl font-bold">Staff &amp; Payroll</h1></div><button onClick={() => { void loadStaff(); void loadRuns(); }} className="ml-auto rounded-lg p-2 text-slate-500 hover:bg-slate-100" aria-label="Refresh"><RefreshCw size={18} /></button></div></header>
    <main className="mx-auto max-w-7xl px-4 py-7 sm:px-6 lg:px-8"><div className="mb-6"><h2 className="text-2xl font-bold">Staff &amp; Payroll</h2><p className="text-sm text-slate-500">Manage staff records and monthly payslips.</p></div>
      {error && <div className="mb-4 flex items-center justify-between rounded-lg bg-red-50 p-3 text-sm text-red-700"><span>{error}</span><button onClick={() => setError("")}><X size={16} /></button></div>}{notice && <div className="mb-4 rounded-lg bg-emerald-50 p-3 text-sm text-emerald-700">{notice}</div>}
      <nav className="mb-6 flex gap-1 rounded-xl border border-slate-200 bg-white p-1">{([["staff", "Staff"], ["payroll", "Payroll"]] as Array<[Tab, string]>).map(([value, label]) => <button key={value} onClick={() => setTab(value)} className={`rounded-lg px-4 py-2 text-sm font-semibold ${tab === value ? "bg-rose-600 text-white" : "text-slate-600 hover:bg-slate-100"}`}>{label}</button>)}</nav>
      {tab === "staff" && <StaffTab staff={staff} total={total} pages={pages} page={page} setPage={setPage} search={search} setSearch={(value) => { setSearch(value); setPage(1); }} status={status} setStatus={(value) => { setStatus(value); setPage(1); }} department={department} setDepartment={(value) => { setDepartment(value); setPage(1); }} departments={departments} summary={summary} form={form} setForm={setForm} editingId={editingId} setEditingId={setEditingId} onSubmit={submitStaff} onEdit={editStaff} saving={saving} />}
      {tab === "payroll" && <PayrollTab runs={runs} run={run} runId={runId} setRunId={setRunId} month={month} setMonth={setMonth} onCreate={createRun} onGenerate={generate} onEdit={editPayslip} onFinalize={finalize} />}
    </main>
  </div>;
}

function StaffTab({ staff, total, pages, page, setPage, search, setSearch, status, setStatus, department, setDepartment, departments, summary, form, setForm, editingId, setEditingId, onSubmit, onEdit, saving }: { staff: StaffMember[]; total: number; pages: number; page: number; setPage: (value: number) => void; search: string; setSearch: (value: string) => void; status: string; setStatus: (value: string) => void; department: string; setDepartment: (value: string) => void; departments: string[]; summary: { total_monthly_ctc: number } | null; form: StaffForm; setForm: (value: StaffForm) => void; editingId?: number; setEditingId: (value?: number) => void; onSubmit: (event: FormEvent) => void; onEdit: (member: StaffMember) => void; saving: boolean }) {
  const update = (key: keyof StaffForm, value: string) => setForm({ ...form, [key]: value });
  return <section className="space-y-5"><div className="grid gap-4 sm:grid-cols-2"><div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm"><p className="text-sm text-slate-500">Active monthly CTC</p><p className="mt-1 text-2xl font-bold">₹{(summary?.total_monthly_ctc || 0).toLocaleString("en-IN", { minimumFractionDigits: 2 })}</p></div><div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm"><p className="text-sm text-slate-500">Staff records</p><p className="mt-1 text-2xl font-bold">{total}</p></div></div>
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]"><div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><div className="mb-4 grid gap-3 sm:grid-cols-3"><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search name, code or phone" className={inputClass} /><select value={status} onChange={(event) => setStatus(event.target.value)} className={inputClass}><option value="">All statuses</option><option value="active">Active</option><option value="inactive">Inactive</option></select><select value={department} onChange={(event) => setDepartment(event.target.value)} className={inputClass}><option value="">All departments</option>{departments.map((item) => <option key={item}>{item}</option>)}</select></div><div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr className="border-b text-slate-500"><th className="px-2 py-2">Employee</th><th className="px-2 py-2">Role / dept.</th><th className="px-2 py-2">CTC</th><th className="px-2 py-2">Status</th><th /></tr></thead><tbody>{staff.map((member) => <tr key={member.id} className="border-b last:border-0"><td className="px-2 py-3"><b>{member.full_name}</b><span className="block text-xs text-slate-500">{member.employee_code}</span></td><td className="px-2 py-3">{member.role}<span className="block text-xs text-slate-500">{member.department}</span></td><td className="px-2 py-3">₹{member.monthly_ctc.toLocaleString("en-IN", { minimumFractionDigits: 2 })}</td><td className="px-2 py-3">{member.status}</td><td className="px-2 py-3"><button onClick={() => { onEdit(member); setEditingId(member.id); }} className={secondaryButtonClass}>Edit</button></td></tr>)}</tbody></table></div><div className="mt-4 flex items-center justify-between text-sm text-slate-500"><span>{total} staff</span><div className="flex gap-2"><button disabled={page <= 1} onClick={() => setPage(page - 1)} className={secondaryButtonClass}>Previous</button><span className="px-2 py-2">Page {page} of {pages}</span><button disabled={page >= pages} onClick={() => setPage(page + 1)} className={secondaryButtonClass}>Next</button></div></div></div>
      <form onSubmit={onSubmit} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><h3 className="mb-4 font-semibold">{editingId ? "Edit staff" : "Add staff"}</h3><div className="space-y-3"><label className="text-sm font-medium">Full name<input required value={form.full_name} onChange={(event) => update("full_name", event.target.value)} className={`${inputClass} mt-1`} /></label><div className="grid gap-3 sm:grid-cols-2"><label className="text-sm font-medium">Role<input value={form.role} onChange={(event) => update("role", event.target.value)} className={`${inputClass} mt-1`} /></label><label className="text-sm font-medium">Department<input value={form.department} onChange={(event) => update("department", event.target.value)} className={`${inputClass} mt-1`} /></label><label className="text-sm font-medium">Phone<input value={form.phone} onChange={(event) => update("phone", event.target.value)} className={`${inputClass} mt-1`} /></label><label className="text-sm font-medium">Email<input type="email" value={form.email} onChange={(event) => update("email", event.target.value)} className={`${inputClass} mt-1`} /></label><label className="text-sm font-medium">Joining date<input type="date" value={form.date_of_joining} onChange={(event) => update("date_of_joining", event.target.value)} className={`${inputClass} mt-1`} /></label><label className="text-sm font-medium">Monthly CTC (₹)<input type="number" min="0" step="0.01" value={form.monthly_ctc} onChange={(event) => update("monthly_ctc", event.target.value)} className={`${inputClass} mt-1`} /></label></div><label className="text-sm font-medium">Status<select value={form.status} onChange={(event) => update("status", event.target.value as StaffMember["status"])} className={`${inputClass} mt-1`}><option value="active">Active</option><option value="inactive">Inactive</option></select></label></div><div className="mt-4 flex gap-2"><button disabled={saving} className={buttonClass}>{editingId ? "Update staff" : "Add staff"}</button>{editingId && <button type="button" onClick={() => { setEditingId(undefined); setForm(emptyForm); }} className={secondaryButtonClass}>Cancel</button>}</div></form></div>
  </section>;
}

function PayrollTab({ runs, run, runId, setRunId, month, setMonth, onCreate, onGenerate, onEdit, onFinalize }: { runs: PayrollRun[]; run: PayrollRun | null; runId?: number; setRunId: (value: number) => void; month: string; setMonth: (value: string) => void; onCreate: (event: FormEvent) => void; onGenerate: () => void; onEdit: (payslip: Payslip) => void; onFinalize: () => void }) {
  return <section className="space-y-5"><div className="flex flex-wrap items-end gap-3 rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><form onSubmit={onCreate} className="flex items-end gap-2"><label className="text-sm font-medium">New month<input required type="month" value={month} onChange={(event) => setMonth(event.target.value)} className={`${inputClass} mt-1`} /></label><button className={buttonClass}>Create / select run</button></form><label className="text-sm font-medium">Payroll run<select value={runId || ""} onChange={(event) => setRunId(Number(event.target.value))} className={`${inputClass} mt-1 min-w-48`}><option value="">Select run</option>{runs.map((item) => <option key={item.id} value={item.id}>{item.month} · {item.status}</option>)}</select></label></div>{run && <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><div className="mb-4 flex flex-wrap items-center justify-between gap-3"><div><h3 className="font-semibold">Payroll for {run.month}</h3><p className="text-sm text-slate-500">Gross ₹{(run.total_gross || 0).toLocaleString("en-IN", { minimumFractionDigits: 2 })} · Deductions ₹{(run.total_deductions || 0).toLocaleString("en-IN", { minimumFractionDigits: 2 })} · Net ₹{(run.total_net || 0).toLocaleString("en-IN", { minimumFractionDigits: 2 })}</p></div><div className="flex gap-2">{run.status === "draft" && <><button onClick={onGenerate} className={secondaryButtonClass}>Generate payslips</button><button onClick={onFinalize} className={buttonClass}><Check className="mr-1 inline" size={16} />Finalize</button></>}</div></div><div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr className="border-b text-slate-500"><th className="px-2 py-2">Staff</th><th className="px-2 py-2">Gross</th><th className="px-2 py-2">Deductions</th><th className="px-2 py-2">Net</th><th /></tr></thead><tbody>{(run.payslips || []).map((payslip) => <tr key={payslip.id} className="border-b last:border-0"><td className="px-2 py-3">{payslip.full_name}<span className="block text-xs text-slate-500">{payslip.employee_code}</span></td><td className="px-2 py-3">₹{payslip.gross.toLocaleString("en-IN", { minimumFractionDigits: 2 })}</td><td className="px-2 py-3">₹{payslip.deductions.toLocaleString("en-IN", { minimumFractionDigits: 2 })}</td><td className="px-2 py-3 font-semibold">₹{payslip.net.toLocaleString("en-IN", { minimumFractionDigits: 2 })}</td><td className="px-2 py-3">{run.status === "draft" && <button onClick={() => onEdit(payslip)} className={secondaryButtonClass}>Edit</button>}</td></tr>)}</tbody></table>{!run.payslips?.length && <p className="py-8 text-center text-sm text-slate-500">Generate payslips for active staff.</p>}</div></div>}</section>;
}
