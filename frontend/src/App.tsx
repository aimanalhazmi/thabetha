import { useEffect, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AuthProvider } from "./contexts/AuthContext";
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
import type { TranslationKey } from "./lib/i18n";
import type { Language } from "./lib/types";

const routeLabels: Record<string, TranslationKey> = {
  "/dashboard": "dashboard",
  "/debts": "debts",
  "/profile": "profile",
  "/qr": "qr",
  "/groups": "groups",
  "/ai": "ai",
  "/notifications": "notifications",
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
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </Layout>
    </ProtectedRoute>
  );
}

export default function App() {
  const [language, setLanguage] = useState<Language>("ar");

  const toggleLanguage = () => setLanguage((l) => (l === "ar" ? "en" : "ar"));

  useEffect(() => {
    document.documentElement.lang = language;
    document.documentElement.dir = language === "ar" ? "rtl" : "ltr";
  }, [language]);

  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<AuthPage language={language} onToggleLanguage={toggleLanguage} />} />
          <Route path="/*" element={<AppShell language={language} onToggleLanguage={toggleLanguage} />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
