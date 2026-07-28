import { FormEvent, useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  BookOpen,
  Bus,
  ChevronRight,
  GraduationCap,
  MapPin,
  Phone,
  Plus,
  Search,
  ShieldCheck,
  UserRound,
  Users,
  X,
} from "lucide-react";
import {
  createErpStudent,
  getErpOverview,
  getErpStudent,
  getErpStudents,
} from "../lib/api";
import { useAuth } from "../lib/auth";

interface Overview {
  active_students: number;
  total_guardians: number;
  transport_students: number;
  grade_count: number;
  students_by_grade: Array<{ grade: string; count: number }>;
}

interface StudentRow {
  id: number;
  admission_number: string;
  full_name: string;
  grade: string;
  status: string;
  transport: string;
  primary_guardian: string;
  guardian_count: number;
  updated_at: string;
}

interface Guardian {
  id: number;
  full_name: string;
  phone: string;
  email: string;
  relationship: string;
  is_primary: boolean;
}

interface StudentDetail extends StudentRow {
  date_of_birth: string;
  gender: string;
  address: string;
  source: string;
  guardians: Guardian[];
}

const emptyForm = {
  admission_number: "",
  full_name: "",
  grade: "",
  date_of_birth: "",
  gender: "",
  address: "",
  transport: "",
  father_name: "",
  father_phone: "",
  mother_name: "",
  mother_phone: "",
};

function formatIst(timestamp: string) {
  if (!timestamp) return "";
  return `${new Intl.DateTimeFormat("en-IN", {
    timeZone: "Asia/Kolkata",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(timestamp))} IST`;
}

