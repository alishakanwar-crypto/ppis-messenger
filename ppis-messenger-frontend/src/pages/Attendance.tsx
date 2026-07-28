import { FormEvent, useCallback, useEffect, useState } from "react";
import { ArrowLeft, CalendarCheck, Check, RefreshCw, X } from "lucide-react";
import { useNavigate } from "react-router-dom";
import {
  AttendanceStudent,
  FeeSession,
  LeaveRequest,
  createLeaveRequest,
  decideLeaveRequest,
  getAttendanceRoster,
  getAttendanceSummary,
  getErpStudents,
  getFeeSessions,
  listLeaveRequests,
  markAttendance,
} from "../lib/api";

const inputClass = "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100";
const buttonClass = "rounded-lg bg-blue-700 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-50";
const secondaryButtonClass = "rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50";
const statuses = ["present", "absent", "late", "half_day", "leave", "holiday"];
const todayIst = () => new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata" }).format(new Date());
const errorMessage = (error: unknown, fallback: string) => error instanceof Error ? error.message : fallback;

type Tab = "mark" | "summary" | "leave";

export default function Attendance() {
  const navigate = useNavigate();
  const [tab, setTab] = useState<Tab>("mark");
  const [sessions, setSessions] = useState<FeeSession[]>([]);
  const [sessionId, setSessionId] = useState<number>();
  const [grades, setGrades] = useState<string[]>([]);
  const [grade, setGrade] = useState("");
  const [date, setDate] = useState(todayIst());
  const [roster, setRoster] = useState<AttendanceStudent[]>([]);
  const [statusMap, setStatusMap] = useState<Record<number, string>>({});
  const [summary, setSummary] = useState<{ days: Array<{ date: string; counts: Record<string, number> }>; students: Array<{ student_id: number; full_name: string; grade: string; present: number; total: number; percentage: number }> } | null>(null);
  const [students, setStudents] = useState<Array<{ id: number; full_name: string; grade: string }>>([]);
  const [leaves, setLeaves] = useState<LeaveRequest[]>([]);
  const [from, setFrom] = useState(todayIst());
  const [to, setTo] = useState(todayIst());
  const [leaveForm, setLeaveForm] = useState({ student_id: "", from_date: todayIst(), to_date: todayIst(), leave_type: "sick" as "sick" | "casual" | "other", reason: "" });
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [saving, setSaving] = useState(false);

  const loadRoster = useCallback(async (id: number) => {
    const data = await getAttendanceRoster({ grade, date, session_id: id });
    setRoster(data.students || []);
    setStatusMap(Object.fromEntries((data.students || []).filter((row: AttendanceStudent) => row.status).map((row: AttendanceStudent) => [row.student_id, row.status || ""])));
  }, [date, grade]);

  const loadSummary = async (id: number) => {
    setSummary(await getAttendanceSummary({ grade, from, to, session_id: id }));
  };

  const loadLeaves = async () => {
    const data = await listLeaveRequests();
    setLeaves(data.leave_requests || []);
  };

  useEffect(() => {
    getFeeSessions().then((data) => {
      const rows = data.sessions || [];
      setSessions(rows);
      const current = rows.find((item: FeeSession) => item.is_current) || rows[0];
      if (current) {
        setSessionId(current.id);
        void loadRoster(current.id);
      }
    }).catch((loadError: unknown) => setError(errorMessage(loadError, "Unable to load sessions")));
    getErpStudents({ status: "active", limit: 200 }).then((data) => {
      setGrades(data.grades || []);
      setStudents(data.students || []);
    }).catch((loadError: unknown) => setError(errorMessage(loadError, "Unable to load students")));
    void loadLeaves().catch((loadError: unknown) => setError(errorMessage(loadError, "Unable to load leave requests")));
  }, [loadRoster]);

  const refresh = () => {
    if (!sessionId) return;
    if (tab === "mark") void loadRoster(sessionId).catch((loadError: unknown) => setError(errorMessage(loadError, "Unable to load attendance")));
    if (tab === "summary") void loadSummary(sessionId).catch((loadError: unknown) => setError(errorMessage(loadError, "Unable to load summary")));
    if (tab === "leave") void loadLeaves().catch((loadError: unknown) => setError(errorMessage(loadError, "Unable to load leave requests")));
  };

  const changeSession = (value: string) => {
    const id = Number(value);
    setSessionId(id);
    if (tab === "mark") void loadRoster(id);
    if (tab === "summary") void loadSummary(id);
  };

  const submitAttendance = async () => {
    if (!sessionId) return;
    setSaving(true);
    try {
      await markAttendance({
        session_id: sessionId,
        date,
        entries: roster.filter((row) => statusMap[row.student_id]).map((row) => ({
          student_id: row.student_id,
          status: statusMap[row.student_id],
        })),
      });
      setNotice("Attendance marked successfully.");
      await loadRoster(sessionId);
    } catch (saveError) {
      setError(errorMessage(saveError, "Attendance could not be saved"));
    } finally {
      setSaving(false);
    }
  };

  const submitLeave = async (event: FormEvent) => {
    event.preventDefault();
    if (!sessionId) return;
    setSaving(true);
    try {
      await createLeaveRequest({ ...leaveForm, student_id: Number(leaveForm.student_id), session_id: sessionId });
      setLeaveForm({ ...leaveForm, student_id: "", reason: "" });
      setNotice("Leave request created.");
      await loadLeaves();
    } catch (saveError) {
      setError(errorMessage(saveError, "Leave request could not be created"));
    } finally {
      setSaving(false);
    }
  };

  const decide = async (id: number, decision: "approved" | "rejected") => {
    try {
      await decideLeaveRequest(id, decision);
      setNotice(`Leave request ${decision}.`);
      await loadLeaves();
    } catch (decisionError) {
      setError(errorMessage(decisionError, "Leave request could not be updated"));
    }
  };

  return <div className="min-h-screen bg-slate-50 text-slate-900">
    <header className="border-b border-slate-200 bg-white"><div className="mx-auto flex max-w-7xl items-center gap-3 px-4 py-4 sm:px-6 lg:px-8">
      <button onClick={() => navigate("/erp")} className="rounded-lg p-2 hover:bg-slate-100" aria-label="Back to ERP"><ArrowLeft size={20} /></button>
      <CalendarCheck className="text-blue-700" /><div><p className="text-xs font-semibold uppercase tracking-widest text-blue-700">School ERP</p><h1 className="text-xl font-bold">Attendance &amp; Leave</h1></div>
      <button onClick={refresh} className="ml-auto rounded-lg p-2 text-slate-500 hover:bg-slate-100" aria-label="Refresh"><RefreshCw size={18} /></button>
    </div></header>
    <main className="mx-auto max-w-7xl px-4 py-7 sm:px-6 lg:px-8">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4"><div><h2 className="text-2xl font-bold">Attendance &amp; Leave</h2><p className="text-sm text-slate-500">Mark daily attendance, review trends and manage leave requests.</p></div>
        <label className="text-sm font-medium text-slate-600">Academic session<select value={sessionId || ""} onChange={(event) => changeSession(event.target.value)} className={`${inputClass} mt-1 min-w-44`}>{sessions.map((session) => <option key={session.id} value={session.id}>{session.name}</option>)}</select></label>
      </div>
      {error && <div className="mb-4 flex items-center justify-between rounded-lg bg-red-50 p-3 text-sm text-red-700"><span>{error}</span><button onClick={() => setError("")}><X size={16} /></button></div>}
      {notice && <div className="mb-4 rounded-lg bg-emerald-50 p-3 text-sm text-emerald-700">{notice}</div>}
      <nav className="mb-6 flex gap-1 overflow-x-auto rounded-xl border border-slate-200 bg-white p-1">{([["mark", "Mark attendance"], ["summary", "Summary"], ["leave", "Leave"]] as Array<[Tab, string]>).map(([value, label]) => <button key={value} onClick={() => { setTab(value); if (sessionId && value === "mark") void loadRoster(sessionId); if (sessionId && value === "summary") void loadSummary(sessionId); if (value === "leave") void loadLeaves(); }} className={`whitespace-nowrap rounded-lg px-4 py-2 text-sm font-semibold ${tab === value ? "bg-blue-700 text-white" : "text-slate-600 hover:bg-slate-100"}`}>{label}</button>)}</nav>
      {tab === "mark" && <MarkTab date={date} setDate={setDate} grade={grade} setGrade={setGrade} grades={grades} roster={roster} statusMap={statusMap} setStatusMap={setStatusMap} onLoad={() => sessionId && void loadRoster(sessionId)} onSave={() => void submitAttendance()} saving={saving} />}
      {tab === "summary" && <SummaryTab from={from} to={to} setFrom={setFrom} setTo={setTo} grade={grade} setGrade={setGrade} grades={grades} summary={summary} onLoad={() => sessionId && void loadSummary(sessionId)} />}
      {tab === "leave" && <LeaveTab students={students} leaves={leaves} form={leaveForm} setForm={setLeaveForm} onSubmit={submitLeave} onDecision={decide} saving={saving} />}
    </main>
  </div>;
}

