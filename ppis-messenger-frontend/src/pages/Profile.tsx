import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { updateProfile, setPin } from "../lib/api";
import { useAuth } from "../lib/auth";
import StudentAvatar from "../components/StudentAvatar";

export default function Profile() {
  const { user, refreshUser, logout } = useAuth();
  const navigate = useNavigate();
  const [name, setName] = useState(user?.name || "");
  const [pin, setPinVal] = useState("");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  const handleSaveName = async () => {
    if (!name.trim()) return;
    setSaving(true);
    setMessage("");
    try {
      await updateProfile(name.trim());
      await refreshUser();
      setMessage("Name updated successfully");
    } catch (e: unknown) {
      setMessage(e instanceof Error ? e.message : "Failed to update name");
    } finally {
      setSaving(false);
    }
  };

  const handleSetPin = async () => {
    if (pin.length !== 4) return;
    setSaving(true);
    setMessage("");
    try {
      await setPin(pin);
      setPinVal("");
      setMessage("PIN set successfully. You can now use it for quick login.");
    } catch (e: unknown) {
      setMessage(e instanceof Error ? e.message : "Failed to set PIN");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 max-w-lg mx-auto">
      {/* Header */}
      <div className="bg-blue-600 text-white px-4 py-3 flex items-center sticky top-0 z-10">
        <button onClick={() => navigate("/")} className="mr-3 p-1 hover:bg-blue-700 rounded-full transition">
          <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </button>
        <h1 className="text-lg font-bold">Profile</h1>
      </div>

      <div className="p-4 space-y-4">
        {/* User Info */}
        <div className="bg-white rounded-xl p-6 shadow-sm text-center">
          {user?.children && user.children.length > 0 ? (
            <div className="flex justify-center mb-3">
              {user.children.length === 1 ? (
                <StudentAvatar
                  name={user.children[0].name}
                  photoId={user.children[0].photo_id}
                  size="xl"
                />
              ) : (
                <div className="flex -space-x-3">
                  {user.children.map((child, i) => (
                    <StudentAvatar
                      key={i}
                      name={child.name}
                      photoId={child.photo_id}
                      size="lg"
                      className="ring-2 ring-white"
                    />
                  ))}
                </div>
              )}
            </div>
          ) : (
            <div className="w-20 h-20 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-3">
              <span className="text-3xl font-bold text-blue-600">
                {(user?.name || user?.phone || "?")[0].toUpperCase()}
              </span>
            </div>
          )}
          <h2 className="text-xl font-bold text-gray-900">{user?.name || "Unnamed"}</h2>
          <p className="text-gray-500">{user?.phone}</p>
          <span className={`inline-block mt-2 text-xs px-2.5 py-1 rounded-full font-medium ${
            user?.role === "admin" ? "bg-red-100 text-red-700" :
            user?.role === "teacher" ? "bg-purple-100 text-purple-700" :
            "bg-blue-100 text-blue-700"
          }`}>
            {user?.role?.toUpperCase()}
          </span>
          {user?.grade && <p className="text-sm text-gray-500 mt-1">{user.grade}</p>}
        </div>

        {/* Children Info */}
        {user?.children && user.children.length > 0 && (
          <div className="bg-white rounded-xl p-4 shadow-sm">
            <h3 className="font-semibold text-gray-900 mb-3">
              {user.children.length === 1 ? "Your Child" : "Your Children"}
            </h3>
            <div className="space-y-3">
              {user.children.map((child, i) => (
                <div key={i} className="flex items-center p-2 rounded-lg bg-gray-50">
                  <StudentAvatar
                    name={child.name}
                    photoId={child.photo_id}
                    size="md"
                  />
                  <div className="ml-3">
                    <p className="font-medium text-gray-900">{child.name}</p>
                    <p className="text-sm text-gray-500">{child.grade}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Edit Name */}
        <div className="bg-white rounded-xl p-4 shadow-sm">
          <h3 className="font-semibold text-gray-900 mb-3">Update Name</h3>
          <div className="flex gap-2">
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Your name"
              className="flex-1 px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500"
            />
            <button
              onClick={handleSaveName}
              disabled={saving || !name.trim()}
              className="px-4 py-2.5 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition"
            >
              {saving ? "..." : "Save"}
            </button>
          </div>
        </div>

        {/* Set PIN */}
        <div className="bg-white rounded-xl p-4 shadow-sm">
          <h3 className="font-semibold text-gray-900 mb-1">
            {user?.has_pin ? "Change PIN" : "Set Quick Login PIN"}
          </h3>
          <p className="text-xs text-gray-500 mb-3">Set a 4-digit PIN for faster login</p>
          <div className="flex gap-2">
            <input
              type="password"
              value={pin}
              onChange={(e) => setPinVal(e.target.value)}
              placeholder="4-digit PIN"
              maxLength={4}
              className="flex-1 px-4 py-2.5 border border-gray-300 rounded-lg text-sm text-center tracking-widest focus:ring-2 focus:ring-blue-500"
            />
            <button
              onClick={handleSetPin}
              disabled={saving || pin.length !== 4}
              className="px-4 py-2.5 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition"
            >
              {saving ? "..." : "Set"}
            </button>
          </div>
        </div>

        {message && (
          <div className={`rounded-lg p-3 text-sm ${
            message.includes("Failed") ? "bg-red-50 text-red-700" : "bg-green-50 text-green-700"
          }`}>
            {message}
          </div>
        )}

        {/* Logout */}
        <button
          onClick={() => { logout(); navigate("/login"); }}
          className="w-full py-3 bg-red-50 text-red-600 rounded-xl font-medium hover:bg-red-100 transition"
        >
          Logout
        </button>

        <p className="text-center text-xs text-gray-400 pb-4">PPIS Campus Care v1.0</p>
      </div>
    </div>
  );
}
