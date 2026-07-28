import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { getConversations, getGroups } from "../lib/api";
import { useAuth } from "../lib/auth";
import StudentAvatar from "../components/StudentAvatar";

interface Conversation {
  type: string;
  id: number;
  name: string;
  last_message: string;
  last_message_time: string;
  unread_count: number;
  grade?: string;
}

interface Group {
  id: number;
  name: string;
  grade: string;
  member_count: number;
}

export default function ChatList() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [groups, setGroups] = useState<Group[]>([]);
  const [tab, setTab] = useState<"chats" | "groups">("chats");
  const [loading, setLoading] = useState(true);
  const { user, logout, isAdmin } = useAuth();
  const navigate = useNavigate();

  const loadData = useCallback(async () => {
    try {
      const [convData, groupData] = await Promise.all([
        getConversations(),
        getGroups(),
      ]);
      setConversations(convData.conversations || []);
      setGroups(groupData.groups || []);
    } catch (e) {
      console.error("Failed to load data", e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 10000);
    return () => clearInterval(interval);
  }, [loadData]);

  const formatTime = (ts: string) => {
    if (!ts) return "";
    const d = new Date(ts);
    const now = new Date();
    const isToday = d.toDateString() === now.toDateString();
    if (isToday) return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    return d.toLocaleDateString([], { month: "short", day: "numeric" });
  };

  const totalUnread = conversations.reduce((s, c) => s + (c.unread_count || 0), 0);

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col max-w-lg mx-auto">
      {/* Header */}
      <div className="bg-blue-600 text-white px-4 py-3 flex items-center justify-between sticky top-0 z-10">
        <div className="flex items-center">
          {user?.children && user.children.length > 0 ? (
            <div className="mr-3">
              {user.children.length === 1 ? (
                <StudentAvatar
                  name={user.children[0].name}
                  photoId={user.children[0].photo_id}
                  size="md"
                  className="ring-2 ring-blue-400"
                />
              ) : (
                <div className="flex -space-x-2">
                  {user.children.slice(0, 2).map((child, i) => (
                    <StudentAvatar
                      key={i}
                      name={child.name}
                      photoId={child.photo_id}
                      size="sm"
                      className="ring-2 ring-blue-500"
                    />
                  ))}
                </div>
              )}
            </div>
          ) : null}
          <div>
            <h1 className="text-lg font-bold">PPIS Campus Care</h1>
            <p className="text-xs text-blue-200">
              {user?.children && user.children.length > 0
                ? user.children.map(c => c.name).join(", ")
                : user?.name || user?.phone}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {isAdmin && (
            <button
              onClick={() => navigate("/admin")}
              className="p-2 rounded-full hover:bg-blue-700 transition"
              title="Admin Dashboard"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
            </button>
          )}
          <button
            onClick={() => navigate("/profile")}
            className="p-2 rounded-full hover:bg-blue-700 transition"
            title="Profile"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            </svg>
          </button>
          <button
            onClick={logout}
            className="p-2 rounded-full hover:bg-blue-700 transition"
            title="Logout"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
            </svg>
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex bg-white border-b sticky top-14 z-10">
        <button
          onClick={() => setTab("chats")}
          className={`flex-1 py-3 text-sm font-medium text-center border-b-2 transition ${
            tab === "chats"
              ? "border-blue-600 text-blue-600"
              : "border-transparent text-gray-500 hover:text-gray-700"
          }`}
        >
          Chats
          {totalUnread > 0 && (
            <span className="ml-1.5 bg-blue-600 text-white text-xs rounded-full px-1.5 py-0.5">
              {totalUnread}
            </span>
          )}
        </button>
        <button
          onClick={() => setTab("groups")}
          className={`flex-1 py-3 text-sm font-medium text-center border-b-2 transition ${
            tab === "groups"
              ? "border-blue-600 text-blue-600"
              : "border-transparent text-gray-500 hover:text-gray-700"
          }`}
        >
          Groups ({groups.length})
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : tab === "chats" ? (
          conversations.length === 0 ? (
            <div className="text-center py-20 text-gray-400">
              <svg className="w-16 h-16 mx-auto mb-4 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
              </svg>
              <p className="font-medium">No conversations yet</p>
              <p className="text-sm mt-1">Start chatting by joining a group</p>
            </div>
          ) : (
            conversations.map((conv) => (
              <button
                key={`${conv.type}-${conv.id}`}
                onClick={() =>
                  navigate(
                    conv.type === "group"
                      ? `/chat/group/${conv.id}`
                      : `/chat/dm/${conv.id}`
                  )
                }
                className="w-full flex items-center px-4 py-3 hover:bg-gray-100 transition border-b border-gray-100"
              >
                <div className={`w-12 h-12 rounded-full flex items-center justify-center flex-shrink-0 ${
                  conv.type === "group" ? "bg-green-100 text-green-700" : "bg-blue-100 text-blue-700"
                }`}>
                  {conv.type === "group" ? (
                    <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                    </svg>
                  ) : (
                    <span className="text-lg font-bold">{(conv.name || "?")[0].toUpperCase()}</span>
                  )}
                </div>
                <div className="ml-3 flex-1 min-w-0 text-left">
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-gray-900 truncate">{conv.name}</span>
                    <span className="text-xs text-gray-400 ml-2 flex-shrink-0">{formatTime(conv.last_message_time)}</span>
                  </div>
                  <div className="flex items-center justify-between mt-0.5">
                    <p className="text-sm text-gray-500 truncate">{conv.last_message || "No messages yet"}</p>
                    {conv.unread_count > 0 && (
                      <span className="bg-blue-600 text-white text-xs rounded-full w-5 h-5 flex items-center justify-center ml-2 flex-shrink-0">
                        {conv.unread_count}
                      </span>
                    )}
                  </div>
                </div>
              </button>
            ))
          )
        ) : groups.length === 0 ? (
          <div className="text-center py-20 text-gray-400">
            <p className="font-medium">No groups yet</p>
          </div>
        ) : (
          groups.map((group) => (
            <button
              key={group.id}
              onClick={() => navigate(`/chat/group/${group.id}`)}
              className="w-full flex items-center px-4 py-3 hover:bg-gray-100 transition border-b border-gray-100"
            >
              <div className="w-12 h-12 rounded-full bg-green-100 text-green-700 flex items-center justify-center flex-shrink-0">
                <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                </svg>
              </div>
              <div className="ml-3 flex-1 min-w-0 text-left">
                <span className="font-medium text-gray-900">{group.name}</span>
                <p className="text-sm text-gray-500">{group.grade} - {group.member_count} members</p>
              </div>
            </button>
          ))
        )}
      </div>
    </div>
  );
}