function MarkTab({ date, setDate, grade, setGrade, grades, roster, statusMap, setStatusMap, onLoad, onSave, saving }: { date: string; setDate: (value: string) => void; grade: string; setGrade: (value: string) => void; grades: string[]; roster: AttendanceStudent[]; statusMap: Record<number, string>; setStatusMap: (value: Record<number, string>) => void; onLoad: () => void; onSave: () => void; saving: boolean }) {
  return <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><div className="mb-5 flex flex-wrap items-end justify-between gap-3"><div className="flex gap-3"><label className="text-sm font-medium">Date<input type="date" value={date} onChange={(event) => setDate(event.target.value)} className={`${inputClass} mt-1`} /></label><label className="text-sm font-medium">Grade<select value={grade} onChange={(event) => setGrade(event.target.value)} className={`${inputClass} mt-1`}><option value="">All grades</option>{grades.map((item) => <option key={item}>{item}</option>)}</select></label><button onClick={onLoad} className={`${secondaryButtonClass} self-end`}>Load roster</button></div><button onClick={onSave} disabled={saving || !roster.length} className={`${buttonClass} self-end`}>{saving ? "Saving..." : "Save attendance"}</button></div>
    <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr className="border-b text-slate-500"><th className="px-3 py-2">Student</th><th className="px-3 py-2">Grade</th><th className="px-3 py-2">Status</th><th className="px-3 py-2">Remarks</th></tr></thead><tbody>{roster.map((row) => <tr key={row.student_id} className="border-b last:border-0"><td className="px-3 py-3 font-medium">{row.full_name}</td><td className="px-3 py-3">{row.grade}</td><td className="px-3 py-3"><select value={statusMap[row.student_id] || ""} onChange={(event) => setStatusMap({ ...statusMap, [row.student_id]: event.target.value })} className={inputClass}><option value="">Unmarked</option>{statuses.map((status) => <option key={status}>{status}</option>)}</select></td><td className="px-3 py-3">{row.remarks || "—"}</td></tr>)}</tbody></table>{!roster.length && <p className="py-8 text-center text-sm text-slate-500">No active students found.</p>}</div>
  </section>;
}

