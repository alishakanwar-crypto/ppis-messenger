import { FormEvent, useCallback, useEffect, useState } from "react";
import { ArrowLeft, BusFront, RefreshCw, Trash2, X } from "lucide-react";
import { useNavigate } from "react-router-dom";
import {
  TransportAssignment,
  TransportRoute,
  TransportStop,
  createTransportAssignment,
  createTransportRoute,
  addTransportStop,
  deleteTransportStop,
  endTransportAssignment,
  getErpStudents,
  getTransportRoute,
  listTransportAssignments,
  listTransportRoutes,
} from "../lib/api";

const inputClass = "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-teal-500 focus:ring-2 focus:ring-teal-100";
const buttonClass = "rounded-lg bg-teal-600 px-4 py-2 text-sm font-semibold text-white hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-50";
const secondaryButtonClass = "rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50";
const errorMessage = (error: unknown, fallback: string) => error instanceof Error ? error.message : fallback;
type Tab = "routes" | "assignments";
type RouteForm = { name: string; vehicle_number: string; driver_name: string; driver_phone: string; capacity: string };
type StopForm = { name: string; stop_order: string; pickup_time: string; drop_time: string; monthly_fee: string };
const emptyRoute: RouteForm = { name: "", vehicle_number: "", driver_name: "", driver_phone: "", capacity: "0" };
const emptyStop: StopForm = { name: "", stop_order: "0", pickup_time: "", drop_time: "", monthly_fee: "0" };

