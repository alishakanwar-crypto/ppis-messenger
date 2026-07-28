import { FormEvent, useCallback, useEffect, useState } from "react";
import { ArrowLeft, ClipboardList, Plus, RefreshCw, Trash2, X } from "lucide-react";
import { useNavigate } from "react-router-dom";
import {
  Exam,
  ExamSubject,
  FeeSession,
  addExamSubject,
  createExam,
  deleteExamSubject,
  getExam,
  getExamMarks,
  getExamResults,
  getErpStudents,
  getFeeSessions,
  getReportCard,
  listExams,
  saveExamMarks,
} from "../lib/api";

const inputClass = "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-amber-500 focus:ring-2 focus:ring-amber-100";
const buttonClass = "rounded-lg bg-amber-600 px-4 py-2 text-sm font-semibold text-white hover:bg-amber-700 disabled:cursor-not-allowed disabled:opacity-50";
const errorMessage = (error: unknown, fallback: string) => error instanceof Error ? error.message : fallback;
const statuses: Exam["status"][] = ["scheduled", "ongoing", "completed", "published"];
type Tab = "exams" | "marks" | "results";
type MarkValue = { marks_obtained: number | null; is_absent: number; remarks: string };
type ExamForm = { name: string; term: string; grade: string; exam_date: string; session_id: string; status: Exam["status"] };
const emptyForm: ExamForm = { name: "", term: "", grade: "", exam_date: "", session_id: "", status: "scheduled" };

