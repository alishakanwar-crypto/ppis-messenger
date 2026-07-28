import { FormEvent, useCallback, useEffect, useState } from "react";
import { ArrowLeft, CalendarDays, Check, RefreshCw, Trash2, X } from "lucide-react";
import { useNavigate } from "react-router-dom";
import {
  FeeSession,
  Homework,
  TimetableSlot,
  createHomework,
  deleteHomework,
  getErpStudents,
  getFeeSessions,
  getTimetable,
  listHomework,
  saveTimetableBulk,
  updateHomework,
} from "../lib/api";

const inputClass = "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100";
const buttonClass = "rounded-lg bg-sky-600 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-700 disabled:cursor-not-allowed disabled:opacity-50";
const secondaryButtonClass = "rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50";
const errorMessage = (error: unknown, fallback: string) => error instanceof Error ? error.message : fallback;
const days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
type Tab = "timetable" | "homework";
type Cell = { subject: string; teacher: string; start_time: string; end_time: string; room: string; id?: number };
type HomeworkForm = { grade: string; subject: string; title: string; description: string; assigned_date: string; due_date: string; session_id: string };
const emptyHomework: HomeworkForm = { grade: "", subject: "", title: "", description: "", assigned_date: "", due_date: "", session_id: "" };

export default function Timetable() {
  const navigate = useNavigate();
  const [tab, setTab] = useState<Tab>("timetable");
  const [sessions, setSessions] = useState<FeeSession[]>([]);
  const [grades, setGrades] = useState<string[]>([]);
  const [sessionId, setSessionId] = useState<number>();
  const [grade, setGrade] = useState("");
  const [cells, setCells] = useState<Record<string, Cell>>({});
  const [homework, setHomework] = useState<Homework[]>([]);
  const [homeworkStatus, setHomeworkStatus] = useState("");
  const [homeworkGrade, setHomeworkGrade] = useState("");
  const [homeworkForm, setHomeworkForm] = useState(emptyHomework);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const loadSlots = async (id: number, selectedGrade: string) => {
    const data = await getTimetable({ session_id: id, grade: selectedGrade });
    const next: Record<string, Cell> = {};
    (data.slots || []).forEach((slot: TimetableSlot) => {
      next[`${slot.day_of_week}-${slot.period}`] = {
        subject: slot.subject, teacher: slot.teacher, start_time: slot.start_time,
        end_time: slot.end_time, room: slot.room, id: slot.id,
      };
    });
    setCells(next);
  };

  const loadHomework = useCallback(async () => {
    const data = await listHomework({ session_id: sessionId, grade: homeworkGrade, status: homeworkStatus });
    setHomework(data.homework || []);
  }, [homeworkGrade, homeworkStatus, sessionId]);

  useEffect(() => {
    getFeeSessions().then((data) => {
      const rows: FeeSession[] = data.sessions || [];
      setSessions(rows);
      const current = rows.find((row) => row.is_current) || rows[0];
      if (current) {
        setSessionId(current.id);
        setHomeworkForm((previous) => ({ ...previous, session_id: String(current.id) }));
      }
    }).catch((loadError: unknown) => setError(errorMessage(loadError, "Unable to load sessions")));
    getErpStudents({ status: "active", limit: 200 }).then((data) => {
      const rows = data.grades || [];
      setGrades(rows);
      if (rows[0]) {
        setGrade(rows[0]);
        setHomeworkGrade(rows[0]);
        setHomeworkForm((previous) => ({ ...previous, grade: rows[0] }));
      }
    }).catch((loadError: unknown) => setError(errorMessage(loadError, "Unable to load grades")));
  }, []);

  useEffect(() => {
    if (sessionId && grade) loadSlots(sessionId, grade).catch((loadError: unknown) => setError(errorMessage(loadError, "Unable to load timetable")));
  }, [sessionId, grade]);

  useEffect(() => {
    if (sessionId) loadHomework().catch((loadError: unknown) => setError(errorMessage(loadError, "Unable to load homework")));
  }, [loadHomework, sessionId]);

  const setCell = (day: number, period: number, field: keyof Cell, value: string) => {
    const key = `${day}-${period}`;
    const current = cells[key] || { subject: "", teacher: "", start_time: "", end_time: "", room: "" };
    setCells({ ...cells, [key]: { ...current, [field]: value } });
  };

  const saveGrid = async () => {
    if (!sessionId || !grade) return;
    setSaving(true);
    try {
      const slotsToSave = Object.entries(cells).filter(([, cell]) => cell.subject || cell.teacher || cell.start_time || cell.end_time || cell.room).map(([key, cell]) => {
        const [day, period] = key.split("-").map(Number);
        return { day_of_week: day, period, subject: cell.subject, teacher: cell.teacher, start_time: cell.start_time, end_time: cell.end_time, room: cell.room };
      });
      await saveTimetableBulk({ session_id: sessionId, grade, slots: slotsToSave });
      setNotice("Timetable saved.");
      await loadSlots(sessionId, grade);
    } catch (saveError) { setError(errorMessage(saveError, "Timetable could not be saved")); } finally { setSaving(false); }
  };

  const submitHomework = async (event: FormEvent) => {
    event.preventDefault();
    setSaving(true);
    try {
      await createHomework({
        session_id: homeworkForm.session_id ? Number(homeworkForm.session_id) : undefined,
        grade: homeworkForm.grade, subject: homeworkForm.subject, title: homeworkForm.title,
        description: homeworkForm.description, assigned_date: homeworkForm.assigned_date, due_date: homeworkForm.due_date,
      });
      setHomeworkForm({ ...emptyHomework, grade: homeworkForm.grade, session_id: homeworkForm.session_id });
      setNotice("Homework created.");
      await loadHomework();
    } catch (saveError) { setError(errorMessage(saveError, "Homework could not be created")); } finally { setSaving(false); }
  };

  const closeHomework = async (item: Homework) => {
    try { await updateHomework(item.id, { status: "closed" }); await loadHomework(); } catch (closeError) { setError(errorMessage(closeError, "Homework could not be closed")); }
  };
  const removeHomework = async (id: number) => {
    try { await deleteHomework(id); await loadHomework(); } catch (deleteError) { setError(errorMessage(deleteError, "Homework could not be deleted")); }
  };

  return <div className="min-h-screen bg-slate-50 text-slate-900">
    <header className="border-b border-slate-200 bg-white"><div className="mx-auto flex max-w-7xl items-center gap-3 px-4 py-4 sm:px-6 lg:px-8">
      <button onClick={() => navigate("/erp")} className="rounded-lg p-2 hover:bg-slate-100" aria-label="Back to ERP"><ArrowLeft size={20} /></button>
      <CalendarDays className="text-sky-600" /><div><p className="text-xs font-semibold uppercase tracking-widest text-sky-600">School ERP</p><h1 className="text-xl font-bold">Timetable &amp; Homework</h1></div>
      <button onClick={() => { if (sessionId && grade) void loadSlots(sessionId, grade); void loadHomework(); }} className="ml-auto rounded-lg p-2 text-slate-500 hover:bg-slate-100" aria-label="Refresh"><RefreshCw size={18} /></button>
    </div></header>
    <main className="mx-auto max-w-7xl px-4 py-7 sm:px-6 lg:px-8">
      <div className="mb-6"><h2 className="text-2xl font-bold">Timetable &amp; Homework</h2><p className="text-sm text-slate-500">Plan weekly classes and track assignments.</p></div>
      {error && <div className="mb-4 flex items-center justify-between rounded-lg bg-red-50 p-3 text-sm text-red-700"><span>{error}</span><button onClick={() => setError("")}><X size={16} /></button></div>}
      {notice && <div className="mb-4 rounded-lg bg-emerald-50 p-3 text-sm text-emerald-700">{notice}</div>}
      <div className="mb-5 grid gap-3 sm:grid-cols-2"><label className="text-sm font-medium">Academic session<select value={sessionId || ""} onChange={(event) => setSessionId(Number(event.target.value))} className={`${inputClass} mt-1`}>{sessions.map((session) => <option key={session.id} value={session.id}>{session.name}</option>)}</select></label><label className="text-sm font-medium">Grade<select value={grade} onChange={(event) => setGrade(event.target.value)} className={`${inputClass} mt-1`}><option value="">Select grade</option>{grades.map((item) => <option key={item}>{item}</option>)}</select></label></div>
      <nav className="mb-6 flex gap-1 rounded-xl border border-slate-200 bg-white p-1">{([["timetable", "Timetable"], ["homework", "Homework"]] as Array<[Tab, string]>).map(([value, label]) => <button key={value} onClick={() => setTab(value)} className={`rounded-lg px-4 py-2 text-sm font-semibold ${tab === value ? "bg-sky-600 text-white" : "text-slate-600 hover:bg-slate-100"}`}>{label}</button>)}</nav>
      {tab === "timetable" && <TimetableGrid cells={cells} setCell={setCell} saveGrid={saveGrid} saving={saving} />}
      {tab === "homework" && <HomeworkPanel items={homework} form={homeworkForm} setForm={setHomeworkForm} grades={grades} sessions={sessions} status={homeworkStatus} setStatus={setHomeworkStatus} filterGrade={homeworkGrade} setFilterGrade={setHomeworkGrade} onSubmit={submitHomework} onClose={closeHomework} onDelete={removeHomework} saving={saving} />}
    </main>
  </div>;
}