export default function Transport() {
  const navigate = useNavigate();
  const [tab, setTab] = useState<Tab>("routes");
  const [routes, setRoutes] = useState<TransportRoute[]>([]);
  const [routeId, setRouteId] = useState<number>();
  const [route, setRoute] = useState<TransportRoute | null>(null);
  const [routeForm, setRouteForm] = useState(emptyRoute);
  const [stopForm, setStopForm] = useState(emptyStop);
  const [assignments, setAssignments] = useState<TransportAssignment[]>([]);
  const [students, setStudents] = useState<Array<{ id: number; full_name: string; grade: string }>>([]);
  const [assignmentRoute, setAssignmentRoute] = useState("");
  const [assignmentStatus, setAssignmentStatus] = useState("");
  const [search, setSearch] = useState("");
  const [assignmentForm, setAssignmentForm] = useState({ student_id: "", route_id: "", stop_id: "", start_date: "" });
  const [assignmentStops, setAssignmentStops] = useState<TransportStop[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const loadRoutes = useCallback(async () => {
    const data = await listTransportRoutes();
    setRoutes(data.routes || []);
    if (!routeId && data.routes?.length) setRouteId(data.routes[0].id);
  }, [routeId]);
  const loadRoute = useCallback(async (id: number) => setRoute(await getTransportRoute(id)), []);
  const loadAssignments = useCallback(async () => {
    const data = await listTransportAssignments({ route_id: assignmentRoute ? Number(assignmentRoute) : undefined, status: assignmentStatus, search });
    setAssignments(data.assignments || []);
  }, [assignmentRoute, assignmentStatus, search]);

  useEffect(() => { loadRoutes().catch((loadError: unknown) => setError(errorMessage(loadError, "Unable to load routes"))); getErpStudents({ status: "active", limit: 200 }).then((data) => setStudents(data.students || [])).catch((loadError: unknown) => setError(errorMessage(loadError, "Unable to load students"))); }, [loadRoutes]);
  useEffect(() => { if (routeId) loadRoute(routeId).catch((loadError: unknown) => setError(errorMessage(loadError, "Unable to load route"))); }, [loadRoute, routeId]);
  useEffect(() => { loadAssignments().catch((loadError: unknown) => setError(errorMessage(loadError, "Unable to load assignments"))); }, [loadAssignments]);

  const submitRoute = async (event: FormEvent) => {
    event.preventDefault(); setSaving(true);
    try { const result = await createTransportRoute({ name: routeForm.name, vehicle_number: routeForm.vehicle_number, driver_name: routeForm.driver_name, driver_phone: routeForm.driver_phone, capacity: Number(routeForm.capacity) }); setRouteForm(emptyRoute); setRouteId(result.id); setNotice("Route created."); await loadRoutes(); await loadRoute(result.id); } catch (saveError) { setError(errorMessage(saveError, "Route could not be created")); } finally { setSaving(false); }
  };
  const submitStop = async (event: FormEvent) => {
    event.preventDefault(); if (!routeId) return;
    try { await addTransportStop(routeId, { name: stopForm.name, stop_order: Number(stopForm.stop_order), pickup_time: stopForm.pickup_time, drop_time: stopForm.drop_time, monthly_fee: Number(stopForm.monthly_fee) }); setStopForm(emptyStop); setNotice("Stop added."); await loadRoute(routeId); await loadRoutes(); } catch (saveError) { setError(errorMessage(saveError, "Stop could not be added")); }
  };
  const removeStop = async (id: number) => { try { await deleteTransportStop(id); if (routeId) await loadRoute(routeId); } catch (deleteError) { setError(errorMessage(deleteError, "Stop could not be deleted")); } };
  const submitAssignment = async (event: FormEvent) => {
    event.preventDefault(); setSaving(true);
    try { await createTransportAssignment({ student_id: Number(assignmentForm.student_id), route_id: Number(assignmentForm.route_id), stop_id: assignmentForm.stop_id ? Number(assignmentForm.stop_id) : undefined, start_date: assignmentForm.start_date }); setNotice("Student assigned."); setAssignmentForm({ ...assignmentForm, student_id: "" }); await loadAssignments(); } catch (assignError) { setError(errorMessage(assignError, "Student could not be assigned")); } finally { setSaving(false); }
  };
  const end = async (id: number) => { try { await endTransportAssignment(id); setNotice("Assignment ended."); await loadAssignments(); } catch (endError) { setError(errorMessage(endError, "Assignment could not be ended")); } };
  useEffect(() => {
    if (!assignmentForm.route_id) { setAssignmentStops([]); return; }
    getTransportRoute(Number(assignmentForm.route_id)).then((data) => setAssignmentStops(data.stops || [])).catch(() => setAssignmentStops([]));
  }, [assignmentForm.route_id]);

  return <div className="min-h-screen bg-slate-50 text-slate-900"><header className="border-b border-slate-200 bg-white"><div className="mx-auto flex max-w-7xl items-center gap-3 px-4 py-4 sm:px-6 lg:px-8"><button onClick={() => navigate("/erp")} className="rounded-lg p-2 hover:bg-slate-100" aria-label="Back to ERP"><ArrowLeft size={20} /></button><BusFront className="text-teal-600" /><div><p className="text-xs font-semibold uppercase tracking-widest text-teal-600">School ERP</p><h1 className="text-xl font-bold">Transport</h1></div><button onClick={() => { void loadRoutes(); void loadAssignments(); }} className="ml-auto rounded-lg p-2 text-slate-500 hover:bg-slate-100" aria-label="Refresh"><RefreshCw size={18} /></button></div></header>
    <main className="mx-auto max-w-7xl px-4 py-7 sm:px-6 lg:px-8"><div className="mb-6"><h2 className="text-2xl font-bold">Transport management</h2><p className="text-sm text-slate-500">Manage routes, stops and student assignments.</p></div>{error && <div className="mb-4 flex items-center justify-between rounded-lg bg-red-50 p-3 text-sm text-red-700"><span>{error}</span><button onClick={() => setError("")}><X size={16} /></button></div>}{notice && <div className="mb-4 rounded-lg bg-emerald-50 p-3 text-sm text-emerald-700">{notice}</div>}
      <nav className="mb-6 flex gap-1 rounded-xl border border-slate-200 bg-white p-1">{([["routes", "Routes"], ["assignments", "Assignments"]] as Array<[Tab, string]>).map(([value, label]) => <button key={value} onClick={() => setTab(value)} className={`rounded-lg px-4 py-2 text-sm font-semibold ${tab === value ? "bg-teal-600 text-white" : "text-slate-600 hover:bg-slate-100"}`}>{label}</button>)}</nav>
      {tab === "routes" && <RoutesTab routes={routes} route={route} routeForm={routeForm} setRouteForm={setRouteForm} stopForm={stopForm} setStopForm={setStopForm} routeId={routeId} setRouteId={setRouteId} onRoute={submitRoute} onStop={submitStop} onDeleteStop={removeStop} saving={saving} />}
      {tab === "assignments" && <AssignmentsTab assignments={assignments} routes={routes} students={students} form={assignmentForm} setForm={setAssignmentForm} stops={assignmentStops} route={assignmentRoute} setRoute={setAssignmentRoute} status={assignmentStatus} setStatus={setAssignmentStatus} search={search} setSearch={setSearch} onSubmit={submitAssignment} onEnd={end} saving={saving} />}
    </main></div>;
}

function RoutesTab({ routes, route, routeForm, setRouteForm, stopForm, setStopForm, routeId, setRouteId, onRoute, onStop, onDeleteStop, saving }: { routes: TransportRoute[]; route: TransportRoute | null; routeForm: RouteForm; setRouteForm: (value: RouteForm) => void; stopForm: StopForm; setStopForm: (value: StopForm) => void; routeId?: number; setRouteId: (value: number) => void; onRoute: (event: FormEvent) => void; onStop: (event: FormEvent) => void; onDeleteStop: (id: number) => void; saving: boolean }) {
  const updateRoute = (key: keyof RouteForm, value: string) => setRouteForm({ ...routeForm, [key]: value });
  const updateStop = (key: keyof StopForm, value: string) => setStopForm({ ...stopForm, [key]: value });
  return <section className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.5fr)]"><div className="space-y-5"><form onSubmit={onRoute} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><h3 className="mb-4 font-semibold">Create route</h3><div className="space-y-3"><label className="text-sm font-medium">Name<input required value={routeForm.name} onChange={(event) => updateRoute("name", event.target.value)} className={`${inputClass} mt-1`} /></label><div className="grid gap-3 sm:grid-cols-2"><label className="text-sm font-medium">Vehicle number<input value={routeForm.vehicle_number} onChange={(event) => updateRoute("vehicle_number", event.target.value)} className={`${inputClass} mt-1`} /></label><label className="text-sm font-medium">Capacity<input type="number" min="0" value={routeForm.capacity} onChange={(event) => updateRoute("capacity", event.target.value)} className={`${inputClass} mt-1`} /></label><label className="text-sm font-medium">Driver name<input value={routeForm.driver_name} onChange={(event) => updateRoute("driver_name", event.target.value)} className={`${inputClass} mt-1`} /></label><label className="text-sm font-medium">Driver phone<input value={routeForm.driver_phone} onChange={(event) => updateRoute("driver_phone", event.target.value)} className={`${inputClass} mt-1`} /></label></div></div><button disabled={saving} className={`${buttonClass} mt-4`}>Create route</button></form><div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm"><h3 className="mb-3 font-semibold">Routes</h3><div className="space-y-2">{routes.map((item) => <button key={item.id} onClick={() => setRouteId(item.id)} className={`block w-full rounded-lg border p-3 text-left ${routeId === item.id ? "border-teal-400 bg-teal-50" : "border-slate-200"}`}><b>{item.name}</b><span className="block text-xs text-slate-500">{item.vehicle_number || "No vehicle"} · {item.stop_count || 0} stops · {item.assigned_student_count || 0} students</span></button>)}</div></div></div>
    <div className="space-y-5"><form onSubmit={onStop} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><h3 className="mb-4 font-semibold">Add stop {route ? `to ${route.name}` : ""}</h3><div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3"><input required placeholder="Stop name" value={stopForm.name} onChange={(event) => updateStop("name", event.target.value)} className={inputClass} /><input type="number" placeholder="Order" value={stopForm.stop_order} onChange={(event) => updateStop("stop_order", event.target.value)} className={inputClass} /><input type="number" min="0" step="0.01" placeholder="Monthly fee ₹" value={stopForm.monthly_fee} onChange={(event) => updateStop("monthly_fee", event.target.value)} className={inputClass} /><input placeholder="Pickup time" value={stopForm.pickup_time} onChange={(event) => updateStop("pickup_time", event.target.value)} className={inputClass} /><input placeholder="Drop time" value={stopForm.drop_time} onChange={(event) => updateStop("drop_time", event.target.value)} className={inputClass} /></div><button disabled={!routeId} className={`${buttonClass} mt-4`}>Add stop</button></form><div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><h3 className="mb-3 font-semibold">{route?.name || "Select a route"} stops</h3><div className="divide-y">{(route?.stops || []).map((stop: TransportStop) => <div key={stop.id} className="flex items-center justify-between py-3 text-sm"><span><b>{stop.stop_order}. {stop.name}</b><span className="ml-2 text-slate-500">{stop.pickup_time} / {stop.drop_time} · ₹{stop.monthly_fee.toLocaleString("en-IN", { minimumFractionDigits: 2 })}</span></span><button onClick={() => onDeleteStop(stop.id)} className="rounded-lg p-2 text-slate-400 hover:bg-red-50 hover:text-red-600" aria-label="Delete stop"><Trash2 size={16} /></button></div>)}{!route?.stops?.length && <p className="text-sm text-slate-500">No stops configured.</p>}</div>{route && <div className="mt-5"><h4 className="mb-2 font-semibold">Assigned students</h4>{(route.assigned_students || []).map((student) => <p key={student.assignment_id} className="text-sm text-slate-600">{student.full_name} · {student.grade} · {student.stop_name || "No stop"}</p>)}</div>}</div></div>
  </section>;
}