export default function Exams() {
  const navigate = useNavigate();
  const [tab, setTab] = useState<Tab>("exams");
  const [sessions, setSessions] = useState<FeeSession[]>([]);
  const [grades, setGrades] = useState<string[]>([]);
  const [exams, setExams] = useState<Exam[]>([]);
  const [selectedExamId, setSelectedExamId] = useState<number>();
  const [selectedExam, setSelectedExam] = useState<Exam | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [subject, setSubject] = useState({ subject: "", max_marks: "100", pass_marks: "33" });
  const [marksData, setMarksData] = useState<{ subjects: ExamSubject[]; students: Array<{ student_id: number; full_name: string; grade: string; marks: Record<string, MarkValue> }> } | null>(null);
  const [markValues, setMarkValues] = useState<Record<string, string>>({});
  const [absentValues, setAbsentValues] = useState<Record<string, boolean>>({});
  const [results, setResults] = useState<Array<{ student_id: number; full_name: string; grade: string; total_obtained: number; total_max: number; percentage: number; rank: number }>>([]);
  const [report, setReport] = useState<Record<string, unknown> | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const loadExams = useCallback(async () => {
    const data = await listExams();
    setExams(data.exams || []);
    if (!selectedExamId && data.exams?.length) setSelectedExamId(data.exams[0].id);
  }, [selectedExamId]);

  useEffect(() => {
    getFeeSessions().then((data) => setSessions(data.sessions || [])).catch((loadError: unknown) => setError(errorMessage(loadError, "Unable to load sessions")));
    getErpStudents({ status: "active", limit: 200 }).then((data) => setGrades(data.grades || [])).catch((loadError: unknown) => setError(errorMessage(loadError, "Unable to load grades")));
    loadExams().catch((loadError: unknown) => setError(errorMessage(loadError, "Unable to load exams")));
  }, [loadExams]);

  const loadExam = async (id: number) => {
    setSelectedExam(await getExam(id));
  };

  useEffect(() => {
    if (selectedExamId) void loadExam(selectedExamId).catch((loadError: unknown) => setError(errorMessage(loadError, "Unable to load exam")));
  }, [selectedExamId]);

  const selectTab = (value: Tab) => {
    setTab(value);
    if (!selectedExamId) return;
    if (value === "marks") void loadMarks(selectedExamId);
    if (value === "results") void loadResults(selectedExamId);
  };

  const loadMarks = async (id: number) => {
    const data = await getExamMarks(id);
    setMarksData(data);
    const nextMarks: Record<string, string> = {};
    const nextAbsent: Record<string, boolean> = {};
    (data.students || []).forEach((student: { student_id: number; marks: Record<string, MarkValue> }) => Object.entries(student.marks || {}).forEach(([subjectId, mark]: [string, MarkValue]) => {
      const key = `${student.student_id}-${subjectId}`;
      if (mark.marks_obtained !== null && mark.marks_obtained !== undefined) nextMarks[key] = String(mark.marks_obtained);
      nextAbsent[key] = Boolean(mark.is_absent);
    }));
    setMarkValues(nextMarks);
    setAbsentValues(nextAbsent);
  };

  const loadResults = async (id: number) => {
    const data = await getExamResults(id);
    setResults(data.results || []);
  };

  const submitExam = async (event: FormEvent) => {
    event.preventDefault();
    setSaving(true);
    try {
      await createExam({ ...form, session_id: form.session_id ? Number(form.session_id) : undefined });
      setForm(emptyForm);
      setNotice("Exam created.");
      await loadExams();
    } catch (saveError) {
      setError(errorMessage(saveError, "Exam could not be created"));
    } finally {
      setSaving(false);
    }
  };

  const addSubject = async (event: FormEvent) => {
    event.preventDefault();
    if (!selectedExamId) return;
    try {
      await addExamSubject(selectedExamId, { subject: subject.subject, max_marks: Number(subject.max_marks), pass_marks: Number(subject.pass_marks) });
      setSubject({ subject: "", max_marks: "100", pass_marks: "33" });
      await loadExam(selectedExamId);
      setNotice("Subject added.");
    } catch (saveError) { setError(errorMessage(saveError, "Subject could not be added")); }
  };

  const removeSubject = async (subjectId: number) => {
    if (!selectedExamId) return;
    try { await deleteExamSubject(selectedExamId, subjectId); await loadExam(selectedExamId); } catch (removeError) { setError(errorMessage(removeError, "Subject could not be removed")); }
  };

  const saveMarks = async () => {
    if (!selectedExamId || !marksData) return;
    setSaving(true);
    try {
      const entries = marksData.students.flatMap((student) => marksData.subjects.map((examSubject) => {
        const key = `${student.student_id}-${examSubject.id}`;
        const value = markValues[key];
        return { student_id: student.student_id, subject_id: examSubject.id, marks_obtained: value === undefined || value === "" ? null : Number(value), is_absent: Boolean(absentValues[key]) };
      }).filter((entry) => entry.marks_obtained !== null || entry.is_absent));
      await saveExamMarks(selectedExamId, entries);
      setNotice("Marks saved.");
      await loadMarks(selectedExamId);
    } catch (saveError) { setError(errorMessage(saveError, "Marks could not be saved")); } finally { setSaving(false); }
  };

  const openReport = async (studentId: number) => {
    if (!selectedExamId) return;
    try { setReport(await getReportCard(selectedExamId, studentId)); } catch (reportError) { setError(errorMessage(reportError, "Report card could not be loaded")); }
  };

  return <div className="min-h-screen bg-slate-50 text-slate-900">
    <header className="border-b border-slate-200 bg-white"><div className="mx-auto flex max-w-7xl items-center gap-3 px-4 py-4 sm:px-6 lg:px-8">
      <button onClick={() => navigate("/erp")} className="rounded-lg p-2 hover:bg-slate-100" aria-label="Back to ERP"><ArrowLeft size={20} /></button>
      <ClipboardList className="text-amber-600" /><div><p className="text-xs font-semibold uppercase tracking-widest text-amber-600">School ERP</p><h1 className="text-xl font-bold">Exams &amp; Report Cards</h1></div>
      <button onClick={() => loadExams()} className="ml-auto rounded-lg p-2 text-slate-500 hover:bg-slate-100" aria-label="Refresh"><RefreshCw size={18} /></button>
    </div></header>
    <main className="mx-auto max-w-7xl px-4 py-7 sm:px-6 lg:px-8">
      <div className="mb-6"><h2 className="text-2xl font-bold">Exams &amp; Report Cards</h2><p className="text-sm text-slate-500">Schedule assessments, enter marks and publish results.</p></div>
      {error && <div className="mb-4 flex items-center justify-between rounded-lg bg-red-50 p-3 text-sm text-red-700"><span>{error}</span><button onClick={() => setError("")}><X size={16} /></button></div>}
      {notice && <div className="mb-4 rounded-lg bg-emerald-50 p-3 text-sm text-emerald-700">{notice}</div>}
      <div className="mb-5 flex items-center gap-3"><select value={selectedExamId || ""} onChange={(event) => setSelectedExamId(Number(event.target.value))} className={`${inputClass} max-w-md`}><option value="">Select exam</option>{exams.map((exam) => <option key={exam.id} value={exam.id}>{exam.name} · {exam.grade || "All grades"}</option>)}</select></div>
      <nav className="mb-6 flex gap-1 rounded-xl border border-slate-200 bg-white p-1">{([["exams", "Exams"], ["marks", "Enter marks"], ["results", "Results"]] as Array<[Tab, string]>).map(([value, label]) => <button key={value} onClick={() => selectTab(value)} className={`rounded-lg px-4 py-2 text-sm font-semibold ${tab === value ? "bg-amber-600 text-white" : "text-slate-600 hover:bg-slate-100"}`}>{label}</button>)}</nav>
      {tab === "exams" && <ExamSetup form={form} setForm={setForm} sessions={sessions} grades={grades} onSubmit={submitExam} saving={saving} exam={selectedExam} subject={subject} setSubject={setSubject} onAdd={addSubject} onRemove={removeSubject} />}
      {tab === "marks" && <MarksTab data={marksData} markValues={markValues} absentValues={absentValues} setMarkValues={setMarkValues} setAbsentValues={setAbsentValues} onSave={saveMarks} saving={saving} />}
      {tab === "results" && <ResultsTab results={results} report={report} onStudent={openReport} />}
    </main>
  </div>;
}

