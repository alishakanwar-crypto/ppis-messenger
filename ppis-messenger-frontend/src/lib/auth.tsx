import { createContext, useContext, useState, useEffect, ReactNode } from "react";
import { getMe } from "./api";

export interface ChildInfo {
  name: string;
  grade: string;
  photo_id?: number;
}

export interface User {
  id: number;
  phone: string;
  name: string;
  role: string;
  grade: string;
  children: ChildInfo[];
  has_pin: boolean;
  avatar_url?: string;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  login: (token: string, user: User) => void;
  logout: () => void;
  refreshUser: () => Promise<void>;
  isAdmin: boolean;
  isTeacher: boolean;
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  token: null,
  login: () => {},
  logout: () => {},
  refreshUser: async () => {},
  isAdmin: false,
  isTeacher: false,
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(() => {
    const saved = localStorage.getItem("ppis_user");
    return saved ? JSON.parse(saved) : null;
  });
  const [token, setToken] = useState<string | null>(() =>
    localStorage.getItem("ppis_token")
  );

  const login = (newToken: string, newUser: User) => {
    setToken(newToken);
    setUser(newUser);
    localStorage.setItem("ppis_token", newToken);
    localStorage.setItem("ppis_user", JSON.stringify(newUser));
  };

  const logout = () => {
    setToken(null);
    setUser(null);
    localStorage.removeItem("ppis_token");
    localStorage.removeItem("ppis_user");
  };

  const refreshUser = async () => {
    try {
      const data = await getMe();
      setUser(data);
      localStorage.setItem("ppis_user", JSON.stringify(data));
    } catch {
      logout();
    }
  };

  useEffect(() => {
    if (token && !user) {
      refreshUser();
    }
  }, [token]);

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        login,
        logout,
        refreshUser,
        isAdmin: user?.role === "admin",
        isTeacher: user?.role === "teacher",
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