function TimetableGrid({ cells, setCell, saveGrid, saving }: { cells: Record<string, Cell>; setCell: (day: number, period: number, field: keyof Cell, value: string) => void; saveGrid: () => void; saving: boolean }) {
  return <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm"><div className="mb-4 flex items-center justify-between"><h3 className="font-semibold">Weekly timetable</h3><button onClick={saveGrid} disabled={saving} className={buttonClass}><Check className="mr-1 inline" size={16} />{saving ? "Saving..." : "Save timetable"}</button></div><div className="overflow-x-auto"><table className="w-full min-w-[1050px] table-fixed text-left text-xs"><thead><tr className="border-b text-slate-500"><th className="w-14 px-2 py-2">Period</th>{days.map((day) => <th key={day} className="px-2 py-2">{day}</th>)}</tr></thead><tbody>{Array.from({ length: 8 }, (_, index) => index + 1).map((period) => <tr key={period} className="border-b last:border-0"><td className="px-2 py-2 font-semibold">{period}</td>{days.map((_, dayIndex) => { const day = dayIndex + 1; const key = `${day}-${period}`; const cell = cells[key] || { subject: "", teacher: "", start_time: "", end_time: "", room: "" }; return <td key={day} className="p-1 align-top"><div className="space-y-1 rounded-lg bg-slate-50 p-1"><input value={cell.subject} onChange={(event) => setCell(day, period, "subject", event.target.value)} placeholder="Subject" className={inputClass} /><input value={cell.teacher} onChange={(event) => setCell(day, period, "teacher", event.target.value)} placeholder="Teacher" className={inputClass} /><div className="grid grid-cols-2 gap-1"><input value={cell.start_time} onChange={(event) => setCell(day, period, "start_time", event.target.value)} placeholder="Start" className={inputClass} /><input value={cell.end_time} onChange={(event) => setCell(day, period, "end_time", event.target.value)} placeholder="End" className={inputClass} /></div><input value={cell.room} onChange={(event) => setCell(day, period, "room", event.target.value)} placeholder="Room" className={inputClass} /></div></td>; })}</tr>)}</tbody></table></div></section>;
}

