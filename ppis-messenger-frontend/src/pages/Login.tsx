import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  requestOtp,
  verifyOtp,
  loginPin,
  loginStatus,
  requestSetupCode,
  setupPin,
} from "../lib/api";
import { useAuth, type User } from "../lib/auth";
import StudentAvatar from "../components/StudentAvatar";

type Step = "phone" | "otp" | "pin" | "success";
type PinStage = "phone" | "login" | "verify";

const PIN_ONLY_AUTH = import.meta.env.VITE_PIN_ONLY_AUTH === "true";
const PIN_MIN_LENGTH = Number(import.meta.env.VITE_PIN_MIN_LENGTH || "8");

export default function Login() {
  const [step, setStep] = useState<Step>(PIN_ONLY_AUTH ? "pin" : "phone");
  const [pinStage, setPinStage] = useState<PinStage>(PIN_ONLY_AUTH ? "phone" : "login");
  const [phone, setPhone] = useState("");
  const [otp, setOtp] = useState("");
  const [code, setCode] = useState("");
  const [pin, setPin] = useState("");
  const [confirmPin, setConfirmPin] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [otpMessage, setOtpMessage] = useState("");
  const [hasPin, setHasPin] = useState(false);
  const [loggedInUser, setLoggedInUser] = useState<User | null>(null);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleRequestOtp = async () => {
    setError("");
    setLoading(true);
    try {
      const data = await requestOtp(phone);
      const otpCode = data.otp_preview || data.otp;
      if (otpCode) {
        setOtpMessage(`Your OTP: ${otpCode}`);
      } else {
        setOtpMessage(data.message || "OTP sent to your phone");
      }
      setStep("otp");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to send OTP");
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyOtp = async () => {
    setError("");
    setLoading(true);
    try {
      const data = await verifyOtp(phone, otp);
      login(data.token, data.user);
      if (data.user.children && data.user.children.length > 0) {
        setLoggedInUser(data.user);
        setStep("success");
        setTimeout(() => navigate(data.user.role === "parent" || data.user.role === "teacher" ? "/portal" : "/"), 2500);
      } else {
        navigate(data.user.role === "parent" || data.user.role === "teacher" ? "/portal" : "/");
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Invalid OTP");
    } finally {
      setLoading(false);
    }
  };

  const handlePinLogin = async () => {
    setError("");
    setLoading(true);
    try {
      const data = await loginPin(phone, pin);
      login(data.token, data.user);
      if (data.user.children && data.user.children.length > 0) {
        setLoggedInUser(data.user);
        setStep("success");
        setTimeout(() => navigate("/"), 2500);
      } else {
        navigate("/");
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Invalid phone or passcode");
    } finally {
      setLoading(false);
    }
  };

  const handleRequestSetupCode = async () => {
    setError("");
    setLoading(true);
    try {
      await requestSetupCode(phone);
      setCode("");
      setPin("");
      setConfirmPin("");
      setPinStage("verify");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Unable to send login code");
    } finally {
      setLoading(false);
    }
  };

  const handlePinContinue = async () => {
    setError("");
    setLoading(true);
    try {
      const data = await loginStatus(phone);
      if (!data.authorized) {
        setError("This number isn't authorized to access the ERP. Please contact the school admin.");
        return;
      }
      setHasPin(data.has_pin);
      if (data.has_pin) {
        setPinStage("login");
      } else {
        await requestSetupCode(phone);
        setCode("");
        setPin("");
        setConfirmPin("");
        setPinStage("verify");
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Unable to check this phone number");
    } finally {
      setLoading(false);
    }
  };

  const handlePinSetup = async () => {
    setError("");
    if (code.length !== 6) {
      setError("Enter the 6-digit code sent to your WhatsApp");
      return;
    }
    if (pin.length < PIN_MIN_LENGTH) {
      setError(`Passcode must be at least ${PIN_MIN_LENGTH} characters`);
      return;
    }
    if (pin !== confirmPin) {
      setError("Passcodes do not match");
      return;
    }
    setLoading(true);
    try {
      const data = await setupPin(phone, code, pin);
      login(data.token, data.user);
      navigate("/");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Unable to set passcode");
    } finally {
      setLoading(false);
    }
  };

  const resetPinFlow = () => {
    setPhone("");
    setCode("");
    setPin("");
    setConfirmPin("");
    setHasPin(false);
    setError("");
    setPinStage("phone");
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-600 to-indigo-800 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-8">
        <div className="text-center mb-8">
          <div className="w-20 h-20 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg className="w-10 h-10 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-gray-900">PPIS Campus Care</h1>
          <p className="text-gray-500 mt-1">PP International School</p>
        </div>

        {error && (
          <div className="bg-red-50 text-red-700 rounded-lg p-3 mb-4 text-sm">
            {error}
          </div>
        )}

        {step === "phone" && (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Phone Number</label>
              <input
                type="tel"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="Enter your phone number"
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-lg"
                autoFocus
              />
            </div>
            <button
              onClick={handleRequestOtp}
              disabled={loading || phone.length < 10}
              className="w-full py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition"
            >
              {loading ? "Sending..." : "Get OTP"}
            </button>
            {hasPin && (
              <button
                onClick={() => setStep("pin")}
                className="w-full py-3 border border-gray-300 text-gray-700 rounded-lg font-medium hover:bg-gray-50 transition"
              >
                Login with PIN instead
              </button>
            )}
            <button
              onClick={() => { setHasPin(true); setPinStage("login"); setStep("pin"); }}
              className="w-full text-sm text-blue-600 hover:underline"
            >
              Already have a PIN? Login with PIN
            </button>
          </div>
        )}

        {step === "otp" && (
          <div className="space-y-4">
            <p className="text-sm text-green-600 text-center">{otpMessage}</p>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Enter OTP</label>
              <input
                type="text"
                value={otp}
                onChange={(e) => setOtp(e.target.value)}
                placeholder="6-digit OTP"
                maxLength={6}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-center text-2xl tracking-widest"
                autoFocus
              />
            </div>
            <button
              onClick={handleVerifyOtp}
              disabled={loading || otp.length < 4}
              className="w-full py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition"
            >
              {loading ? "Verifying..." : "Verify OTP"}
            </button>
            <button
              onClick={() => { setStep("phone"); setOtp(""); }}
              className="w-full text-sm text-gray-500 hover:underline"
            >
              Change phone number
            </button>
          </div>
        )}

        {step === "success" && loggedInUser && (
          <div className="text-center space-y-4 animate-fade-in">
            <div className="flex justify-center">
              {loggedInUser.children.length === 1 ? (
                <StudentAvatar
                  name={loggedInUser.children[0].name}
                  photoId={loggedInUser.children[0].photo_id}
                  size="xl"
                />
              ) : (
                <div className="flex -space-x-3">
                  {loggedInUser.children.map((child, i) => (
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
            <div>
              <p className="text-lg font-semibold text-gray-900">
                Welcome, Parent of
              </p>
              {loggedInUser.children.map((child, i) => (
                <p key={i} className="text-blue-600 font-bold text-xl">
                  {child.name} <span className="text-sm font-normal text-gray-500">({child.grade})</span>
                </p>
              ))}
            </div>
            <div className="flex items-center justify-center text-sm text-gray-400">
              <svg className="w-4 h-4 mr-1 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
              </svg>
              Opening PPIS Campus Care...
            </div>
          </div>
        )}

        {step === "pin" && PIN_ONLY_AUTH && pinStage === "phone" && (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Phone Number</label>
              <input
                type="tel"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="Enter your phone number"
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-lg"
                autoFocus
              />
            </div>
            <button
              onClick={handlePinContinue}
              disabled={loading || phone.length < 10}
              className="w-full py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition"
            >
              {loading ? "Checking..." : "Continue"}
            </button>
          </div>
        )}

        {step === "pin" && (!PIN_ONLY_AUTH || pinStage === "login") && (
          <div className="space-y-4">
            {!PIN_ONLY_AUTH ? (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Phone Number</label>
                <input
                  type="tel"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  placeholder="Enter your phone number"
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
              </div>
            ) : (
              <p className="text-sm text-gray-500">
                Signing in with <span className="font-medium text-gray-700">{phone}</span>
              </p>
            )}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Admin passcode</label>
              <input
                type="password"
                value={pin}
                onChange={(e) => setPin(e.target.value)}
                placeholder={`${PIN_MIN_LENGTH}–12 characters`}
                maxLength={12}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-center text-2xl tracking-widest"
                autoFocus
              />
            </div>
            <button
              onClick={handlePinLogin}
              disabled={loading || pin.length < PIN_MIN_LENGTH || phone.length < 10}
              className="w-full py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition"
            >
              {loading ? "Logging in..." : "Secure login"}
            </button>
            {!PIN_ONLY_AUTH && (
              <button
                onClick={() => { setStep("phone"); setPin(""); }}
                className="w-full text-sm text-gray-500 hover:underline"
              >
                Login with OTP instead
              </button>
            )}
            {PIN_ONLY_AUTH && (
              <>
                <button
                  onClick={handleRequestSetupCode}
                  disabled={loading}
                  className="w-full text-sm text-blue-600 hover:underline disabled:opacity-50"
                >
                  Forgot / reset passcode
                </button>
                <button
                  onClick={resetPinFlow}
                  className="w-full text-sm text-gray-500 hover:underline"
                >
                  Change phone number
                </button>
              </>
            )}
          </div>
        )}

        {step === "pin" && PIN_ONLY_AUTH && pinStage === "verify" && (
          <div className="space-y-4">
            <p className="text-sm text-gray-600">
              Enter the code sent to your WhatsApp.
            </p>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">WhatsApp code</label>
              <input
                type="text"
                inputMode="numeric"
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                placeholder="6-digit code"
                maxLength={6}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-center text-2xl tracking-widest"
                autoFocus
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Create your passcode</label>
              <input
                type="password"
                value={pin}
                onChange={(e) => setPin(e.target.value)}
                placeholder={`${PIN_MIN_LENGTH}–12 characters`}
                maxLength={12}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-center text-2xl tracking-widest"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Confirm passcode</label>
              <input
                type="password"
                value={confirmPin}
                onChange={(e) => setConfirmPin(e.target.value)}
                placeholder="Re-enter your passcode"
                maxLength={12}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-center text-2xl tracking-widest"
              />
            </div>
            <button
              onClick={handlePinSetup}
              disabled={loading || code.length !== 6 || pin.length < PIN_MIN_LENGTH || confirmPin.length < PIN_MIN_LENGTH}
              className="w-full py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition"
            >
              {loading ? "Setting passcode..." : "Set passcode & log in"}
            </button>
            <button
              onClick={handleRequestSetupCode}
              disabled={loading}
              className="w-full text-sm text-blue-600 hover:underline disabled:opacity-50"
            >
              Resend code
            </button>
            <button
              onClick={resetPinFlow}
              className="w-full text-sm text-gray-500 hover:underline"
            >
              Change phone number
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
