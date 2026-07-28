const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8001";

function getToken(): string | null {
  return localStorage.getItem("ppis_token");
}

function authHeaders(): Record<string, string> {
  const token = getToken();
  return token
    ? { Authorization: `Bearer ${token}`, "Content-Type": "application/json" }
    : { "Content-Type": "application/json" };
}

async function apiCall(path: string, options: RequestInit = {}) {
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: { ...authHeaders(), ...(options.headers as Record<string, string>) },
  });
  if (res.status === 401) {
    localStorage.removeItem("ppis_token");
    localStorage.removeItem("ppis_user");
    window.location.href = "/login";
    throw new Error("Unauthorized");
  }
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Request failed");
  return data;
}

// Auth
export async function requestOtp(phone: string) {
  return apiCall("/api/auth/request-otp", {
    method: "POST",
    body: JSON.stringify({ phone }),
  });
}

export async function verifyOtp(phone: string, code: string) {
  return apiCall("/api/auth/verify-otp", {
    method: "POST",
    body: JSON.stringify({ phone, code }),
  });
}

export async function setPin(pin: string) {
  return apiCall("/api/auth/set-pin", {
    method: "POST",
    body: JSON.stringify({ pin }),
  });
}

export async function loginPin(phone: string, pin: string) {
  return apiCall("/api/auth/login-pin", {
    method: "POST",
    body: JSON.stringify({ phone, pin }),
  });
}

export async function getMe() {
  return apiCall("/api/auth/me");
}
export async function getPortalMe() { return apiCall("/api/erp/portal/me"); }
export async function getPortalChildren() { return apiCall("/api/erp/portal/children"); }
export async function getChildAttendance(studentId: number, from: string, to: string) {
  return apiCall(`/api/erp/portal/children/${studentId}/attendance?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`);
}
export async function getChildFees(studentId: number) { return apiCall(`/api/erp/portal/children/${studentId}/fees`); }
export async function listChildReportCards(studentId: number) { return apiCall(`/api/erp/portal/children/${studentId}/report-cards`); }
export async function getChildReportCard(studentId: number, examId: number) { return apiCall(`/api/erp/portal/children/${studentId}/report-cards/${examId}`); }
export async function getChildHomework(studentId: number) { return apiCall(`/api/erp/portal/children/${studentId}/homework`); }
export async function getChildTimetable(studentId: number) { return apiCall(`/api/erp/portal/children/${studentId}/timetable`); }
export async function getTeacherGrades() { return apiCall("/api/erp/portal/teacher/grades"); }
export async function getGradeStudents(grade: string) { return apiCall(`/api/erp/portal/teacher/grades/${encodeURIComponent(grade)}/students`); }
export async function getGradeAttendanceSummary(grade: string, from: string, to: string) {
  return apiCall(`/api/erp/portal/teacher/grades/${encodeURIComponent(grade)}/attendance/summary?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`);
}
export async function getGradeHomework(grade: string) { return apiCall(`/api/erp/portal/teacher/grades/${encodeURIComponent(grade)}/homework`); }
export async function getGradeTimetable(grade: string) { return apiCall(`/api/erp/portal/teacher/grades/${encodeURIComponent(grade)}/timetable`); }
export async function listTeachers() { return apiCall("/api/erp/portal/teachers"); }
export async function upsertTeacher(body: { phone: string; name: string; grades: string[] }) {
  return apiCall("/api/erp/portal/teachers", { method: "POST", body: JSON.stringify(body) });
}
export async function unassignTeacherGrade(userId: number, grade: string) {
  return apiCall(`/api/erp/portal/teachers/${userId}/grades/${encodeURIComponent(grade)}`, { method: "DELETE" });
}

export async function updateProfile(name: string) {
  return apiCall("/api/auth/profile", {
    method: "PUT",
    body: JSON.stringify({ name }),
  });
}

// Chat
export async function getConversations() {
  return apiCall("/api/chat/conversations");
}

export async function getMessages(params: { group_id?: number; recipient_id?: number; before_id?: number; limit?: number }) {
  const qs = new URLSearchParams();
  if (params.group_id) qs.set("group_id", String(params.group_id));
  if (params.recipient_id) qs.set("recipient_id", String(params.recipient_id));
  if (params.before_id) qs.set("before_id", String(params.before_id));
  if (params.limit) qs.set("limit", String(params.limit));
  return apiCall(`/api/chat/messages?${qs.toString()}`);
}

