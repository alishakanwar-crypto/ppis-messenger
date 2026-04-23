import { useState, useEffect, useRef, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { getMessages, sendMessage, markRead, getGroup } from "../lib/api";
import { useAuth } from "../lib/auth";
import StudentAvatar from "../components/StudentAvatar";

interface Message {
  id: number;
  sender_id: number;
  sender_name: string;
  sender_role: string;
  content: string;
  message_type: string;
  media_url: string | null;
  reply_to_id: number | null;
  created_at: string;
  is_read: boolean;
}

export default function ChatScreen() {
  const { type, id } = useParams<{ type: string; id: string }>();
  const [messages, setMessages] = useState<Message[]>([]);
  const [newMsg, setNewMsg] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [chatName, setChatName] = useState("");
  const [chatGrade, setChatGrade] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const { user } = useAuth();
  const navigate = useNavigate();

  const isGroup = type === "group";
  const targetId = Number(id);

  const loadMessages = useCallback(async () => {
    try {
      const params = isGroup ? { group_id: targetId } : { recipient_id: targetId };
      const data = await getMessages(params);
      setMessages(data.messages || []);

      // Mark messages as read
      const unreadIds = (data.messages || [])
        .filter((m: Message) => m.sender_id !== user?.id && !m.is_read)
        .map((m: Message) => m.id);
      if (unreadIds.length > 0) markRead(unreadIds).catch(() => {});
    } catch (e) {
      console.error("Failed to load messages", e);
    } finally {
      setLoading(false);
    }
  }, [isGroup, targetId, user?.id]);

  const loadGroupInfo = useCallback(async () => {
    if (isGroup) {
      try {
        const data = await getGroup(targetId);
        setChatName(data.group?.name || `Group ${targetId}`);
        setChatGrade(data.group?.grade || "");
      } catch {
        setChatName(`Group ${targetId}`);
      }
    } else {
      setChatName(`Chat`);
    }
  }, [isGroup, targetId]);

  useEffect(() => {
    loadMessages();
    loadGroupInfo();
    const interval = setInterval(loadMessages, 5000);
    return () => clearInterval(interval);
  }, [loadMessages, loadGroupInfo]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async () => {
    if (!newMsg.trim() || sending) return;
    setSending(true);
    try {
      const body = isGroup
        ? { content: newMsg.trim(), group_id: targetId }
        : { content: newMsg.trim(), recipient_id: targetId };
      await sendMessage(body);
      setNewMsg("");
      await loadMessages();
    } catch (e) {
      console.error("Failed to send", e);
    } finally {
      setSending(false);
    }
  };

  const formatTime = (ts: string) => {
    const d = new Date(ts);
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  };

  const formatDateHeader = (ts: string) => {
    const d = new Date(ts);
    const now = new Date();
    if (d.toDateString() === now.toDateString()) return "Today";
    const yesterday = new Date(now);
    yesterday.setDate(yesterday.getDate() - 1);
    if (d.toDateString() === yesterday.toDateString()) return "Yesterday";
    return d.toLocaleDateString([], { weekday: "long", month: "short", day: "numeric" });
  };

  const getRoleBadge = (role: string) => {
    switch (role) {
      case "admin":
        return <span className="text-xs bg-red-100 text-red-700 px-1.5 py-0.5 rounded-full ml-1">Admin</span>;
      case "teacher":
        return <span className="text-xs bg-purple-100 text-purple-700 px-1.5 py-0.5 rounded-full ml-1">Teacher</span>;
      case "bot":
        return <span className="text-xs bg-green-100 text-green-700 px-1.5 py-0.5 rounded-full ml-1">Bot</span>;
      default:
        return null;
    }
  };

  // Group messages by date
  const groupedMessages: { date: string; msgs: Message[] }[] = [];
  let lastDate = "";
  for (const msg of messages) {
    const date = new Date(msg.created_at).toDateString();
    if (date !== lastDate) {
      groupedMessages.push({ date: msg.created_at, msgs: [msg] });
      lastDate = date;
    } else {
      groupedMessages[groupedMessages.length - 1].msgs.push(msg);
    }
  }

  return (
    <div className="min-h-screen bg-gray-100 flex flex-col max-w-lg mx-auto">
      {/* Header */}
      <div className="bg-blue-600 text-white px-4 py-3 flex items-center sticky top-0 z-10">
        <button onClick={() => navigate("/")} className="mr-3 p-1 hover:bg-blue-700 rounded-full transition">
          <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </button>
        {user?.children && user.children.length > 0 && !isGroup ? (
          <StudentAvatar
            name={user.children[0].name}
            photoId={user.children[0].photo_id}
            size="md"
            className="ring-2 ring-blue-400"
          />
        ) : (
          <div className={`w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 ${
            isGroup ? "bg-green-200 text-green-800" : "bg-blue-200 text-blue-800"
          }`}>
            {isGroup ? (
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
            ) : (
              <span className="text-lg font-bold">{(chatName || "?")[0].toUpperCase()}</span>
            )}
          </div>
        )}
        <div className="ml-3">
          <h2 className="font-semibold text-base">{chatName}</h2>
          {chatGrade && <p className="text-xs text-blue-200">{chatGrade}</p>}
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-3 py-2" style={{ backgroundImage: "url(\"data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%239C92AC' fill-opacity='0.05'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E\")" }}>
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : messages.length === 0 ? (
          <div className="text-center py-20 text-gray-400">
            <p>No messages yet. Say hello!</p>
          </div>
        ) : (
          groupedMessages.map((group) => (
            <div key={group.date}>
              <div className="flex justify-center my-3">
                <span className="bg-white text-gray-500 text-xs px-3 py-1 rounded-full shadow-sm">
                  {formatDateHeader(group.date)}
                </span>
              </div>
              {group.msgs.map((msg) => {
                const isOwn = msg.sender_id === user?.id;
                return (
                  <div key={msg.id} className={`flex mb-2 ${isOwn ? "justify-end" : "justify-start"}`}>
                    <div
                      className={`max-w-xs lg:max-w-sm rounded-2xl px-4 py-2 shadow-sm ${
                        isOwn
                          ? "bg-blue-600 text-white rounded-br-sm"
                          : "bg-white text-gray-900 rounded-bl-sm"
                      }`}
                    >
                      {isGroup && !isOwn && (
                        <div className="flex items-center mb-1">
                          <span className={`text-xs font-semibold ${isOwn ? "text-blue-200" : "text-blue-600"}`}>
                            {msg.sender_name}
                          </span>
                          {getRoleBadge(msg.sender_role)}
                        </div>
                      )}
                      {msg.media_url && (
                        <div className="mb-1">
                          <img src={msg.media_url} alt="Media" className="rounded-lg max-w-full" loading="lazy" />
                        </div>
                      )}
                      <p className="text-sm whitespace-pre-wrap break-words">{msg.content}</p>
                      <div className={`flex items-center justify-end mt-1 gap-1 ${isOwn ? "text-blue-200" : "text-gray-400"}`}>
                        <span className="text-xs">{formatTime(msg.created_at)}</span>
                        {isOwn && (
                          <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 24 24">
                            {msg.is_read ? (
                              <path d="M18 7l-1.41-1.41-6.34 6.34 1.41 1.41L18 7zm4.24-1.41L11.66 16.17 7.48 12l-1.41 1.41L11.66 19l12-12-1.42-1.41zM.41 13.41L6 19l1.41-1.41L1.83 12 .41 13.41z" />
                            ) : (
                              <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z" />
                            )}
                          </svg>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="bg-white border-t px-3 py-2 flex items-center gap-2 sticky bottom-0">
        <input
          type="text"
          value={newMsg}
          onChange={(e) => setNewMsg(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSend()}
          placeholder="Type a message..."
          className="flex-1 px-4 py-2.5 bg-gray-100 rounded-full text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <button
          onClick={handleSend}
          disabled={!newMsg.trim() || sending}
          className="w-10 h-10 bg-blue-600 text-white rounded-full flex items-center justify-center hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition flex-shrink-0"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
          </svg>
        </button>
      </div>
    </div>
  );
}