export default function ErpDashboard() {
  const navigate = useNavigate();
  const { isAdmin, user } = useAuth();
  const [overview, setOverview] = useState<Overview | null>(null);
  const [students, setStudents] = useState<StudentRow[]>([]);
  const [grades, setGrades] = useState<string[]>([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [grade, setGrade] = useState("");
  const [status, setStatus] = useState("active");
  const [loading, setLoading] = useState(true);
  const [selectedStudent, setSelectedStudent] = useState<StudentDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [showAddStudent, setShowAddStudent] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState("");

  useEffect(() => {
    if (!isAdmin) navigate("/");
  }, [isAdmin, navigate]);

  const loadOverview = useCallback(async () => {
    const data = await getErpOverview();
    setOverview(data);
  }, []);

  const loadStudents = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getErpStudents({ search, grade, status, limit: 100 });
      setStudents(data.students || []);
      setGrades(data.grades || []);
      setTotal(data.total || 0);
    } finally {
      setLoading(false);
    }
  }, [grade, search, status]);

  useEffect(() => {
    loadOverview().catch(console.error);
  }, [loadOverview]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      loadStudents().catch(console.error);
    }, 200);
    return () => window.clearTimeout(timer);
  }, [loadStudents]);

  const openStudent = async (studentId: number) => {
    setDetailLoading(true);
    try {
      setSelectedStudent(await getErpStudent(studentId));
    } finally {
      setDetailLoading(false);
    }
  };

  const submitStudent = async (event: FormEvent) => {
    event.preventDefault();
    setFormError("");
    setSaving(true);
    try {
      await createErpStudent({
        admission_number: form.admission_number,
        full_name: form.full_name,
        grade: form.grade,
        date_of_birth: form.date_of_birth,
        gender: form.gender,
        address: form.address,
        transport: form.transport,
        guardians: [
          {
            full_name: form.father_name,
            phone: form.father_phone,
            relationship: "father",
            is_primary: Boolean(form.father_name || form.father_phone),
          },
          {
            full_name: form.mother_name,
            phone: form.mother_phone,
            relationship: "mother",
            is_primary: !form.father_name && !form.father_phone,
          },
        ],
      });
      setForm(emptyForm);
      setShowAddStudent(false);
      await Promise.all([loadOverview(), loadStudents()]);
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Student could not be saved");
    } finally {
      setSaving(false);
    }
  };

  const statCards = [
    {
      label: "Active students",
      value: overview?.active_students || 0,
      icon: GraduationCap,
      accent: "bg-blue-50 text-blue-700",
    },
    {
      label: "Parent records",
      value: overview?.total_guardians || 0,
      icon: Users,
      accent: "bg-violet-50 text-violet-700",
    },
    {
      label: "Classes",
      value: overview?.grade_count || 0,
      icon: BookOpen,
      accent: "bg-amber-50 text-amber-700",
    },
    {
      label: "Using transport",
      value: overview?.transport_students || 0,
      icon: Bus,
      accent: "bg-emerald-50 text-emerald-700",
    },
  ];

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate("/admin")}
              className="rounded-lg p-2 text-slate-500 transition hover:bg-slate-100 hover:text-slate-900"
              aria-label="Back to admin dashboard"
            >
              <ArrowLeft size={20} />
            </button>
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-blue-700 text-white shadow-sm">
              <ShieldCheck size={24} />
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-blue-700">
                PP International School
              </p>
              <h1 className="text-xl font-bold tracking-tight">School ERP</h1>
            </div>
          </div>
          <div className="hidden text-right sm:block">
            <p className="text-sm font-medium text-slate-800">{user?.name || "Administrator"}</p>
            <p className="text-xs text-slate-500">Student information system</p>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
        <section className="mb-7 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
          <div>
            <p className="mb-1 text-sm font-medium text-blue-700">ERP foundation · Phase 1</p>
            <h2 className="text-2xl font-bold tracking-tight sm:text-3xl">Student records</h2>
            <p className="mt-1 max-w-2xl text-sm text-slate-500">
              One structured directory for students, parents, classes, transport and future attendance or fee modules.
            </p>
          </div>
          <button
            onClick={() => setShowAddStudent(true)}
            className="inline-flex items-center justify-center gap-2 rounded-xl bg-blue-700 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-800"
          >
            <Plus size={18} />
            Add student
          </button>
          <button
            onClick={() => navigate("/erp/fees")}
            className="inline-flex items-center justify-center gap-2 rounded-xl border border-blue-200 bg-blue-50 px-4 py-2.5 text-sm font-semibold text-blue-700"
          >
            Fees &amp; payments
          </button>
          <button
            onClick={() => navigate("/erp/exams")}
            className="inline-flex items-center justify-center gap-2 rounded-xl border border-amber-200 bg-amber-50 px-4 py-2.5 text-sm font-semibold text-amber-700"
          >
            Exams &amp; Report Cards
          </button>
          <button
            onClick={() => navigate("/erp/teachers")}
            className="inline-flex items-center justify-center gap-2 rounded-xl border border-indigo-200 bg-indigo-50 px-4 py-2.5 text-sm font-semibold text-indigo-700"
          >
            Teacher Access
          </button>
          <button
            onClick={() => navigate("/erp/attendance")}
            className="inline-flex items-center justify-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-2.5 text-sm font-semibold text-emerald-700"
          >
            Attendance &amp; Leave
          </button>
          <button
            onClick={() => navigate("/erp/admissions")}
            className="inline-flex items-center justify-center gap-2 rounded-xl border border-violet-200 bg-violet-50 px-4 py-2.5 text-sm font-semibold text-violet-700"
          >
            Admissions
          </button>
          <button
            onClick={() => navigate("/erp/timetable")}
            className="inline-flex items-center justify-center gap-2 rounded-xl border border-sky-200 bg-sky-50 px-4 py-2.5 text-sm font-semibold text-sky-700"
          >
            Timetable &amp; Homework
          </button>
          <button
            onClick={() => navigate("/erp/staff")}
            className="inline-flex items-center justify-center gap-2 rounded-xl border border-rose-200 bg-rose-50 px-4 py-2.5 text-sm font-semibold text-rose-700"
          >
            Staff &amp; Payroll
          </button>
        </section>

        <section className="mb-7 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {statCards.map(({ label, value, icon: Icon, accent }) => (
            <div key={label} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-slate-500">{label}</p>
                  <p className="mt-1 text-3xl font-bold tracking-tight">{value.toLocaleString("en-IN")}</p>
                </div>
                <div className={`rounded-xl p-3 ${accent}`}>
                  <Icon size={22} />
                </div>
              </div>
            </div>
          ))}
        </section>

        <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div className="border-b border-slate-200 p-4 sm:p-5">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <h3 className="font-semibold">Student directory</h3>
                <p className="text-sm text-slate-500">{total.toLocaleString("en-IN")} matching records</p>
              </div>
              <div className="grid gap-2 sm:grid-cols-[minmax(240px,1fr)_180px_150px]">
                <label className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={17} />
                  <input
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                    placeholder="Search student or admission no."
                    className="w-full rounded-xl border border-slate-300 py-2.5 pl-9 pr-3 text-sm outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
                  />
                </label>
                <select
                  value={grade}
                  onChange={(event) => setGrade(event.target.value)}
                  className="rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
                >
                  <option value="">All classes</option>
                  {grades.map((item) => <option key={item} value={item}>{item}</option>)}
                </select>
                <select
                  value={status}
                  onChange={(event) => setStatus(event.target.value)}
                  className="rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
                >
                  <option value="active">Active</option>
                  <option value="inactive">Inactive</option>
                  <option value="alumni">Alumni</option>
                  <option value="withdrawn">Withdrawn</option>
                  <option value="">All statuses</option>
                </select>
              </div>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full min-w-[800px] text-left text-sm">
              <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-5 py-3 font-semibold">Student</th>
                  <th className="px-5 py-3 font-semibold">Class</th>
                  <th className="px-5 py-3 font-semibold">Primary parent</th>
                  <th className="px-5 py-3 font-semibold">Transport</th>
                  <th className="px-5 py-3 font-semibold">Status</th>
                  <th className="px-5 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {loading ? (
                  <tr><td colSpan={6} className="px-5 py-16 text-center text-slate-500">Loading student records…</td></tr>
                ) : students.length === 0 ? (
                  <tr><td colSpan={6} className="px-5 py-16 text-center text-slate-500">No student records match these filters.</td></tr>
                ) : students.map((student) => (
                  <tr
                    key={student.id}
                    onClick={() => openStudent(student.id)}
                    className="cursor-pointer transition hover:bg-blue-50/50"
                  >
                    <td className="px-5 py-4">
                      <div className="flex items-center gap-3">
                        <div className="flex h-9 w-9 items-center justify-center rounded-full bg-blue-100 font-semibold text-blue-700">
                          {student.full_name.charAt(0).toUpperCase()}
                        </div>
                        <div>
                          <p className="font-semibold text-slate-900">{student.full_name}</p>
                          <p className="text-xs text-slate-500">{student.admission_number || "Admission number pending"}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-5 py-4 font-medium text-slate-700">{student.grade}</td>
                    <td className="px-5 py-4 text-slate-600">{student.primary_guardian || `${student.guardian_count} parent record(s)`}</td>
                    <td className="px-5 py-4 text-slate-600">{student.transport || "Not recorded"}</td>
                    <td className="px-5 py-4">
                      <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-semibold capitalize text-emerald-700">
                        {student.status}
                      </span>
                    </td>
                    <td className="px-5 py-4 text-right text-slate-400"><ChevronRight size={18} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </main>

      {(selectedStudent || detailLoading) && (
        <div className="fixed inset-0 z-50 flex justify-end bg-slate-950/35" onClick={() => setSelectedStudent(null)}>
          <aside className="h-full w-full max-w-lg overflow-y-auto bg-white p-6 shadow-2xl" onClick={(event) => event.stopPropagation()}>
            <button onClick={() => setSelectedStudent(null)} className="float-right rounded-lg p-2 text-slate-500 hover:bg-slate-100" aria-label="Close details">
              <X size={20} />
            </button>
            {detailLoading || !selectedStudent ? (
              <p className="py-20 text-center text-slate-500">Loading student details…</p>
            ) : (
              <div>
                <div className="mb-6 flex items-center gap-4 pr-10">
                  <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-blue-100 text-xl font-bold text-blue-700">
                    {selectedStudent.full_name.charAt(0).toUpperCase()}
                  </div>
                  <div>
                    <h3 className="text-xl font-bold">{selectedStudent.full_name}</h3>
                    <p className="text-sm text-slate-500">{selectedStudent.grade} · {selectedStudent.status}</p>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <DetailCard label="Admission number" value={selectedStudent.admission_number || "Not assigned"} />
                  <DetailCard label="Date of birth" value={selectedStudent.date_of_birth || "Not recorded"} />
                  <DetailCard label="Gender" value={selectedStudent.gender || "Not recorded"} />
                  <DetailCard label="Transport" value={selectedStudent.transport || "Not recorded"} />
                </div>

                <div className="mt-6">
                  <h4 className="mb-3 flex items-center gap-2 font-semibold"><Users size={18} className="text-blue-700" /> Parents and guardians</h4>
                  <div className="space-y-3">
                    {selectedStudent.guardians.length === 0 ? (
                      <p className="rounded-xl bg-slate-50 p-4 text-sm text-slate-500">No guardian details recorded.</p>
                    ) : selectedStudent.guardians.map((guardian) => (
                      <div key={guardian.id} className="rounded-xl border border-slate-200 p-4">
                        <div className="flex items-center justify-between">
                          <div>
                            <p className="font-semibold">{guardian.full_name || "Name not recorded"}</p>
                            <p className="text-xs capitalize text-slate-500">{guardian.relationship}{guardian.is_primary ? " · Primary contact" : ""}</p>
                          </div>
                          <UserRound size={19} className="text-slate-400" />
                        </div>
                        {guardian.phone && <p className="mt-3 flex items-center gap-2 text-sm text-slate-600"><Phone size={15} /> {guardian.phone}</p>}
                      </div>
                    ))}
                  </div>
                </div>

                <div className="mt-6">
                  <h4 className="mb-3 flex items-center gap-2 font-semibold"><MapPin size={18} className="text-blue-700" /> Address</h4>
                  <p className="rounded-xl bg-slate-50 p-4 text-sm leading-6 text-slate-600">{selectedStudent.address || "Address not recorded"}</p>
                </div>

                <p className="mt-6 text-xs text-slate-400">Last updated {formatIst(selectedStudent.updated_at)}</p>
              </div>
            )}
          </aside>
        </div>
      )}

      {showAddStudent && (
        <div className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-slate-950/40 p-4">
          <form onSubmit={submitStudent} className="my-6 w-full max-w-2xl rounded-2xl bg-white p-6 shadow-2xl">
            <div className="mb-5 flex items-start justify-between">
              <div>
                <h3 className="text-xl font-bold">Add student record</h3>
                <p className="text-sm text-slate-500">Create the core record and parent contacts.</p>
              </div>
              <button type="button" onClick={() => setShowAddStudent(false)} className="rounded-lg p-2 text-slate-500 hover:bg-slate-100" aria-label="Close form">
                <X size={20} />
              </button>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <FormField label="Student name" required value={form.full_name} onChange={(value) => setForm({ ...form, full_name: value })} />
              <FormField label="Class / section" required value={form.grade} onChange={(value) => setForm({ ...form, grade: value })} />
              <FormField label="Admission number" value={form.admission_number} onChange={(value) => setForm({ ...form, admission_number: value })} />
              <FormField label="Date of birth" type="date" value={form.date_of_birth} onChange={(value) => setForm({ ...form, date_of_birth: value })} />
              <label className="text-sm font-medium text-slate-700">
                Gender
                <select value={form.gender} onChange={(event) => setForm({ ...form, gender: event.target.value })} className="mt-1.5 w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100">
                  <option value="">Select</option>
                  <option value="Female">Female</option>
                  <option value="Male">Male</option>
                  <option value="Other">Other</option>
                </select>
              </label>
              <FormField label="Transport / route" value={form.transport} onChange={(value) => setForm({ ...form, transport: value })} />
            </div>

            <div className="my-5 border-t border-slate-200" />
            <h4 className="mb-3 font-semibold">Parent contacts</h4>
            <div className="grid gap-4 sm:grid-cols-2">
              <FormField label="Father's name" value={form.father_name} onChange={(value) => setForm({ ...form, father_name: value })} />
              <FormField label="Father's mobile" type="tel" value={form.father_phone} onChange={(value) => setForm({ ...form, father_phone: value })} />
              <FormField label="Mother's name" value={form.mother_name} onChange={(value) => setForm({ ...form, mother_name: value })} />
              <FormField label="Mother's mobile" type="tel" value={form.mother_phone} onChange={(value) => setForm({ ...form, mother_phone: value })} />
            </div>
            <label className="mt-4 block text-sm font-medium text-slate-700">
              Address
              <textarea value={form.address} onChange={(event) => setForm({ ...form, address: event.target.value })} rows={3} className="mt-1.5 w-full rounded-xl border border-slate-300 px-3 py-2.5 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100" />
            </label>

            {formError && <p className="mt-4 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">{formError}</p>}
            <div className="mt-6 flex justify-end gap-3">
              <button type="button" onClick={() => setShowAddStudent(false)} className="rounded-xl border border-slate-300 px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50">Cancel</button>
              <button disabled={saving || !form.full_name.trim() || !form.grade.trim()} className="rounded-xl bg-blue-700 px-5 py-2.5 text-sm font-semibold text-white hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-50">
                {saving ? "Saving…" : "Save student"}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}

function DetailCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-slate-50 p-3">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</p>
      <p className="mt-1 text-sm font-semibold text-slate-700">{value}</p>
    </div>
  );
}

function FormField({
  label,
  value,
  onChange,
  type = "text",
  required = false,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: string;
  required?: boolean;
}) {
  return (
    <label className="text-sm font-medium text-slate-700">
      {label}{required ? " *" : ""}
      <input
        type={type}
        required={required}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="mt-1.5 w-full rounded-xl border border-slate-300 px-3 py-2.5 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
      />
    </label>
  );
}
