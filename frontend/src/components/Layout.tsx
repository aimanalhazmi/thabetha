import { Bell, Bot, CreditCard, Languages, LogOut, QrCode, RefreshCw, Store, UserRound, Users, WalletCards } from "lucide-react";
import type { ReactNode } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { t, type TranslationKey } from "../lib/i18n";
import type { Language } from "../lib/types";

const navItems: Array<{ path: string; icon: typeof WalletCards; label: TranslationKey }> = [
  { path: "/dashboard", icon: WalletCards, label: "dashboard" },
  { path: "/debts", icon: CreditCard, label: "debts" },
  { path: "/profile", icon: UserRound, label: "profile" },
  { path: "/qr", icon: QrCode, label: "qr" },
  { path: "/groups", icon: Users, label: "groups" },
  { path: "/ai", icon: Bot, label: "ai" },
  { path: "/notifications", icon: Bell, label: "notifications" },
];

interface Props {
  language: Language;
  onToggleLanguage: () => void;
  onRefresh: () => void;
  currentPageLabel: TranslationKey;
  children: ReactNode;
}

export function Layout({ language, onToggleLanguage, onRefresh, currentPageLabel, children }: Props) {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();
  const tr = (key: TranslationKey) => t(language, key);

  function handleSignOut() {
    signOut();
    navigate("/");
  }

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <Store size={28} />
          <div>
            <strong>{tr("appName")}</strong>
            <span>Thabetha</span>
          </div>
        </div>

        {user && (
          <div className="user-info">
            <span className="user-name">{user.name}</span>
            <span className="user-email">{user.email}</span>
          </div>
        )}

        <nav className="nav-list">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.path}
                to={item.path}
                className={({ isActive }) => (isActive ? "active" : "")}
              >
                <Icon size={18} />
                <span>{tr(item.label)}</span>
              </NavLink>
            );
          })}
        </nav>

        <button className="ghost-button" onClick={onToggleLanguage}>
          <Languages size={18} />
          <span>{language === "ar" ? "English" : "العربية"}</span>
        </button>

        <button className="ghost-button signout-btn" onClick={handleSignOut}>
          <LogOut size={18} />
          <span>{tr("signOut")}</span>
        </button>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <span className="eyebrow">{user?.email ?? ""}</span>
            <h1>{tr(currentPageLabel)}</h1>
          </div>
          <button className="icon-button" title={tr("refresh")} onClick={onRefresh}>
            <RefreshCw size={18} />
          </button>
        </header>

        {children}
      </section>
    </main>
  );
}

// Shared sub-components used across pages
export function Stat({ label, value }: { label: string; value: string }) {
  return (
    <section className="stat">
      <span>{label}</span>
      <strong>{value}</strong>
    </section>
  );
}

export function Panel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="panel">
      <h2>{title}</h2>
      {children}
    </section>
  );
}

export function Input({
  label,
  value,
  onChange,
  type = "text",
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: string;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      <input type={type} value={value} onChange={(e) => onChange(e.target.value)} />
    </label>
  );
}
