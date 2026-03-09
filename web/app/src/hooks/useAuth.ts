import { create } from "zustand";
import { loadAuthTokenFromStorage, setAuthToken as setApiToken } from "../lib/api";

type AuthStatus = "guest" | "authed";

interface AuthState {
  token: string | null;
  status: AuthStatus;
  setToken: (token: string | null) => void;
  clear: () => void;
}

const existing = loadAuthTokenFromStorage();

export const useAuth = create<AuthState>((set) => ({
  token: existing,
  status: existing ? "authed" : "guest",
  setToken: (token) =>
    set(() => {
      setApiToken(token);
      return { token, status: token ? "authed" : "guest" };
    }),
  clear: () =>
    set(() => {
      setApiToken(null);
      return { token: null, status: "guest" };
    }),
}));