function SummaryTab({ from, to, setFrom, setTo, grade, setGrade, grades, summary, onLoad }: { from: string; to: string; setFrom: (value: string) => void; setTo: (value: string) => void; grade: string; setGrade: (value: string) => void; grades: string[]; summary: { days: Array<{ date: string; counts: Record<string, number> }>; students: Array<{ student_id: number; full_name: string; grade: string; present: number; total: number; percentage: number }> } | null; onLoad: () => void }) {
  return <section className="space-y-6"><div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><div className="flex flex-wrap items-end gap-3"><label className="text-sm font-medium">From<input type="date" value={from} onChange={(event) => setFrom(event.target.value)} className={`${inputClass} mt-1`} /></label><label className="text-sm font-medium">To<input type="date" value={to} onChange={(event) => setTo(event.target.value)} className={`${inputClass} mt-1`} /></label><label className="text-sm font-medium">Grade<select value={grade} onChange={(event) => setGrade(event.target.value)} className={`${inputClass} mt-1`}><option value="">All grades</option>{grades.map((item) => <option key={item}>{item}</option>)}</select></label><button onClick={onLoad} className={`${buttonClass} self-end`}>Load summary</button></div></div>
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><h3 className="mb-4 font-semibold">Daily counts</h3><div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr className="border-b text-slate-500"><th className="px-3 py-2">Date</th>{statuses.map((status) => <th key={status} className="px-3 py-2">{status}</th>)}</tr></thead><tbody>{(summary?.days || []).map((day) => <tr key={day.date} className="border-b last:border-0"><td className="px-3 py-3 font-medium">{day.date}</td>{statuses.map((status) => <td key={status} className="px-3 py-3">{day.counts[status] || 0}</td>)}</tr>)}</tbody></table>{!summary?.days.length && <p className="py-6 text-center text-sm text-slate-500">No attendance marked in this range.</p>}</div></div>
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><h3 className="mb-4 font-semibold">Per-student attendance</h3><div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr className="border-b text-slate-500"><th className="px-3 py-2">Student</th><th className="px-3 py-2">Grade</th><th className="px-3 py-2">Present</th><th className="px-3 py-2">Total</th><th className="px-3 py-2">Percentage</th></tr></thead><tbody>{(summary?.students || []).map((student) => <tr key={student.student_id} className="border-b last:border-0"><td className="px-3 py-3 font-medium">{student.full_name}</td><td className="px-3 py-3">{student.grade}</td><td className="px-3 py-3">{student.present}</td><td className="px-3 py-3">{student.total}</td><td className="px-3 py-3">{student.percentage}%</td></tr>)}</tbody></table></div></div>
  </section>;
}

