import { useState, useEffect, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { getAdminStats, getAllConversations, getUsers, sendBroadcast, getBroadcasts, uploadStudentPhoto, getStudentPhotos, deleteStudentPhoto } from "../lib/api";
import { useAuth } from "../lib/auth";
import StudentAvatar from "../components/StudentAvatar";

interface Stats {
  total_users: number;
  total_messages: number;
  total_groups: number;
  total_broadcasts: number;
  users_by_role: Record<string, number>;
  messages_today: number;
}

interface ConvItem {
  type: string;
  id: number;
  name: string;
  last_message: string;
  last_message_time: string;
  unread_count: number;
  grade?: string;
}

interface UserItem {
  id: number;
  phone: string;
  name: string;
  role: string;
  grade: string;
  created_at: string;
}

interface Broadcast {
  id: number;
  title: string;
  content: string;
  target_grades: string;
  sent_by: number;
  sent_at: string;
}

interface StudentPhoto {
  id: number;
  student_name: string;
  grade: string;
  uploaded_at: string;
}

type Tab = "overview" | "conversations" | "users" | "broadcast" | "photos";

const GRADES = [
  "Nursery 1", "Nursery 2", "Nursery 3",
  "Prep 1", "Prep 2", "Prep 3",
  "Grade 1A", "Grade 1B",
  "Grade 2A", "Grade 2B",
  "Grade 3A", "Grade 3B", "Grade 3C",
  "Grade 4A", "Grade 4B",
  "Grade 5A", "Grade 5B",
  "Grade 6A", "Grade 6B",
  "Grade 7A", "Grade 7B",
  "Grade 8A", "Grade 8B", "Grade 8C",
  "Grade 9A", "Grade 9B", "Grade 9C",
  "Grade 10A", "Grade 10B",
  "Grade 11A", "Grade 11B", "Grade 11C",
  "Grade 12A", "Grade 12B", "Grade 12C",
  "Popsicles",
];

export default function AdminDashboard() {
  const [tab, setTab] = useState<Tab>("overview");
  const [stats, setStats] = useState<Stats | null>(null);
  const [conversations, setConversations] = useState<ConvItem[]>([]);
  const [users, setUsers] = useState<UserItem[]>([]);
  const [broadcasts, setBroadcasts] = useState<Broadcast[]>([]);
  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState("");
  const [loading, setLoading] = useState(true);

  // Broadcast form
  const [bcTitle, setBcTitle] = useState("");
  const [bcContent, setBcContent] = useState("");
  const [bcGrades, setBcGrades] = useState<string[]>([]);
  const [bcSending, setBcSending] = useState(false);
  const [bcResult, setBcResult] = useState("");

  // Photos tab
  const [photos, setPhotos] = useState<StudentPhoto[]>([]);
  const [photoName, setPhotoName] = useState("");
  const [photoGrade, setPhotoGrade] = useState("");
  const [photoFile, setPhotoFile] = useState<File | null>(null);
  const [photoUploading, setPhotoUploading] = useState(false);
  const [photoMsg, setPhotoMsg] = useState("");
  const [photoFilter, setPhotoFilter] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { isAdmin } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (!isAdmin) {
      navigate("/");
    }
  }, [isAdmin, navigate]);

  const loadStats = useCallback(async () => {
    try {
      const data = await getAdminStats();
      setStats(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, []);

  const loadConversations = useCallback(async () => {
    try {
      const data = await getAllConversations(1, 100, search);
      setConversations(data.conversations || []);
    } catch (e) {
      console.error(e);
    }
  }, [search]);

  const loadUsers = useCallback(async () => {
    try {
      const data = await getUsers({ role: roleFilter, search });
      setUsers(data.users || []);
    } catch (e) {
      console.error(e);
    }
  }, [roleFilter, search]);

  const loadBroadcasts = useCallback(async () => {
    try {
      const data = await getBroadcasts();
      setBroadcasts(data.broadcasts || []);
    } catch (e) {
      console.error(e);
    }
  }, []);

  const loadPhotos = useCallback(async () => {
    try {
      const data = await getStudentPhotos(photoFilter || undefined);
      setPhotos(data.photos || []);
    } catch (e) {
      console.error(e);
    }
  }, [photoFilter]);

  useEffect(() => {
    loadStats();
  }, [loadStats]);

  useEffect(() => {
    if (tab === "conversations") loadConversations();
    if (tab === "users") loadUsers();
    if (tab === "broadcast") loadBroadcasts();
    if (tab === "photos") loadPhotos();
  }, [tab, loadConversations, loadUsers, loadBroadcasts, loadPhotos]);

  const handleBroadcast = async () => {
    if (!bcTitle.trim() || !bcContent.trim()) return;
    setBcSending(true);
    setBcResult("");
    try {
      const data = await sendBroadcast(bcTitle.trim(), bcContent.trim(), bcGrades);
      setBcResult(`Broadcast sent to ${data.recipients_count || 0} recipients`);
      setBcTitle("");
      setBcContent("");
      setBcGrades([]);
      loadBroadcasts();
    } catch (e: unknown) {
      setBcResult(e instanceof Error ? e.message : "Failed to send broadcast");
    } finally {
      setBcSending(false);
    }
  };

  const handlePhotoUpload = async () => {
    if (!photoName.trim() || !photoGrade || !photoFile) return;
    setPhotoUploading(true);
    setPhotoMsg("");
    try {
      await uploadStudentPhoto(photoName.trim(), photoGrade, photoFile);
      setPhotoMsg(`Photo uploaded for ${photoName.trim()} (${photoGrade})`);
      setPhotoName("");
      setPhotoGrade("");
      setPhotoFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
      loadPhotos();
    } catch (e: unknown) {
      setPhotoMsg(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setPhotoUploading(false);
    }
  };

  const handleDeletePhoto = async (id: number, name: string) => {
    if (!confirm(`Delete photo of ${name}?`)) return;
    try {
      await deleteStudentPhoto(id);
      loadPhotos();
    } catch (e) {
      console.error(e);
    }
  };

  const toggleGrade = (grade: string) => {
    setBcGrades((prev) =>
      prev.includes(grade) ? prev.filter((g) => g !== grade) : [...prev, grade]
    );
  };

  const formatTime = (ts: string) => {
    if (!ts) return "";
    return new Date(ts).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
  };

  const tabs: { key: Tab; label: string }[] = [
    { key: "overview", label: "Overview" },
    { key: "conversations", label: "Chats" },
    { key: "users", label: "Users" },
    { key: "broadcast", label: "Broadcast" },
    { key: "photos", label: "Photos" },
  ];

  return (
    <div className="min-h-screen bg-gray-50 max-w-4xl mx-auto">
      {/* Header */}
      <div className="bg-blue-600 text-white px-4 py-3 flex items-center justify-between sticky top-0 z-10">
        <div className="flex items-center">
          <button onClick={() => navigate("/")} className="mr-3 p-1 hover:bg-blue-700 rounded-full transition">
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <h1 className="text-lg font-bold">Admin Dashboard</h1>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex bg-white border-b overflow-x-auto sticky top-14 z-10">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`flex-1 min-w-fit py-3 px-4 text-sm font-medium text-center border-b-2 transition whitespace-nowrap ${
              tab === t.key ? "border-blue-600 text-blue-600" : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="p-4">
        {/* Overview */}
        {tab === "overview" && (
          loading ? (
            <div className="flex items-center justify-center py-20">
              <div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
            </div>
          ) : stats ? (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <StatCard label="Total Users" value={stats.total_users} color="blue" />
                <StatCard label="Total Messages" value={stats.total_messages} color="green" />
                <StatCard label="Groups" value={stats.total_groups} color="purple" />
                <StatCard label="Messages Today" value={stats.messages_today} color="orange" />
                <StatCard label="Broadcasts" value={stats.total_broadcasts} color="red" />
                <StatCard label="Parents" value={stats.users_by_role?.parent || 0} color="teal" />
              </div>
              <div className="bg-white rounded-xl p-4 shadow-sm">
                <h3 className="font-semibold text-gray-900 mb-3">Users by Role</h3>
                {Object.entries(stats.users_by_role || {}).map(([role, count]) => (
                  <div key={role} className="flex items-center justify-between py-2 border-b border-gray-100 last:border-0">
                    <span className="text-gray-600 capitalize">{role}</span>
                    <span className="font-medium">{count}</span>
                  </div>
                ))}
              </div>
            </div>
          ) : null
        )}

        {/* Conversations */}
        {tab === "conversations" && (
          <div>
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search conversations..."
              className="w-full px-4 py-2.5 bg-white border border-gray-300 rounded-lg mb-4 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
            <button onClick={loadConversations} className="mb-4 text-sm text-blue-600 hover:underline">
              Refresh
            </button>
            <div className="space-y-2">
              {conversations.map((conv) => (
                <button
                  key={`${conv.type}-${conv.id}`}
                  onClick={() => navigate(conv.type === "group" ? `/chat/group/${conv.id}` : `/chat/dm/${conv.id}`)}
                  className="w-full bg-white rounded-lg p-3 shadow-sm hover:bg-gray-50 transition text-left flex items-center"
                >
                  <div className={`w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 ${
                    conv.type === "group" ? "bg-green-100 text-green-700" : "bg-blue-100 text-blue-700"
                  }`}>
                    <span className="text-sm font-bold">{(conv.name || "?")[0]}</span>
                  </div>
                  <div className="ml-3 flex-1 min-w-0">
                    <div className="flex justify-between items-center">
                      <span className="font-medium text-gray-900 truncate text-sm">{conv.name}</span>
                      <span className="text-xs text-gray-400">{formatTime(conv.last_message_time)}</span>
                    </div>
                    <p className="text-xs text-gray-500 truncate mt-0.5">{conv.last_message}</p>
                  </div>
                  {conv.unread_count > 0 && (
                    <span className="bg-blue-600 text-white text-xs rounded-full w-5 h-5 flex items-center justify-center ml-2">
                      {conv.unread_count}
                    </span>
                  )}
                </button>
              ))}
              {conversations.length === 0 && (
                <p className="text-center text-gray-400 py-10">No conversations found</p>
              )}
            </div>
          </div>
        )}

        {/* Users */}
        {tab === "users" && (
          <div>
            <div className="flex gap-2 mb-4">
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search users..."
                className="flex-1 px-4 py-2.5 bg-white border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500"
              />
              <select
                value={roleFilter}
                onChange={(e) => setRoleFilter(e.target.value)}
                className="px-3 py-2.5 bg-white border border-gray-300 rounded-lg text-sm"
              >
                <option value="">All Roles</option>
                <option value="parent">Parents</option>
                <option value="teacher">Teachers</option>
                <option value="admin">Admins</option>
              </select>
            </div>
            <button onClick={loadUsers} className="mb-4 text-sm text-blue-600 hover:underline">
              Refresh
            </button>
            <div className="space-y-2">
              {users.map((u) => (
                <div key={u.id} className="bg-white rounded-lg p-3 shadow-sm flex items-center">
                  <div className="w-10 h-10 rounded-full bg-gray-100 flex items-center justify-center flex-shrink-0">
                    <span className="text-sm font-bold text-gray-600">{(u.name || u.phone)[0].toUpperCase()}</span>
                  </div>
                  <div className="ml-3 flex-1 min-w-0">
                    <div className="flex items-center">
                      <span className="font-medium text-gray-900 text-sm">{u.name || "Unnamed"}</span>
                      <span className={`ml-2 text-xs px-1.5 py-0.5 rounded-full ${
                        u.role === "admin" ? "bg-red-100 text-red-700" :
                        u.role === "teacher" ? "bg-purple-100 text-purple-700" :
                        "bg-gray-100 text-gray-600"
                      }`}>{u.role}</span>
                    </div>
                    <p className="text-xs text-gray-500 mt-0.5">{u.phone} {u.grade ? `- ${u.grade}` : ""}</p>
                  </div>
                  <button
                    onClick={() => navigate(`/chat/dm/${u.id}`)}
                    className="text-blue-600 text-xs hover:underline ml-2"
                  >
                    Chat
                  </button>
                </div>
              ))}
              {users.length === 0 && (
                <p className="text-center text-gray-400 py-10">No users found</p>
              )}
            </div>
          </div>
        )}

        {/* Photos */}
        {tab === "photos" && (
          <div className="space-y-4">
            {/* Upload Form */}
            <div className="bg-white rounded-xl p-4 shadow-sm">
              <h3 className="font-semibold text-gray-900 mb-3">Upload Student Photo</h3>
              <div className="space-y-3">
                <input
                  type="text"
                  value={photoName}
                  onChange={(e) => setPhotoName(e.target.value)}
                  placeholder="Student name (e.g., Suhaan Ahuja)"
                  className="w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500"
                />
                <select
                  value={photoGrade}
                  onChange={(e) => setPhotoGrade(e.target.value)}
                  className="w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">Select Grade</option>
                  {GRADES.map((g) => (
                    <option key={g} value={g}>{g}</option>
                  ))}
                </select>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  onChange={(e) => setPhotoFile(e.target.files?.[0] || null)}
                  className="w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
                />
                {photoMsg && (
                  <p className={`text-sm ${photoMsg.includes("failed") || photoMsg.includes("Failed") ? "text-red-600" : "text-green-600"}`}>
                    {photoMsg}
                  </p>
                )}
                <button
                  onClick={handlePhotoUpload}
                  disabled={photoUploading || !photoName.trim() || !photoGrade || !photoFile}
                  className="w-full py-2.5 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 transition"
                >
                  {photoUploading ? "Uploading..." : "Upload Photo"}
                </button>
              </div>
            </div>

            {/* Photo Gallery */}
            <div className="bg-white rounded-xl p-4 shadow-sm">
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-semibold text-gray-900">Student Photos ({photos.length})</h3>
                <select
                  value={photoFilter}
                  onChange={(e) => setPhotoFilter(e.target.value)}
                  className="px-3 py-1.5 border border-gray-300 rounded-lg text-sm"
                >
                  <option value="">All Grades</option>
                  {GRADES.map((g) => (
                    <option key={g} value={g}>{g}</option>
                  ))}
                </select>
              </div>
              {photos.length === 0 ? (
                <p className="text-gray-400 text-sm text-center py-8">No photos uploaded yet</p>
              ) : (
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                  {photos.map((p) => (
                    <div key={p.id} className="bg-gray-50 rounded-lg p-3 text-center relative group">
                      <div className="flex justify-center mb-2">
                        <StudentAvatar name={p.student_name} photoId={p.id} size="lg" />
                      </div>
                      <p className="text-sm font-medium text-gray-900 truncate">{p.student_name}</p>
                      <p className="text-xs text-gray-500">{p.grade}</p>
                      <button
                        onClick={() => handleDeletePhoto(p.id, p.student_name)}
                        className="absolute top-1 right-1 w-6 h-6 bg-red-100 text-red-600 rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition text-xs"
                        title="Delete photo"
                      >
                        X
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Broadcast */}
        {tab === "broadcast" && (
          <div className="space-y-4">
            <div className="bg-white rounded-xl p-4 shadow-sm">
              <h3 className="font-semibold text-gray-900 mb-3">Send Broadcast</h3>
              <div className="space-y-3">
                <input
                  type="text"
                  value={bcTitle}
                  onChange={(e) => setBcTitle(e.target.value)}
                  placeholder="Broadcast title"
                  className="w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500"
                />
                <textarea
                  value={bcContent}
                  onChange={(e) => setBcContent(e.target.value)}
                  placeholder="Broadcast message..."
                  rows={4}
                  className="w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 resize-none"
                />
                <div>
                  <p className="text-sm text-gray-600 mb-2">Target grades (leave empty for all):</p>
                  <div className="flex flex-wrap gap-1.5">
                    {GRADES.map((g) => (
                      <button
                        key={g}
                        onClick={() => toggleGrade(g)}
                        className={`px-2 py-1 text-xs rounded-full border transition ${
                          bcGrades.includes(g)
                            ? "bg-blue-600 text-white border-blue-600"
                            : "bg-white text-gray-600 border-gray-300 hover:border-blue-400"
                        }`}
                      >
                        {g}
                      </button>
                    ))}
                  </div>
                </div>
                {bcResult && (
                  <p className={`text-sm ${bcResult.includes("Failed") ? "text-red-600" : "text-green-600"}`}>
                    {bcResult}
                  </p>
                )}
                <button
                  onClick={handleBroadcast}
                  disabled={bcSending || !bcTitle.trim() || !bcContent.trim()}
                  className="w-full py-2.5 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 transition"
                >
                  {bcSending ? "Sending..." : "Send Broadcast"}
                </button>
              </div>
            </div>

            <div className="bg-white rounded-xl p-4 shadow-sm">
              <h3 className="font-semibold text-gray-900 mb-3">Previous Broadcasts</h3>
              {broadcasts.length === 0 ? (
                <p className="text-gray-400 text-sm">No broadcasts yet</p>
              ) : (
                <div className="space-y-3">
                  {broadcasts.map((b) => (
                    <div key={b.id} className="border-b border-gray-100 pb-3 last:border-0 last:pb-0">
                      <div className="flex justify-between items-start">
                        <span className="font-medium text-gray-900 text-sm">{b.title}</span>
                        <span className="text-xs text-gray-400">{formatTime(b.sent_at)}</span>
                      </div>
                      <p className="text-sm text-gray-600 mt-1">{b.content}</p>
                      {b.target_grades && (
                        <p className="text-xs text-blue-600 mt-1">Grades: {b.target_grades}</p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function StatCard({ label, value, color }: { label: string; value: number; color: string }) {
  const colorMap: Record<string, string> = {
    blue: "bg-blue-50 text-blue-700 border-blue-200",
    green: "bg-green-50 text-green-700 border-green-200",
    purple: "bg-purple-50 text-purple-700 border-purple-200",
    orange: "bg-orange-50 text-orange-700 border-orange-200",
    red: "bg-red-50 text-red-700 border-red-200",
    teal: "bg-teal-50 text-teal-700 border-teal-200",
  };
  return (
    <div className={`rounded-xl p-4 border ${colorMap[color] || colorMap.blue}`}>
      <p className="text-2xl font-bold">{value.toLocaleString()}</p>
      <p className="text-sm opacity-80">{label}</p>
    </div>
  );
}
