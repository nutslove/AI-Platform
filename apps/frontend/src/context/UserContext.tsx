import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import type { User } from "../types";
import { api, getCurrentUserId, setCurrentUserId } from "../api/client";

interface UserContextValue {
  user: User | null;
  users: User[];
  loading: boolean;
  /** 簡易ログイン: ユーザを切り替える */
  switchUser: (userId: string) => Promise<void>;
  isAdmin: boolean;
}

const UserContext = createContext<UserContextValue | undefined>(undefined);

export function UserProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const allUsers = await api.listLoginUsers();
      setUsers(allUsers);
      const currentId = getCurrentUserId() ?? allUsers[0]?.id ?? null;
      if (currentId) {
        setCurrentUserId(currentId);
        setUser(await api.me());
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const switchUser = useCallback(async (userId: string) => {
    setCurrentUserId(userId);
    setUser(await api.me());
  }, []);

  return (
    <UserContext.Provider
      value={{
        user,
        users,
        loading,
        switchUser,
        isAdmin: user?.role === "admin",
      }}
    >
      {children}
    </UserContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useUser(): UserContextValue {
  const ctx = useContext(UserContext);
  if (!ctx) throw new Error("useUser must be used within UserProvider");
  return ctx;
}