function LeaveTab({ students, leaves, form, setForm, onSubmit, onDecision, saving }: { students: Array<{ id: number; full_name: string; grade: string }>; leaves: LeaveRequest[]; form: { student_id: string; from_date: string; to_date: string; leave_type: "sick" | "casual" | "other"; reason: string }; setForm: (value: { student_id: string; from_date: string; to_date: string; leave_type: "sick" | "casual" | "other"; reason: string }) => void; onSubmit: (event: FormEvent) => void; onDecision: (id: number, decision: "approved" | "rejected") => void; saving: boolean }) {
  return <section className="space-y-6"><form onSubmit={onSubmit} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><h3 className="mb-4 font-semibold">New leave request</h3><div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4"><label className="text-sm font-medium lg:col-span-2">Student<select required value={form.student_id} onChange={(event) => setForm({ ...form, student_id: event.target.value })} className={`${inputClass} mt-1`}><option value="">Select student</option>{students.map((student) => <option key={student.id} value={student.id}>{student.full_name} · {student.grade}</option>)}</select></label><label className="text-sm font-medium">From<input required type="date" value={form.from_date} onChange={(event) => setForm({ ...form, from_date: event.target.value })} className={`${inputClass} mt-1`} /></label><label className="text-sm font-medium">To<input required type="date" value={form.to_date} onChange={(event) => setForm({ ...form, to_date: event.target.value })} className={`${inputClass} mt-1`} /></label><label className="text-sm font-medium">Type<select value={form.leave_type} onChange={(event) => setForm({ ...form, leave_type: event.target.value as "sick" | "casual" | "other" })} className={`${inputClass} mt-1`}><option value="sick">Sick</option><option value="casual">Casual</option><option value="other">Other</option></select></label><label className="text-sm font-medium lg:col-span-3">Reason<input value={form.reason} onChange={(event) => setForm({ ...form, reason: event.target.value })} className={`${inputClass} mt-1`} /></label></div><button disabled={saving} className={`${buttonClass} mt-4`}>Create leave request</button></form>
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><h3 className="mb-4 font-semibold">Leave requests</h3><div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr className="border-b text-slate-500"><th className="px-3 py-2">Student</th><th className="px-3 py-2">Dates</th><th className="px-3 py-2">Type</th><th className="px-3 py-2">Reason</th><th className="px-3 py-2">Status</th><th className="px-3 py-2">Action</th></tr></thead><tbody>{leaves.map((leave) => <tr key={leave.id} className="border-b last:border-0"><td className="px-3 py-3 font-medium">{leave.full_name} · {leave.grade}</td><td className="px-3 py-3">{leave.from_date} → {leave.to_date}</td><td className="px-3 py-3">{leave.leave_type}</td><td className="px-3 py-3">{leave.reason || "—"}</td><td className="px-3 py-3">{leave.status}</td><td className="px-3 py-3">{leave.status === "pending" && <div className="flex gap-2"><button onClick={() => onDecision(leave.id, "approved")} className="rounded-lg bg-emerald-600 p-2 text-white" aria-label="Approve"><Check size={15} /></button><button onClick={() => onDecision(leave.id, "rejected")} className="rounded-lg bg-red-600 p-2 text-white" aria-label="Reject"><X size={15} /></button></div>}</td></tr>)}</tbody></table>{!leaves.length && <p className="py-6 text-center text-sm text-slate-500">No leave requests found.</p>}</div></div>
  </section>;
}
