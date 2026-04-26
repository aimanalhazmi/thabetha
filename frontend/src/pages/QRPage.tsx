import { QrCode, Search } from "lucide-react";
import { useEffect, useState } from "react";
import QRCode from "react-qr-code";
import { Input, Panel } from "../components/Layout";
import { apiRequest } from "../lib/api";
import { t } from "../lib/i18n";
import type { Language, Profile, QRToken } from "../lib/types";

interface Props { language: Language }

export function QRPage({ language }: Props) {
  const tr = (key: Parameters<typeof t>[1]) => t(language, key);
  const [qr, setQr] = useState<QRToken | null>(null);
  const [message, setMessage] = useState("");

  // QR lookup state
  const [lookupToken, setLookupToken] = useState("");
  const [foundProfile, setFoundProfile] = useState<Profile | null>(null);
  const [lookupError, setLookupError] = useState("");
  const [lookupLoading, setLookupLoading] = useState(false);
  const [copiedId, setCopiedId] = useState(false);

  useEffect(() => {
    void apiRequest<QRToken>("/qr/current").then(setQr).catch(() => {});
  }, []);

  async function rotate() {
    try {
      const updated = await apiRequest<QRToken>("/qr/rotate", { method: "POST" });
      setQr(updated);
      setMessage(language === "ar" ? "تم تجديد الرمز" : "QR rotated");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Failed");
    }
  }

  async function lookupQr() {
    if (!lookupToken.trim()) return;
    setLookupLoading(true);
    setLookupError("");
    setFoundProfile(null);
    try {
      const profile = await apiRequest<Profile>(`/qr/resolve/${encodeURIComponent(lookupToken.trim())}`);
      setFoundProfile(profile);
    } catch {
      setLookupError(tr("invalidQrToken"));
    } finally {
      setLookupLoading(false);
    }
  }

  function copyId(id: string) {
    void navigator.clipboard.writeText(id).then(() => {
      setCopiedId(true);
      setTimeout(() => setCopiedId(false), 2000);
    });
  }

  return (
    <section className="split">
      {/* My QR code */}
      <Panel title={tr("qr")}>
        {message && <div className="message">{message}</div>}
        {qr ? (
          <div className="qr-layout">
            <div className="qr-box">
              <QRCode value={qr.token} size={180} />
            </div>
            <div>
              <p className="token">{qr.token}</p>
              <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                {language === "ar" ? "ينتهي:" : "Expires:"} {new Date(qr.expires_at).toLocaleString()}
              </p>
              <button className="primary-button" onClick={() => void rotate()}>
                <QrCode size={18} /><span>{tr("rotate")}</span>
              </button>
            </div>
          </div>
        ) : (
          <p className="empty">{tr("noData")}</p>
        )}
      </Panel>

      {/* QR lookup — paste someone else's token to get their ID */}
      <Panel title={tr("scanQr")}>
        <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "8px" }}>
          {language === "ar"
            ? "الصق رمز QR الخاص بالمدين لتعبئة معرّفه تلقائياً عند إنشاء دين."
            : "Paste a debtor's QR token to fill their ID when creating a debt."}
        </p>
        <Input
          label={tr("qrToken")}
          value={lookupToken}
          onChange={setLookupToken}
          placeholder={language === "ar" ? "الصق الرمز هنا..." : "Paste token here..."}
        />
        <button
          className="primary-button"
          disabled={!lookupToken.trim() || lookupLoading}
          onClick={() => void lookupQr()}
        >
          <Search size={18} />
          <span>{lookupLoading ? "..." : tr("lookupDebtor")}</span>
        </button>

        {lookupError && <div className="message error">{lookupError}</div>}

        {foundProfile && (
          <div className="qr-result">
            <div className="qr-result-header">
              <strong>{tr("debtorFound")}</strong>
            </div>
            <div className="qr-result-row">
              <span>{tr("name")}</span>
              <strong>{foundProfile.name}</strong>
            </div>
            <div className="qr-result-row">
              <span>{tr("phone")}</span>
              <strong>{foundProfile.phone}</strong>
            </div>
            <div className="qr-result-row">
              <span>ID</span>
              <code style={{ fontSize: "0.75rem", wordBreak: "break-all" }}>{foundProfile.id}</code>
            </div>
            <button
              className="primary-button"
              onClick={() => copyId(foundProfile.id)}
              style={{ marginTop: "8px" }}
            >
              {copiedId
                ? (language === "ar" ? "تم النسخ!" : "Copied!")
                : (language === "ar" ? "نسخ المعرّف" : "Copy ID")}
            </button>
          </div>
        )}
      </Panel>
    </section>
  );
}
