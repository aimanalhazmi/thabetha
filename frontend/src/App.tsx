import { useLayoutEffect, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AuthProvider, useAuth } from "./contexts/AuthContext";
import { Layout } from "./components/Layout";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { AuthPage } from "./pages/AuthPage";
import { DashboardPage } from "./pages/DashboardPage";
import { DebtsPage } from "./pages/DebtsPage";
import { ProfilePage } from "./pages/ProfilePage";
import { QRPage } from "./pages/QRPage";
import { GroupsPage } from "./pages/GroupsPage";
import { AIPage } from "./pages/AIPage";
import { NotificationsPage } from "./pages/NotificationsPage";
import { LandingPage } from "./pages/LandingPage";
import { SettingsPage } from "./pages/SettingsPage";
import type { TranslationKey } from "./lib/i18n";
import type { Language } from "./lib/types";
import { loadInitialLocale, persistLocale } from "./lib/localePersistence";

const routeLabels: Record<string, TranslationKey> = {
  "/dashboard": "dashboard",
  "/debts": "debts",
  "/profile": "profile",
  "/qr": "qr",
  "/groups": "groups",
  "/ai": "ai",
  "/notifications": "notifications",
  "/settings": "settings",
};

interface ShellProps {
  language: Language;
  onToggleLanguage: () => void;
}

function AppShell({ language, onToggleLanguage }: ShellProps) {
  const location = useLocation();
  const [refreshKey, setRefreshKey] = useState(0);
  const currentLabel = (routeLabels[location.pathname] ?? "dashboard") as TranslationKey;

  return (
    <ProtectedRoute>
      <Layout
        language={language}
        onToggleLanguage={onToggleLanguage}
        onRefresh={() => setRefreshKey((k) => k + 1)}
        currentPageLabel={currentLabel}
      >
        <Routes>
          <Route path="/dashboard" element={<DashboardPage language={language} message="" key={refreshKey} />} />
          <Route path="/debts" element={<DebtsPage language={language} key={refreshKey} />} />
          <Route path="/profile" element={<ProfilePage language={language} key={refreshKey} />} />
          <Route path="/qr" element={<QRPage language={language} key={refreshKey} />} />
          <Route path="/groups" element={<GroupsPage language={language} key={refreshKey} />} />
          <Route path="/ai" element={<AIPage language={language} key={refreshKey} />} />
          <Route path="/notifications" element={<NotificationsPage language={language} key={refreshKey} />} />
          <Route path="/settings" element={<SettingsPage language={language} onToggleLanguage={onToggleLanguage} key={refreshKey} />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </Layout>
    </ProtectedRoute>
  );
}

function RootRoute({ language, onToggleLanguage }: ShellProps) {
  const { isAuthenticated, isLoading } = useAuth();
  if (isLoading) return null;
  if (isAuthenticated) return <Navigate to="/dashboard" replace />;
  return <LandingPage language={language} onToggleLanguage={onToggleLanguage} />;
}

function AppContent() {
  const { isAuthenticated, profileLocale } = useAuth();
  const [language, setLanguage] = useState<Language>(() => loadInitialLocale());

  // When the user signs in and the profile locale loads, sync the app state.
  useLayoutEffect(() => {
    if (profileLocale) setLanguage(profileLocale);
  }, [profileLocale]);

  const toggleLanguage = () => {
    setLanguage((l) => {
      const next = l === "ar" ? "en" : "ar";
      void persistLocale(next, isAuthenticated);
      return next;
    });
  };

  useLayoutEffect(() => {
    document.documentElement.lang = language;
    document.documentElement.dir = language === "ar" ? "rtl" : "ltr";
  }, [language]);

  return (
    <Routes>
      <Route path="/" element={<RootRoute language={language} onToggleLanguage={toggleLanguage} />} />
      <Route path="/auth" element={<AuthPage language={language} onToggleLanguage={toggleLanguage} />} />
      <Route path="/*" element={<AppShell language={language} onToggleLanguage={toggleLanguage} />} />
    </Routes>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppContent />
      </BrowserRouter>
    </AuthProvider>
  );
}
