import { Store } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { t } from "../lib/i18n";
import type { Language } from "../lib/types";

interface Props {
  language: Language;
  onToggleLanguage: () => void;
}

export function AuthPage({ language, onToggleLanguage }: Props) {
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { signIn, signUp } = useAuth();
  const navigate = useNavigate();

  // Sign-in fields
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  // Sign-up extras
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [accountType, setAccountType] = useState<"individual" | "business">("individual");
  const [taxId, setTaxId] = useState("");
  const [commercialReg, setCommercialReg] = useState("");

  const tr = (key: Parameters<typeof t>[1]) => t(language, key);

  async function handleSignIn(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await signIn(email, password);
      navigate("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign in failed");
    } finally {
      setLoading(false);
    }
  }

  async function handleSignUp(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await signUp({
        name,
        phone,
        email,
        password,
        account_type: accountType,
        tax_id: taxId || undefined,
        commercial_registration: commercialReg || undefined,
      });
      navigate("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign up failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-brand">
          <Store size={36} />
          <h1>{tr("appName")}</h1>
        </div>

        <h2>{mode === "signin" ? tr("welcomeBack") : tr("createAccount")}</h2>

        {error && <div className="message error">{error}</div>}

        {mode === "signin" ? (
          <form onSubmit={(e) => void handleSignIn(e)} className="auth-form">
            <label className="field">
              <span>{tr("email")}</span>
              <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
            </label>
            <label className="field">
              <span>{tr("password")}</span>
              <input type="password" required value={password} onChange={(e) => setPassword(e.target.value)} />
            </label>
            <button type="submit" className="primary-button" disabled={loading}>
              {loading ? "..." : tr("signIn")}
            </button>
          </form>
        ) : (
          <form onSubmit={(e) => void handleSignUp(e)} className="auth-form">
            <label className="field">
              <span>{tr("name")}</span>
              <input type="text" required value={name} onChange={(e) => setName(e.target.value)} />
            </label>
            <label className="field">
              <span>{tr("phone")}</span>
              <input type="tel" required value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+966500000000" />
            </label>
            <label className="field">
              <span>{tr("email")}</span>
              <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
            </label>
            <label className="field">
              <span>{tr("password")}</span>
              <input type="password" required minLength={6} value={password} onChange={(e) => setPassword(e.target.value)} />
            </label>
            <div className="field">
              <span>{tr("accountType")}</span>
              <div className="radio-group">
                <label>
                  <input type="radio" name="account_type" value="individual" checked={accountType === "individual"} onChange={() => setAccountType("individual")} />
                  <span>{tr("individual")}</span>
                </label>
                <label>
                  <input type="radio" name="account_type" value="business" checked={accountType === "business"} onChange={() => setAccountType("business")} />
                  <span>{tr("business")}</span>
                </label>
              </div>
            </div>
            {accountType === "business" && (
              <>
                <label className="field">
                  <span>{tr("taxId")}</span>
                  <input type="text" value={taxId} onChange={(e) => setTaxId(e.target.value)} />
                </label>
                <label className="field">
                  <span>{tr("commercialRegistration")}</span>
                  <input type="text" value={commercialReg} onChange={(e) => setCommercialReg(e.target.value)} />
                </label>
              </>
            )}
            <button type="submit" className="primary-button" disabled={loading}>
              {loading ? "..." : tr("signUp")}
            </button>
          </form>
        )}

        <p className="auth-toggle">
          {mode === "signin" ? tr("dontHaveAccount") : tr("alreadyHaveAccount")}
          {" "}
          <button className="link-button" onClick={() => { setMode(mode === "signin" ? "signup" : "signin"); setError(""); }}>
            {mode === "signin" ? tr("signUp") : tr("signIn")}
          </button>
        </p>

        <button className="ghost-button lang-toggle" onClick={onToggleLanguage}>
          {language === "ar" ? "English" : "العربية"}
        </button>
      </div>
    </div>
  );
}
