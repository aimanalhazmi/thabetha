import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { supabase } from '../lib/supabaseClient';
import type { AuthUser, SignUpData } from '../lib/auth';
import {
  signIn as authSignIn,
  signUp as authSignUp,
  signOut as authSignOut,
  getCurrentUser,
} from '../lib/auth';

interface AuthState {
  user: AuthUser | null;
  isLoading: boolean;
}

interface AuthContextValue extends AuthState {
  isAuthenticated: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (data: SignUpData) => Promise<{ needsVerification: boolean }>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null,
    isLoading: true,
  });

  // Listen for Supabase auth state changes
  useEffect(() => {
    // Check initial session
    getCurrentUser().then((user) => {
      setState({ user, isLoading: false });
    });

    // Subscribe to auth changes
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      async (_event, session) => {
        if (session?.user) {
          const meta = session.user.user_metadata ?? {};
          setState({
            user: {
              id: session.user.id,
              email: session.user.email ?? '',
              name: meta.name ?? '',
              phone: meta.phone ?? '',
              account_type: meta.account_type ?? 'debtor',
            },
            isLoading: false,
          });
        } else {
          setState({ user: null, isLoading: false });
        }
      }
    );

    return () => {
      subscription.unsubscribe();
    };
  }, []);

  const signIn = useCallback(async (email: string, password: string) => {
    const user = await authSignIn(email, password);
    setState({ user, isLoading: false });
  }, []);

  const signUp = useCallback(async (data: SignUpData) => {
    return await authSignUp(data);
  }, []);

  const signOut = useCallback(async () => {
    await authSignOut();
    setState({ user: null, isLoading: false });
  }, []);

  return (
    <AuthContext.Provider
      value={{
        ...state,
        isAuthenticated: !!state.user,
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
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}
