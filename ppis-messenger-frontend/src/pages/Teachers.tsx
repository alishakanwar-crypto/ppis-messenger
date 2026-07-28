import { FormEvent, useEffect, useState } from "react";
import { ArrowLeft, UserRound, X } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { listTeachers, unassignTeacherGrade, upsertTeacher } from "../lib/api";

const input = "w-full rounded-lg border border-slate-300 px-3 py-2 text-sm";
export default function Teachers() {
  const navigate = useNavigate();
  const [teachers, setTeachers] = useState<Array<{ id: number; name: string; phone: string; grades: string[] }>>([]);
  const [phone, setPhone] = useState(""); const [name, setName] = useState(""); const [grades, setGrades] = useState("");
  const [error, setError] = useState("");
  const load = async () => { const data = await listTeachers(); setTeachers(data.teachers || []); };
  useEffect(() => { load().catch((loadError: unknown) => setError(loadError instanceof Error ? loadError.message : "Unable to load teachers")); }, []);
  const submit = async (event: FormEvent) => { event.preventDefault(); try { await upsertTeacher({ phone, name, grades: grades.split(",").map((item) => item.trim()).filter(Boolean) }); setPhone(""); setName(""); setGrades(""); await load(); } catch (saveError) { setError(saveError instanceof Error ? saveError.message : "Unable to save teacher"); } };
  const remove = async (id: number, grade: string) => { try { await unassignTeacherGrade(id, grade); await load(); } catch (removeError) { setError(removeError instanceof Error ? removeError.message : "Unable to unassign grade"); } };
  return <div className="min-h-screen bg-slate-50"><header className="border-b bg-white"><div className="mx-auto flex max-w-5xl items-center gap-3 px-4 py-4"><button onClick={() => navigate("/erp")} className="rounded-lg p-2 hover:bg-slate-100"><ArrowLeft size={20} /></button><UserRound className="text-indigo-600" /><h1 className="text-xl font-bold">Teacher Access</h1></div></header><main className="mx-auto max-w-5xl px-4 py-7">{error && <div className="mb-4 flex justify-between rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}<button onClick={() => setError("")}><X size={16} /></button></div>}<div className="grid gap-6 md:grid-cols-2"><form onSubmit={submit} className="rounded-xl border bg-white p-5 shadow-sm"><h2 className="mb-4 font-semibold">Add or update teacher</h2><div className="space-y-3"><input required placeholder="Phone" value={phone} onChange={(event) => setPhone(event.target.value)} className={input} /><input placeholder="Name" value={name} onChange={(event) => setName(event.target.value)} className={input} /><input placeholder="Grades, comma separated" value={grades} onChange={(event) => setGrades(event.target.value)} className={input} /></div><button className="mt-4 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white">Save teacher</button></form><section className="rounded-xl border bg-white p-5 shadow-sm"><h2 className="mb-4 font-semibold">Teachers</h2>{teachers.map((teacher) => <div key={teacher.id} className="border-b py-3 last:border-0"><b>{teacher.name || teacher.phone}</b><span className="ml-2 text-sm text-slate-500">{teacher.phone}</span><div className="mt-2 flex flex-wrap gap-2">{teacher.grades.map((grade) => <button key={grade} onClick={() => remove(teacher.id, grade)} className="rounded-full bg-indigo-50 px-2 py-1 text-xs text-indigo-700">{grade} ×</button>)}</div></div>)}</section></div></main></div>;
}
