import { QrCode, Search } from "lucide-react";
import { useEffect, useState } from "react";
import QRCode from "react-qr-code";
import { Input, Panel } from "../components/Layout";
import { useAuth } from "../contexts/AuthContext";
import { apiRequest } from "../lib/api";
import { t } from "../lib/i18n";
import type { Language, Profile, QRToken } from "../lib/types";

interface Props { language: Language }

export function QRPage({ language }: Props) {
  const tr = (key: Parameters<typeof t>[1]) => t(language, key);
  const { user } = useAuth();
  const isCreditor = user?.account_type === 'creditor' || user?.account_type === 'both';
  const [qr, setQr] = useState<QRToken | null>(null);
  const [message, setMessage] = useState("");
  const [scanToken, setScanToken] = useState("");
  const [scanned, setScanned] = useState<Profile | null>(null);
  const [scanError, setScanError] = useState("");

  useEffect(() => {
    void apiRequest<QRToken>("/qr/current").then(setQr).catch(() => {});
  }, []);

  async function rotate() {
    try {
      const updated = await apiRequest<QRToken>("/qr/rotate", { method: "POST" });
      setQr(updated);
      setMessage("QR rotated");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Failed");
    }
  }

  async function lookup() {
    setScanError("");
    setScanned(null);
    if (!scanToken.trim()) return;
    try {
      const profile = await apiRequest<Profile>(`/qr/resolve/${encodeURIComponent(scanToken.trim())}`);
      setScanned(profile);
    } catch (err) {
      setScanError(err instanceof Error ? err.message : "Lookup failed");
    }
  }

  return (
    <section className="split">
      <Panel title={tr("qr")}>
        {message && <div className="message">{message}</div>}
        {qr ? (
          <div className="qr-layout">
            <div className="qr-box">
              <QRCode value={qr.token} size={180} />
            </div>
            <div>
              <p className="token">{qr.token}</p>
              <p>{new Date(qr.expires_at).toLocaleString()}</p>
              <button className="primary-button" onClick={() => void rotate()}>
                <QrCode size={18} /><span>{tr("rotate")}</span>
              </button>
            </div>
          </div>
        ) : (
          <p className="empty">{tr("noData")}</p>
        )}
      </Panel>

      {isCreditor && (
        <Panel title={tr("scanCustomerQr")}>
          <p style={{ color: '#64748b', marginTop: 0 }}>{tr("scanCustomerQrDesc")}</p>
          <Input label={tr("enterToken")} value={scanToken} onChange={setScanToken} />
          <button className="primary-button" onClick={() => void lookup()}>
            <Search size={18} /><span>{tr("lookup")}</span>
          </button>
          {scanError && <div className="message error" style={{ marginTop: '0.75rem' }}>{scanError}</div>}
          {scanned && (
            <div className="customer-profile-card" style={{ marginTop: '1rem' }}>
              <h3>{tr("customerProfile")}</h3>
              <p><strong>{scanned.name}</strong></p>
              <p>{scanned.phone}</p>
              <p>{tr("trustScore")}: <strong>{scanned.trust_score} / 100</strong></p>
              <p style={{ fontSize: '0.75rem', color: '#94a3b8' }}>ID: {scanned.id}</p>
            </div>
          )}
        </Panel>
      )}
    </section>
  );
}
