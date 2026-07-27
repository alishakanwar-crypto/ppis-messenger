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
export async function generateInvoices(body: object, idempotencyKey: string) {
  return apiCall("/api/erp/invoices/generate", { method: "POST", headers: { "Idempotency-Key": idempotencyKey }, body: JSON.stringify(body) });
}
export async function collectPayment(body: object, idempotencyKey: string) {
  return apiCall("/api/erp/payments", { method: "POST", headers: { "Idempotency-Key": idempotencyKey }, body: JSON.stringify(body) });
}
