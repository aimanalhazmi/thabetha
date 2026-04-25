import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import {
  type AuthUser,
  clearTokens,
  getStoredToken,
  getStoredUser,
  signIn as authSignIn,
  signUp as authSignUp,
  storeTokens,
  type SignUpData,
} from "../lib/auth";

interface AuthState {
  user: AuthUser | null;
  token: string | null;
  isLoading: boolean;
}

interface AuthContextValue extends AuthState {
  isAuthenticated: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (data: SignUpData) => Promise<void>;
  signOut: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null,
    token: null,
    isLoading: true,
  });

  // Restore session from localStorage on mount
  useEffect(() => {
    const token = getStoredToken();
    const user = getStoredUser();
    setState({ user, token, isLoading: false });
  }, []);

  const signIn = useCallback(async (email: string, password: string) => {
    const { tokens, user } = await authSignIn(email, password);
    storeTokens(tokens, user);
    setState({ user, token: tokens.access_token, isLoading: false });
  }, []);

  const signUp = useCallback(async (data: SignUpData) => {
    const { tokens, user } = await authSignUp(data);
    storeTokens(tokens, user);
    setState({ user, token: tokens.access_token, isLoading: false });
  }, []);

  const signOut = useCallback(() => {
    clearTokens();
    setState({ user: null, token: null, isLoading: false });
  }, []);

  return (
    <AuthContext.Provider
      value={{
        ...state,
        isAuthenticated: !!state.token,
        signIn,
        signUp,
        signOut,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