function ExamSetup({ form, setForm, sessions, grades, onSubmit, saving, exam, subject, setSubject, onAdd, onRemove }: { form: ExamForm; setForm: (value: ExamForm) => void; sessions: FeeSession[]; grades: string[]; onSubmit: (event: FormEvent) => void; saving: boolean; exam: Exam | null; subject: { subject: string; max_marks: string; pass_marks: string }; setSubject: (value: { subject: string; max_marks: string; pass_marks: string }) => void; onAdd: (event: FormEvent) => void; onRemove: (id: number) => void }) {
  const update = (key: keyof ExamForm, value: string) => setForm({ ...form, [key]: value });
  return <section className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]"><form onSubmit={onSubmit} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><h3 className="mb-4 font-semibold">Create exam</h3><div className="space-y-3"><label className="text-sm font-medium">Name<input required value={form.name} onChange={(event) => update("name", event.target.value)} className={`${inputClass} mt-1`} /></label><div className="grid gap-3 sm:grid-cols-2"><label className="text-sm font-medium">Term<input value={form.term} onChange={(event) => update("term", event.target.value)} className={`${inputClass} mt-1`} /></label><label className="text-sm font-medium">Grade<select value={form.grade} onChange={(event) => update("grade", event.target.value)} className={`${inputClass} mt-1`}><option value="">All grades</option>{grades.map((item) => <option key={item}>{item}</option>)}</select></label><label className="text-sm font-medium">Date<input type="date" value={form.exam_date} onChange={(event) => update("exam_date", event.target.value)} className={`${inputClass} mt-1`} /></label><label className="text-sm font-medium">Session<select value={form.session_id} onChange={(event) => update("session_id", event.target.value)} className={`${inputClass} mt-1`}><option value="">Optional</option>{sessions.map((session) => <option key={session.id} value={session.id}>{session.name}</option>)}</select></label></div><label className="text-sm font-medium">Status<select value={form.status} onChange={(event) => update("status", event.target.value)} className={`${inputClass} mt-1`}>{statuses.map((value) => <option key={value}>{value}</option>)}</select></label></div><button disabled={saving} className={`${buttonClass} mt-4`}><Plus className="mr-1 inline" size={16} />Create exam</button></form>
    <div className="space-y-5"><form onSubmit={onAdd} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><h3 className="mb-4 font-semibold">Subjects {exam ? `for ${exam.name}` : ""}</h3><div className="grid gap-3 sm:grid-cols-3"><input required placeholder="Subject" value={subject.subject} onChange={(event) => setSubject({ ...subject, subject: event.target.value })} className={inputClass} /><input required type="number" min="1" value={subject.max_marks} onChange={(event) => setSubject({ ...subject, max_marks: event.target.value })} className={inputClass} /><input required type="number" min="0" value={subject.pass_marks} onChange={(event) => setSubject({ ...subject, pass_marks: event.target.value })} className={inputClass} /></div><button disabled={!exam} className={`${buttonClass} mt-3`}>Add subject</button></form><div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><div className="divide-y">{(exam?.subjects || []).map((item) => <div key={item.id} className="flex items-center justify-between py-3 text-sm"><span><b>{item.subject}</b> · max {item.max_marks} · pass {item.pass_marks}</span><button onClick={() => onRemove(item.id)} className="text-slate-400 hover:text-red-600" aria-label="Delete subject"><Trash2 size={16} /></button></div>)}{!exam?.subjects?.length && <p className="text-sm text-slate-500">Select an exam and add subjects.</p>}</div></div></div>
  </section>;
}

