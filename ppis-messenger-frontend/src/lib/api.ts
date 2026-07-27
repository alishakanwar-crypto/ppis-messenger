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