function HomeworkPanel({ items, form, setForm, grades, sessions, status, setStatus, filterGrade, setFilterGrade, onSubmit, onClose, onDelete, saving }: { items: Homework[]; form: HomeworkForm; setForm: (value: HomeworkForm) => void; grades: string[]; sessions: FeeSession[]; status: string; setStatus: (value: string) => void; filterGrade: string; setFilterGrade: (value: string) => void; onSubmit: (event: FormEvent) => void; onClose: (item: Homework) => void; onDelete: (id: number) => void; saving: boolean }) {
  const update = (key: keyof HomeworkForm, value: string) => setForm({ ...form, [key]: value });
  return <section className="space-y-6"><form onSubmit={onSubmit} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><h3 className="mb-4 font-semibold">Create homework</h3><div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4"><label className="text-sm font-medium">Grade<select required value={form.grade} onChange={(event) => update("grade", event.target.value)} className={`${inputClass} mt-1`}><option value="">Select grade</option>{grades.map((item) => <option key={item}>{item}</option>)}</select></label><label className="text-sm font-medium">Subject<input value={form.subject} onChange={(event) => update("subject", event.target.value)} className={`${inputClass} mt-1`} /></label><label className="text-sm font-medium">Assigned date<input required type="date" value={form.assigned_date} onChange={(event) => update("assigned_date", event.target.value)} className={`${inputClass} mt-1`} /></label><label className="text-sm font-medium">Due date<input type="date" value={form.due_date} onChange={(event) => update("due_date", event.target.value)} className={`${inputClass} mt-1`} /></label><label className="text-sm font-medium sm:col-span-2">Title<input required value={form.title} onChange={(event) => update("title", event.target.value)} className={`${inputClass} mt-1`} /></label><label className="text-sm font-medium sm:col-span-2">Session<select value={form.session_id} onChange={(event) => update("session_id", event.target.value)} className={`${inputClass} mt-1`}><option value="">Optional</option>{sessions.map((session) => <option key={session.id} value={session.id}>{session.name}</option>)}</select></label><label className="text-sm font-medium sm:col-span-4">Description<textarea rows={2} value={form.description} onChange={(event) => update("description", event.target.value)} className={`${inputClass} mt-1`} /></label></div><button disabled={saving} className={`${buttonClass} mt-4`}>Create homework</button></form>
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><div className="mb-4 flex gap-3"><select value={filterGrade} onChange={(event) => setFilterGrade(event.target.value)} className={`${inputClass} max-w-xs`}><option value="">All grades</option>{grades.map((item) => <option key={item}>{item}</option>)}</select><select value={status} onChange={(event) => setStatus(event.target.value)} className={`${inputClass} max-w-xs`}><option value="">All statuses</option><option value="open">Open</option><option value="closed">Closed</option></select></div><div className="space-y-3">{items.map((item) => <article key={item.id} className="rounded-lg border border-slate-200 p-4"><div className="flex flex-wrap items-start justify-between gap-3"><div><div className="flex items-center gap-2"><h4 className="font-semibold">{item.title}</h4><span className={`rounded-full px-2 py-1 text-xs font-semibold ${item.status === "open" ? "bg-sky-100 text-sky-700" : "bg-slate-100 text-slate-600"}`}>{item.status}</span></div><p className="text-sm text-slate-500">{item.grade} · {item.subject || "General"} · assigned {item.assigned_date}{item.due_date ? ` · due ${item.due_date}` : ""}</p></div><div className="flex gap-2">{item.status === "open" && <button onClick={() => onClose(item)} className={secondaryButtonClass}>Close</button>}<button onClick={() => onDelete(item.id)} className="rounded-lg p-2 text-slate-400 hover:bg-red-50 hover:text-red-600" aria-label="Delete homework"><Trash2 size={16} /></button></div></div>{item.description && <p className="mt-3 text-sm text-slate-700">{item.description}</p>}</article>)}{!items.length && <p className="py-8 text-center text-sm text-slate-500">No homework found.</p>}</div></div>
  </section>;
}