function MarksTab({ data, markValues, absentValues, setMarkValues, setAbsentValues, onSave, saving }: { data: { subjects: ExamSubject[]; students: Array<{ student_id: number; full_name: string; grade: string }> } | null; markValues: Record<string, string>; absentValues: Record<string, boolean>; setMarkValues: (value: Record<string, string>) => void; setAbsentValues: (value: Record<string, boolean>) => void; onSave: () => void; saving: boolean }) {
  return <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><div className="mb-4 flex items-center justify-between"><h3 className="font-semibold">Enter marks</h3><button disabled={!data || saving} onClick={onSave} className={buttonClass}>Save marks</button></div><div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr className="border-b text-slate-500"><th className="sticky left-0 bg-white px-3 py-2">Student</th>{(data?.subjects || []).map((subject) => <th key={subject.id} className="min-w-32 px-3 py-2">{subject.subject}<span className="block text-xs font-normal">/{subject.max_marks}</span></th>)}</tr></thead><tbody>{(data?.students || []).map((student) => <tr key={student.student_id} className="border-b last:border-0"><td className="sticky left-0 bg-white px-3 py-3 font-medium">{student.full_name}<span className="ml-2 text-xs text-slate-500">{student.grade}</span></td>{data?.subjects.map((subject) => { const key = `${student.student_id}-${subject.id}`; return <td key={subject.id} className="px-3 py-3"><input disabled={absentValues[key]} type="number" min="0" max={subject.max_marks} value={markValues[key] || ""} onChange={(event) => setMarkValues({ ...markValues, [key]: event.target.value })} className={`${inputClass} w-20`} /><label className="mt-1 block text-xs text-slate-500"><input type="checkbox" checked={Boolean(absentValues[key])} onChange={(event) => setAbsentValues({ ...absentValues, [key]: event.target.checked })} /> Absent</label></td>; })}</tr>)}</tbody></table>{!data?.students.length && <p className="py-8 text-center text-sm text-slate-500">Select an exam to load students.</p>}</div></section>;
}

function ResultsTab({ results, report, onStudent }: { results: Array<{ student_id: number; full_name: string; grade: string; total_obtained: number; total_max: number; percentage: number; rank: number }>; report: Record<string, unknown> | null; onStudent: (id: number) => void }) {
  const subjects = (report?.subjects || []) as Array<{ subject: string; max_marks: number; marks_obtained: number | null; is_absent: number; passed: boolean }>;
  return <section className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,0.8fr)]"><div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><h3 className="mb-4 font-semibold">Ranked results</h3><div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr className="border-b text-slate-500"><th className="px-3 py-2">Rank</th><th className="px-3 py-2">Student</th><th className="px-3 py-2">Total</th><th className="px-3 py-2">%</th></tr></thead><tbody>{results.map((row) => <tr key={row.student_id} onClick={() => onStudent(row.student_id)} className="cursor-pointer border-b hover:bg-amber-50"><td className="px-3 py-3">{row.rank}</td><td className="px-3 py-3 font-medium">{row.full_name} <span className="text-xs text-slate-500">{row.grade}</span></td><td className="px-3 py-3">{row.total_obtained} / {row.total_max}</td><td className="px-3 py-3">{row.percentage}%</td></tr>)}</tbody></table>{!results.length && <p className="py-8 text-center text-sm text-slate-500">Select an exam and open Results.</p>}</div></div><div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">{report ? <><div className="mb-4 flex items-start justify-between"><div><h3 className="font-semibold">{(report.student as { full_name: string }).full_name}</h3><p className="text-sm text-slate-500">{(report.exam as { name: string }).name}</p></div><span className="rounded-full bg-amber-100 px-3 py-1 text-sm font-bold text-amber-700">{String(report.grade_letter)}</span></div><p className="mb-4 text-2xl font-bold">{String(report.percentage)}%</p><div className="divide-y">{subjects.map((subject) => <div key={subject.subject} className="flex justify-between py-2 text-sm"><span>{subject.subject}</span><span>{subject.is_absent ? "Absent" : `${subject.marks_obtained ?? "—"} / ${subject.max_marks}`} · {subject.passed ? "Pass" : "Fail"}</span></div>)}</div></> : <p className="text-sm text-slate-500">Click a student to view the report card.</p>}</div></section>;
}
