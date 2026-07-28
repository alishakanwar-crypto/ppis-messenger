import { useCallback, useEffect, useState } from "react";
import { ArrowLeft, BookOpen, CalendarDays, ClipboardList, GraduationCap, IndianRupee, X } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { getChildAttendance, getChildFees, getChildHomework, getChildTimetable, getGradeAttendanceSummary, getGradeHomework, getGradeStudents, getGradeTimetable, getPortalMe, listChildReportCards } from "../lib/api";

const select = "rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-indigo-500";
type Tab = "attendance" | "fees" | "reports" | "homework" | "timetable";
const day = (offset: number) => { const value = new Date(); value.setDate(value.getDate() + offset); return value.toISOString().slice(0, 10); };

export default function Portal() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [me, setMe] = useState<{ role: string; name: string; children: Array<{ id: number; full_name: string; grade: string }>; grades: string[] } | null>(null);
  const [childId, setChildId] = useState<number>();
  const [grade, setGrade] = useState("");
  const [tab, setTab] = useState<Tab>("attendance");
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState("");
  const load = useCallback(async (nextTab = tab, nextChild = childId, nextGrade = grade) => {
    try {
      if (user?.role === "parent" && nextChild) {
        const result = nextTab === "attendance" ? await getChildAttendance(nextChild, day(-30), day(0)) : nextTab === "fees" ? await getChildFees(nextChild) : nextTab === "reports" ? await listChildReportCards(nextChild) : nextTab === "homework" ? await getChildHomework(nextChild) : await getChildTimetable(nextChild);
        setData(result);
      } else if (user?.role === "teacher" && nextGrade) {
        const result = nextTab === "attendance" ? await getGradeAttendanceSummary(nextGrade, day(-30), day(0)) : nextTab === "homework" ? await getGradeHomework(nextGrade) : nextTab === "timetable" ? await getGradeTimetable(nextGrade) : await getGradeStudents(nextGrade);
        setData(result);
      }
    } catch (loadError) { setError(loadError instanceof Error ? loadError.message : "Unable to load portal data"); }
  }, [childId, grade, tab, user?.role]);
  useEffect(() => { getPortalMe().then((result) => { setMe(result); if (result.children?.length) setChildId(result.children[0].id); if (result.grades?.length) setGrade(result.grades[0]); }).catch((loadError: unknown) => setError(loadError instanceof Error ? loadError.message : "Unable to load portal")); }, []);
  useEffect(() => { if (childId || grade) void load(tab, childId, grade); }, [childId, grade, load, tab]);
  const tabs: Array<[Tab, string]> = user?.role === "parent" ? [["attendance", "Attendance"], ["fees", "Fees"], ["reports", "Report cards"], ["homework", "Homework"], ["timetable", "Timetable"]] : [["attendance", "Attendance summary"], ["homework", "Homework"], ["timetable", "Timetable"], ["reports", "Students"]];
  const title = user?.role === "parent" ? "Parent Portal" : "Teacher Portal";
  return <div className="min-h-screen bg-slate-50 text-slate-900"><header className="border-b border-slate-200 bg-white"><div className="mx-auto flex max-w-6xl items-center gap-3 px-4 py-4"><button onClick={() => navigate("/")} className="rounded-lg p-2 hover:bg-slate-100" aria-label="Back"><ArrowLeft size={20} /></button><GraduationCap className="text-indigo-600" /><div><p className="text-xs font-semibold uppercase tracking-widest text-indigo-600">PPIS Campus Care</p><h1 className="text-xl font-bold">{title}</h1></div></div></header><main className="mx-auto max-w-6xl px-4 py-7"><div className="mb-5 flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-2xl font-bold">Welcome, {me?.name || user?.name || "User"}</h2><p className="text-sm text-slate-500">Read-only school information and updates.</p></div>{user?.role === "parent" && <select value={childId || ""} onChange={(event) => setChildId(Number(event.target.value))} className={select}>{(me?.children || []).map((child) => <option key={child.id} value={child.id}>{child.full_name} · {child.grade}</option>)}</select>}{user?.role === "teacher" && <select value={grade} onChange={(event) => setGrade(event.target.value)} className={select}>{(me?.grades || []).map((item) => <option key={item}>{item}</option>)}</select>}</div>{error && <div className="mb-4 flex justify-between rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}<button onClick={() => setError("")}><X size={16} /></button></div>}<nav className="mb-6 flex flex-wrap gap-1 rounded-xl border border-slate-200 bg-white p-1">{tabs.map(([value, label]) => <button key={value} onClick={() => setTab(value)} className={`rounded-lg px-4 py-2 text-sm font-semibold ${tab === value ? "bg-indigo-600 text-white" : "text-slate-600 hover:bg-slate-100"}`}>{label}</button>)}</nav><PortalData tab={tab} data={data} parent={user?.role === "parent"} /></main></div>;
}

function PortalData({ tab, data, parent }: { tab: Tab; data: Record<string, unknown> | null; parent: boolean }) {
  if (!data) return <div className="rounded-xl border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">Select a {parent ? "child" : "grade"} to view information.</div>;
  if (tab === "attendance") {
    const rows = (data.records || data.days || []) as Array<Record<string, unknown>>;
    return <Card icon={<CalendarDays />} title={parent ? `Attendance · ${data.percentage || 0}%` : "Attendance summary"}><Rows rows={rows} fields={parent ? ["date", "status", "remarks"] : ["date", "present", "absent", "late"]} /></Card>;
  }
  if (tab === "fees") {
    const rows = (data.invoices || []) as Array<Record<string, unknown>>;
    return <Card icon={<IndianRupee />} title={`Fees · Outstanding ₹${((Number(data.outstanding_paise) || 0) / 100).toFixed(2)}`}><Rows rows={rows} fields={["invoice_number", "period_code", "status", "net_paise", "outstanding_paise"]} /></Card>;
  }
  if (tab === "reports") {
    const rows = (data.exams || data.students || []) as Array<Record<string, unknown>>;
    return <Card icon={<ClipboardList />} title={parent ? "Published report cards" : "Students"}><Rows rows={rows} fields={parent ? ["name", "term", "exam_date", "status"] : ["full_name", "grade", "admission_number"]} /></Card>;
  }
  if (tab === "homework") return <Card icon={<BookOpen />} title="Homework"><Rows rows={(data.homework || []) as Array<Record<string, unknown>>} fields={["assigned_date", "subject", "title", "due_date", "status"]} /></Card>;
  return <Card icon={<CalendarDays />} title="Timetable"><Rows rows={(data.slots || []) as Array<Record<string, unknown>>} fields={["day_of_week", "period", "subject", "teacher", "start_time", "end_time", "room"]} /></Card>;
}
function Card({ icon, title, children }: { icon: React.ReactNode; title: string; children: React.ReactNode }) { return <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><h3 className="mb-4 flex items-center gap-2 font-semibold text-slate-800">{icon}{title}</h3>{children}</section>; }
function Rows({ rows, fields }: { rows: Array<Record<string, unknown>>; fields: string[] }) { return rows.length ? <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr className="border-b text-slate-500">{fields.map((field) => <th key={field} className="px-2 py-2 capitalize">{field.replace(/_/g, " ")}</th>)}</tr></thead><tbody>{rows.map((row, index) => <tr key={index} className="border-b last:border-0">{fields.map((field) => <td key={field} className="px-2 py-3">{String(row[field] ?? "—")}</td>)}</tr>)}</tbody></table></div> : <p className="text-sm text-slate-500">No records found.</p>; }