function AssignmentsTab({ assignments, routes, students, form, setForm, stops, route, setRoute, status, setStatus, search, setSearch, onSubmit, onEnd, saving }: { assignments: TransportAssignment[]; routes: TransportRoute[]; students: Array<{ id: number; full_name: string; grade: string }>; form: { student_id: string; route_id: string; stop_id: string; start_date: string }; setForm: (value: { student_id: string; route_id: string; stop_id: string; start_date: string }) => void; stops: TransportStop[]; route: string; setRoute: (value: string) => void; status: string; setStatus: (value: string) => void; search: string; setSearch: (value: string) => void; onSubmit: (event: FormEvent) => void; onEnd: (id: number) => void; saving: boolean }) {
  const update = (key: keyof typeof form, value: string) => setForm({ ...form, [key]: value });
  return <section className="space-y-6"><form onSubmit={onSubmit} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><h3 className="mb-4 font-semibold">Assign student</h3><div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4"><select required value={form.student_id} onChange={(event) => update("student_id", event.target.value)} className={inputClass}><option value="">Select student</option>{students.map((student) => <option key={student.id} value={student.id}>{student.full_name} · {student.grade}</option>)}</select><select required value={form.route_id} onChange={(event) => setForm({ ...form, route_id: event.target.value, stop_id: "" })} className={inputClass}><option value="">Select route</option>{routes.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select><select value={form.stop_id} onChange={(event) => update("stop_id", event.target.value)} className={inputClass}><option value="">Optional stop</option>{stops.map((stop) => <option key={stop.id} value={stop.id}>{stop.name} · ₹{stop.monthly_fee}</option>)}</select><input type="date" value={form.start_date} onChange={(event) => update("start_date", event.target.value)} className={inputClass} /></div><button disabled={saving} className={`${buttonClass} mt-4`}>Assign student</button></form><div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><div className="mb-4 grid gap-3 sm:grid-cols-3"><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search student or route" className={inputClass} /><select value={route} onChange={(event) => setRoute(event.target.value)} className={inputClass}><option value="">All routes</option>{routes.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select><select value={status} onChange={(event) => setStatus(event.target.value)} className={inputClass}><option value="">All statuses</option><option value="active">Active</option><option value="inactive">Inactive</option></select></div><div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr className="border-b text-slate-500"><th className="px-2 py-2">Student</th><th className="px-2 py-2">Route / stop</th><th className="px-2 py-2">Fee</th><th className="px-2 py-2">Status</th><th /></tr></thead><tbody>{assignments.map((item) => <tr key={item.id} className="border-b last:border-0"><td className="px-2 py-3">{item.full_name}<span className="block text-xs text-slate-500">{item.grade}</span></td><td className="px-2 py-3">{item.route_name}<span className="block text-xs text-slate-500">{item.stop_name || "No stop"}</span></td><td className="px-2 py-3">₹{item.monthly_fee.toLocaleString("en-IN", { minimumFractionDigits: 2 })}</td><td className="px-2 py-3">{item.status}</td><td className="px-2 py-3">{item.status === "active" && <button onClick={() => onEnd(item.id)} className={secondaryButtonClass}>End</button>}</td></tr>)}</tbody></table>{!assignments.length && <p className="py-8 text-center text-sm text-slate-500">No assignments found.</p>}</div></div></section>;
}