export async function sendMessage(body: {
  content: string;
  group_id?: number;
  recipient_id?: number;
  message_type?: string;
  media_url?: string;
  reply_to_id?: number;
}) {
  return apiCall("/api/chat/send", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function markRead(messageIds: number[]) {
  return apiCall("/api/chat/mark-read", {
    method: "POST",
    body: JSON.stringify({ message_ids: messageIds }),
  });
}

export async function pollNewMessages(afterId: number) {
  return apiCall(`/api/chat/new-messages?after_id=${afterId}`);
}

// Groups
export async function getGroups() {
  return apiCall("/api/groups/");
}

export async function getGroup(groupId: number) {
  return apiCall(`/api/groups/${groupId}`);
}

export async function getGroupMembers(groupId: number) {
  return apiCall(`/api/groups/${groupId}/members`);
}

// Admin
export async function getAdminStats() {
  return apiCall("/api/admin/stats");
}

export async function getAllConversations(page = 1, limit = 50, search = "") {
  const qs = new URLSearchParams({ page: String(page), limit: String(limit) });
  if (search) qs.set("search", search);
  return apiCall(`/api/admin/all-conversations?${qs.toString()}`);
}

export async function getUsers(params: { role?: string; search?: string; page?: number }) {
  const qs = new URLSearchParams();
  if (params.role) qs.set("role", params.role);
  if (params.search) qs.set("search", params.search);
  if (params.page) qs.set("page", String(params.page));
  return apiCall(`/api/admin/users?${qs.toString()}`);
}

export async function sendBroadcast(title: string, content: string, targetGrades: string[] = []) {
  return apiCall("/api/admin/broadcast", {
    method: "POST",
    body: JSON.stringify({ title, content, target_grades: targetGrades }),
  });
}

export async function adminReply(body: { recipient_id?: number; group_id?: number; content: string }) {
  return apiCall("/api/admin/reply", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function getBroadcasts() {
  return apiCall("/api/admin/broadcasts");
}

// Student Photos
export async function uploadStudentPhoto(studentName: string, grade: string, photoFile: File) {
  const token = getToken();
  const formData = new FormData();
  formData.append("student_name", studentName);
  formData.append("grade", grade);
  formData.append("photo", photoFile);
  const res = await fetch(`${API_URL}/api/admin/upload-student-photo`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: formData,
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Upload failed");
  return data;
}

export async function getStudentPhotos(grade = "", search = "") {
  const qs = new URLSearchParams();
  if (grade) qs.set("grade", grade);
  if (search) qs.set("search", search);
  return apiCall(`/api/admin/student-photos?${qs.toString()}`);
}

export async function deleteStudentPhoto(photoId: number) {
  return apiCall(`/api/admin/student-photos/${photoId}`, { method: "DELETE" });
}

export function getStudentPhotoUrl(photoId: number): string {
  return `${API_URL}/api/admin/student-photo-image/${photoId}`;
}

// ERP
export async function getErpOverview() {
  return apiCall("/api/erp/overview");
}

export async function getErpStudents(params: {
  search?: string;
  grade?: string;
  status?: string;
  page?: number;
  limit?: number;
} = {}) {
  const qs = new URLSearchParams();
  if (params.search) qs.set("search", params.search);
  if (params.grade) qs.set("grade", params.grade);
  if (params.status) qs.set("status", params.status);
  if (params.page) qs.set("page", String(params.page));
  if (params.limit) qs.set("limit", String(params.limit));
  return apiCall(`/api/erp/students?${qs.toString()}`);
}

export async function getErpStudent(studentId: number) {
  return apiCall(`/api/erp/students/${studentId}`);
}

export async function createErpStudent(student: {
  admission_number?: string;
  full_name: string;
  grade: string;
  date_of_birth?: string;
  gender?: string;
  address?: string;
  transport?: string;
  status?: string;
  guardians?: Array<{
    full_name: string;
    phone?: string;
    relationship?: string;
    is_primary?: boolean;
  }>;
}) {
  return apiCall("/api/erp/students", {
    method: "POST",
    body: JSON.stringify(student),
  });
}

export async function getFeeSummary(sessionId: number) {
  return apiCall(`/api/erp/fees/summary?session_id=${sessionId}`);
}
export async function getFeeSessions() { return apiCall("/api/erp/sessions"); }
export interface ExamSubject {
  id: number;
  exam_id: number;
  subject: string;
  max_marks: number;
  pass_marks: number;
  created_at: string;
}
export interface Exam {
  id: number;
  session_id?: number | null;
  name: string;
  term: string;
  grade: string;
  max_marks: number;
  exam_date: string;
  status: "scheduled" | "ongoing" | "completed" | "published";
  subject_count?: number;
  subjects?: ExamSubject[];
}
export async function listExams(params: { session_id?: number; grade?: string; status?: string } = {}) {
  const qs = new URLSearchParams();
  if (params.session_id) qs.set("session_id", String(params.session_id));
  if (params.grade) qs.set("grade", params.grade);
  if (params.status) qs.set("status", params.status);
  return apiCall(`/api/erp/exams?${qs}`);
}
export async function createExam(body: {
  name: string;
  session_id?: number;
  term?: string;
  grade?: string;
  max_marks?: number;
  exam_date?: string;
  status?: Exam["status"];
}) {
  return apiCall("/api/erp/exams", { method: "POST", body: JSON.stringify(body) });
}
export async function getExam(examId: number) {
  return apiCall(`/api/erp/exams/${examId}`);
}
export async function updateExam(examId: number, body: Partial<{
  name: string;
  session_id: number;
  term: string;
  grade: string;
  max_marks: number;
  exam_date: string;
  status: Exam["status"];
}>) {
  return apiCall(`/api/erp/exams/${examId}`, { method: "PUT", body: JSON.stringify(body) });
}
export async function addExamSubject(examId: number, body: { subject: string; max_marks: number; pass_marks: number }) {
  return apiCall(`/api/erp/exams/${examId}/subjects`, { method: "POST", body: JSON.stringify(body) });
}
export async function deleteExamSubject(examId: number, subjectId: number) {
  return apiCall(`/api/erp/exams/${examId}/subjects/${subjectId}`, { method: "DELETE" });
}
export async function getExamMarks(examId: number, grade = "") {
  const qs = grade ? `?grade=${encodeURIComponent(grade)}` : "";
  return apiCall(`/api/erp/exams/${examId}/marks${qs}`);
}
export async function saveExamMarks(examId: number, entries: Array<{
  student_id: number;
  subject_id: number;
  marks_obtained?: number | null;
  is_absent?: boolean;
  remarks?: string;
}>) {
  return apiCall(`/api/erp/exams/${examId}/marks`, { method: "POST", body: JSON.stringify({ entries }) });
}
export async function getReportCard(examId: number, studentId: number) {
  return apiCall(`/api/erp/exams/${examId}/report-card/${studentId}`);
}
export async function getExamResults(examId: number, grade = "") {
  const qs = grade ? `?grade=${encodeURIComponent(grade)}` : "";
  return apiCall(`/api/erp/exams/${examId}/results${qs}`);
}
export interface AttendanceStudent {
  student_id: number;
  admission_number: string;
  full_name: string;
  grade: string;
  attendance_id?: number;
  status?: string | null;
  remarks?: string | null;
}
export interface AttendanceSummaryStudent {
  student_id: number;
  full_name: string;
  grade: string;
  present: number;
  total: number;
  percentage: number;
}
export interface LeaveRequest {
  id: number;
  student_id: number;
  session_id: number;
  from_date: string;
  to_date: string;
  leave_type: "sick" | "casual" | "other";
  reason: string;
  status: "pending" | "approved" | "rejected";
  decided_at?: string | null;
  created_at: string;
  full_name?: string;
  grade?: string;
}
export async function getAttendanceRoster(params: { grade?: string; date?: string; session_id?: number } = {}) {
  const qs = new URLSearchParams();
  if (params.grade) qs.set("grade", params.grade);
  if (params.date) qs.set("date", params.date);
  if (params.session_id) qs.set("session_id", String(params.session_id));
  return apiCall(`/api/erp/attendance?${qs}`);
}
export async function markAttendance(body: {
  session_id: number;
  date: string;
  entries: Array<{ student_id: number; status: string; remarks?: string }>;
}) {
  return apiCall("/api/erp/attendance/mark", { method: "POST", body: JSON.stringify(body) });
}
export async function getAttendanceSummary(params: { grade?: string; from: string; to: string; session_id?: number }) {
  const qs = new URLSearchParams({ from: params.from, to: params.to });
  if (params.grade) qs.set("grade", params.grade);
  if (params.session_id) qs.set("session_id", String(params.session_id));
  return apiCall(`/api/erp/attendance/summary?${qs}`);
}
export async function getStudentAttendance(studentId: number, params: { from: string; to: string }) {
  const qs = new URLSearchParams({ from: params.from, to: params.to });
  return apiCall(`/api/erp/attendance/student/${studentId}?${qs}`);
}
export async function listLeaveRequests(status = "") {
  const qs = status ? `?status=${encodeURIComponent(status)}` : "";
  return apiCall(`/api/erp/leave${qs}`);
}
export async function createLeaveRequest(body: {
  student_id: number;
  session_id: number;
  from_date: string;
  to_date: string;
  leave_type: "sick" | "casual" | "other";
  reason: string;
}) {
  return apiCall("/api/erp/leave", { method: "POST", body: JSON.stringify(body) });
}
export async function decideLeaveRequest(leaveId: number, decision: "approved" | "rejected") {
  return apiCall(`/api/erp/leave/${leaveId}/decision`, {
    method: "POST",
    body: JSON.stringify({ decision }),
  });
}
export interface AdmissionEnquiry {
  id: number;
  application_number: string;
  applicant_name: string;
  grade_applying: string;
  date_of_birth: string;
  gender: string;
  parent_name: string;
  parent_phone: string;
  parent_email: string;
  address: string;
  previous_school: string;
  source: string;
  status: "enquiry" | "applied" | "shortlisted" | "offered" | "admitted" | "rejected" | "withdrawn";
  notes: string;
  session_id?: number | null;
  student_id?: number | null;
  created_at: string;
  updated_at: string;
  student_full_name?: string | null;
}
export async function listAdmissions(params: { status?: string; grade?: string; search?: string; page?: number; limit?: number } = {}) {
  const qs = new URLSearchParams();
  if (params.status) qs.set("status", params.status);
  if (params.grade) qs.set("grade", params.grade);
  if (params.search) qs.set("search", params.search);
  if (params.page) qs.set("page", String(params.page));
  if (params.limit) qs.set("limit", String(params.limit));
  return apiCall(`/api/erp/admissions?${qs}`);
}
export async function getAdmission(admissionId: number) {
  return apiCall(`/api/erp/admissions/${admissionId}`);
}
export async function createAdmission(body: {
  applicant_name: string;
  grade_applying?: string;
  date_of_birth?: string;
  gender?: string;
  parent_name?: string;
  parent_phone?: string;
  parent_email?: string;
  address?: string;
  previous_school?: string;
  source?: string;
  notes?: string;
  session_id?: number;
}) {
  return apiCall("/api/erp/admissions", { method: "POST", body: JSON.stringify(body) });
}
export async function updateAdmission(admissionId: number, body: Partial<Omit<AdmissionEnquiry, "id" | "application_number" | "status" | "student_id" | "created_at" | "updated_at" | "student_full_name">>) {
  return apiCall(`/api/erp/admissions/${admissionId}`, { method: "PUT", body: JSON.stringify(body) });
}
export async function setAdmissionStatus(admissionId: number, status: AdmissionEnquiry["status"], note = "") {
  return apiCall(`/api/erp/admissions/${admissionId}/status`, { method: "POST", body: JSON.stringify({ status, note }) });
}
export async function convertAdmission(admissionId: number) {
  return apiCall(`/api/erp/admissions/${admissionId}/convert`, { method: "POST" });
}
export async function getAdmissionsSummary() {
  return apiCall("/api/erp/admissions/summary");
}
export interface TimetableSlot {
  id: number;
  session_id?: number | null;
  grade: string;
  day_of_week: number;
  period: number;
  subject: string;
  teacher: string;
  start_time: string;
  end_time: string;
  room: string;
}
export async function getTimetable(params: { session_id?: number; grade?: string } = {}) {
  const qs = new URLSearchParams();
  if (params.session_id) qs.set("session_id", String(params.session_id));
  if (params.grade) qs.set("grade", params.grade);
  return apiCall(`/api/erp/timetable?${qs}`);
}
export async function saveTimetableSlot(body: Omit<TimetableSlot, "id">) {
  return apiCall("/api/erp/timetable/slots", { method: "POST", body: JSON.stringify(body) });
}
export async function saveTimetableBulk(body: { session_id?: number; grade: string; slots: Array<Omit<TimetableSlot, "id" | "session_id" | "grade">> }) {
  return apiCall("/api/erp/timetable/bulk", { method: "POST", body: JSON.stringify(body) });
}
export async function deleteTimetableSlot(slotId: number) {
  return apiCall(`/api/erp/timetable/slots/${slotId}`, { method: "DELETE" });
}
export interface Homework {
  id: number;
  session_id?: number | null;
  grade: string;
  subject: string;
  title: string;
  description: string;
  assigned_date: string;
  due_date: string;
  status: "open" | "closed";
  assigned_by_name?: string;
}
export async function listHomework(params: { session_id?: number; grade?: string; status?: string; from?: string; to?: string } = {}) {
  const qs = new URLSearchParams();
  if (params.session_id) qs.set("session_id", String(params.session_id));
  if (params.grade) qs.set("grade", params.grade);
  if (params.status) qs.set("status", params.status);
  if (params.from) qs.set("from", params.from);
  if (params.to) qs.set("to", params.to);
  return apiCall(`/api/erp/homework?${qs}`);
}
export async function createHomework(body: {
  session_id?: number;
  grade: string;
  subject?: string;
  title: string;
  description?: string;
  assigned_date: string;
  due_date?: string;
}) {
  return apiCall("/api/erp/homework", { method: "POST", body: JSON.stringify(body) });
}
export async function updateHomework(homeworkId: number, body: Partial<{
  session_id: number;
  grade: string;
  subject: string;
  title: string;
  description: string;
  assigned_date: string;
  due_date: string;
  status: Homework["status"];
}>) {
  return apiCall(`/api/erp/homework/${homeworkId}`, { method: "PUT", body: JSON.stringify(body) });
}
export async function deleteHomework(homeworkId: number) {
  return apiCall(`/api/erp/homework/${homeworkId}`, { method: "DELETE" });
}
export interface StaffMember {
  id: number;
  employee_code: string;
  full_name: string;
  role: string;
  department: string;
  phone: string;
  email: string;
  date_of_joining: string;
  monthly_ctc: number;
  status: "active" | "inactive";
}
export async function listStaff(params: { status?: string; department?: string; search?: string; page?: number; limit?: number } = {}) {
  const qs = new URLSearchParams();
  if (params.status) qs.set("status", params.status);
  if (params.department) qs.set("department", params.department);
  if (params.search) qs.set("search", params.search);
  if (params.page) qs.set("page", String(params.page));
  if (params.limit) qs.set("limit", String(params.limit));
  return apiCall(`/api/erp/staff?${qs}`);
}
export async function getStaff(staffId: number) { return apiCall(`/api/erp/staff/${staffId}`); }
export async function createStaff(body: {
  full_name: string; role?: string; department?: string; phone?: string; email?: string;
  date_of_joining?: string; monthly_ctc?: number; status?: StaffMember["status"];
}) {
  return apiCall("/api/erp/staff", { method: "POST", body: JSON.stringify(body) });
}
export async function updateStaff(staffId: number, body: Partial<{
  full_name: string; role: string; department: string; phone: string; email: string;
  date_of_joining: string; monthly_ctc: number; status: StaffMember["status"];
}>) {
  return apiCall(`/api/erp/staff/${staffId}`, { method: "PUT", body: JSON.stringify(body) });
}
export async function getStaffSummary() { return apiCall("/api/erp/staff/summary"); }
export interface PayrollRun {
  id: number;
  month: string;
  status: "draft" | "finalized";
  payslip_count?: number;
  total_net?: number;
  payslips?: Payslip[];
  total_gross?: number;
  total_deductions?: number;
}
export interface Payslip {
  id: number;
  run_id: number;
  staff_id: number;
  full_name: string;
  employee_code: string;
  role?: string;
  department?: string;
  gross: number;
  deductions: number;
  net: number;
  remarks: string;
}
export async function listPayrollRuns() { return apiCall("/api/erp/payroll"); }
export async function createPayrollRun(month: string) {
  return apiCall("/api/erp/payroll", { method: "POST", body: JSON.stringify({ month }) });
}
export async function generatePayroll(runId: number) {
  return apiCall(`/api/erp/payroll/${runId}/generate`, { method: "POST" });
}
export async function getPayrollRun(runId: number) { return apiCall(`/api/erp/payroll/${runId}`); }
export async function updatePayslip(payslipId: number, body: { gross: number; deductions: number; remarks?: string }) {
  return apiCall(`/api/erp/payroll/payslips/${payslipId}`, { method: "PUT", body: JSON.stringify(body) });
}
export async function finalizePayroll(runId: number) {
  return apiCall(`/api/erp/payroll/${runId}/finalize`, { method: "POST" });
}
export async function getFeeHeads() { return apiCall("/api/erp/fee-heads"); }
export async function getFeeStructures(params: { session_id?: number; grade?: string } = {}) {
  const qs = new URLSearchParams();
  if (params.session_id) qs.set("session_id", String(params.session_id));
  if (params.grade) qs.set("grade", params.grade);
  return apiCall(`/api/erp/fee-structures?${qs}`);
}
export interface FeeSession { id: number; name: string; start_date: string; end_date: string; is_current: number }
export interface FeeHead { id: number; code: string; name: string; is_refundable: number; is_active: number }
export interface FeeStructureItem {
  id?: number;
  fee_head_id: number;
  code?: string;
  name?: string;
  amount_paise: number;
  is_optional: number;
}
export interface FeeStructure {
  id: number;
  session_id: number;
  grade: string;
  frequency: "monthly" | "quarterly" | "annual" | "one_time";
  status: "draft" | "published" | "archived";
  items: FeeStructureItem[];
}
export interface StudentFeeSummary {
  plan: Array<{ id: number; session_id: number; structure_id: number; transport_opted: number }>;
  invoices: Array<{
    id: number;
    invoice_number: string;
    due_date: string;
    net_paise: number;
    paid_paise: number;
    status: string;
  }>;
  receipts: Array<{ id: number; receipt_number: string; amount_paise: number; paid_at: string }>;
  dues: number;
}
export interface FeeDue {
  id: number;
  invoice_number: string;
  full_name: string;
  grade: string;
  net_paise: number;
  paid_paise: number;
  due_date: string;
}

export async function createFeeHead(body: { code: string; name: string; is_refundable: boolean }) {
  return apiCall("/api/erp/fee-heads", { method: "POST", body: JSON.stringify(body) });
}
export async function createFeeStructure(body: {
  session_id: number;
  grade: string;
  frequency: FeeStructure["frequency"];
  items: Array<{ fee_head_id: number; amount_paise: number; is_optional: boolean }>;
}) {
  return apiCall("/api/erp/fee-structures", { method: "POST", body: JSON.stringify(body) });
}
export async function updateFeeStructure(structureId: number, body: {
  session_id: number;
  grade: string;
  frequency: FeeStructure["frequency"];
  items: Array<{ fee_head_id: number; amount_paise: number; is_optional: boolean }>;
}) {
  return apiCall(`/api/erp/fee-structures/${structureId}`, { method: "PUT", body: JSON.stringify(body) });
}
export async function publishFeeStructure(structureId: number) {
  return apiCall(`/api/erp/fee-structures/${structureId}/publish`, { method: "POST" });
}
export async function upsertFeePlan(studentId: number, body: {
  session_id: number;
  structure_id: number;
  transport_opted: boolean;
}) {
  return apiCall(`/api/erp/students/${studentId}/fee-plan`, { method: "POST", body: JSON.stringify(body) });
}
export async function getStudentFees(studentId: number, sessionId: number) {
  return apiCall(`/api/erp/students/${studentId}/fees?session_id=${sessionId}`);
}
export async function getFeeDues(sessionId: number, grade = "") {
  const qs = new URLSearchParams({ session_id: String(sessionId) });
  if (grade) qs.set("grade", grade);
  return apiCall(`/api/erp/fees/dues?${qs.toString()}`);
}
export async function listInvoices(params: {
  session_id?: number;
  grade?: string;
  status?: string;
  student_id?: number;
} = {}) {
  const qs = new URLSearchParams();
  if (params.session_id) qs.set("session_id", String(params.session_id));
  if (params.grade) qs.set("grade", params.grade);
  if (params.status) qs.set("status", params.status);
  if (params.student_id) qs.set("student_id", String(params.student_id));
  return apiCall(`/api/erp/invoices?${qs.toString()}`);
}
export async function generateInvoices(body: {
  session_id: number;
  period_code: string;
  grade?: string;
  student_ids?: number[];
  dry_run: boolean;
}, idempotencyKey: string) {
  return apiCall("/api/erp/invoices/generate", { method: "POST", headers: { "Idempotency-Key": idempotencyKey }, body: JSON.stringify(body) });
}
export async function collectPayment(body: {
  student_id: number;
  session_id: number;
  amount_paise: number;
  method: string;
  reference_last4?: string;
  bank_label?: string;
  allocations?: Array<{ invoice_id: number; amount_paise: number }>;
}, idempotencyKey: string) {
  return apiCall("/api/erp/payments", { method: "POST", headers: { "Idempotency-Key": idempotencyKey }, body: JSON.stringify(body) });
}
