import { QrCode, Search } from "lucide-react";
import { useEffect, useState } from "react";
import QRCode from "react-qr-code";
import { useNavigate } from "react-router-dom";
import { Input, Panel } from "../components/Layout";
import { useAuth } from "../contexts/AuthContext";
import { apiRequest } from "../lib/api";
import { humanizeError } from "../lib/errors";
import { t } from "../lib/i18n";
import type { Language, Profile, QRToken } from "../lib/types";

interface Props { language: Language }

export function QRPage({ language }: Props) {
  const tr = (key: Parameters<typeof t>[1]) => t(language, key);
  const { user } = useAuth();
  const navigate = useNavigate();
  const isCreditor = user?.account_type === 'creditor' || user?.account_type === 'both' || user?.account_type === 'business';
  const isDebtor = user?.account_type === 'debtor' || user?.account_type === 'both';
  const [qr, setQr] = useState<QRToken | null>(null);
  const [message, setMessage] = useState("");
  const [scanToken, setScanToken] = useState("");
  const [scanned, setScanned] = useState<Profile | null>(null);
  const [scanError, setScanError] = useState("");
  // Track the resolved token separately so the confirm step can navigate with it
  const [resolvedToken, setResolvedToken] = useState<string | null>(null);

  useEffect(() => {
    void apiRequest<QRToken>("/qr/current").then(setQr).catch(() => {});
  }, []);

  async function rotate() {
    try {
      const updated = await apiRequest<QRToken>("/qr/rotate", { method: "POST" });
      setQr(updated);
      setMessage("QR rotated");
    } catch (err) {
      setMessage(humanizeError(err, language, 'generic'));
    }
  }

  async function lookup() {
    setScanError("");
    setScanned(null);
    setResolvedToken(null);
    if (!scanToken.trim()) return;
    try {
      const token = scanToken.trim();
      const profile = await apiRequest<Profile>(`/qr/resolve/${encodeURIComponent(token)}`);
      setScanned(profile);
      setResolvedToken(token);
    } catch (err) {
      setScanError(humanizeError(err, language, 'qrResolve'));
    }
  }

  // T008: navigate to create-debt with QR token on confirm
  function confirmCreateDebt() {
    if (!resolvedToken) return;
    navigate(`/debts/new?qr_token=${encodeURIComponent(resolvedToken)}`);
  }

  function dismissScanned() {
    setScanned(null);
    setResolvedToken(null);
    setScanToken("");
  }

  return (
    <section className="split">
      {isDebtor && (
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
            <p className="empty">{tr("loading")}</p>
          )}
        </Panel>
      )}

      {isCreditor && (
        <Panel title={tr("scanCustomerQr")}>
          <p style={{ color: '#64748b', marginTop: 0 }}>{tr("scanCustomerQrDesc")}</p>
          <Input label={tr("enterToken")} value={scanToken} onChange={setScanToken} />
          <button className="primary-button" onClick={() => void lookup()}>
            <Search size={18} /><span>{tr("lookup")}</span>
          </button>
          {scanError && <div className="message error" style={{ marginTop: '0.75rem' }}>{scanError}</div>}
          {/* T007: confirm step — profile preview + Create debt / Cancel actions */}
          {scanned && (
            <div className="customer-profile-card" style={{ marginTop: '1rem' }}>
              <h3>{tr("customerProfile")}</h3>
              <p><strong>{scanned.name}</strong></p>
              <p>···· {scanned.phone.slice(-4)}</p>
              <p>{tr("commitmentIndicator")}: <strong>{scanned.commitment_score} / 100</strong></p>
              <div style={{ display: 'flex', gap: 8, marginTop: '0.75rem' }}>
                <button className="primary-button" onClick={confirmCreateDebt} style={{ flex: 1 }}>
                  {tr("createDebtForPerson")}
                </button>
                <button className="secondary-button" onClick={dismissScanned} style={{ flex: 1 }}>
                  {tr("cancel")}
                </button>
              </div>
            </div>
          )}
        </Panel>
      )}
    </section>
  );
}
