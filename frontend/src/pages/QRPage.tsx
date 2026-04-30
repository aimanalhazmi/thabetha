import { Clock, QrCode, RotateCcw, Search, UserRound } from "lucide-react";
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

function getInitials(name: string) {
  return name.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase();
}

function ScoreBar({ score }: { score: number }) {
  const color = score >= 70 ? 'var(--success)' : score >= 40 ? 'var(--warning)' : 'var(--danger)';
  return (
    <div className="score-bar">
      <div className="score-bar-fill" style={{ width: `${score}%`, background: color }} />
    </div>
  );
}

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
  const [resolvedToken, setResolvedToken] = useState<string | null>(null);

  // ── Data fetching — untouched ─────────────────────────────────
  useEffect(() => {
    void apiRequest<QRToken>("/qr/current").then(setQr).catch(() => {});
  }, []);

  // ── Handlers — untouched ──────────────────────────────────────
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

  function confirmCreateDebt() {
    if (!resolvedToken) return;
    navigate(`/debts/new?qr_token=${encodeURIComponent(resolvedToken)}`);
  }

  function dismissScanned() {
    setScanned(null);
    setResolvedToken(null);
    setScanToken("");
  }

  function formatExpiry(iso: string) {
    try {
      return new Date(iso).toLocaleString(
        language === 'ar' ? 'ar-SA' : 'en-GB',
        { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }
      );
    } catch { return iso; }
  }

  return (
    <section className="split">
      {/* ── My QR panel — debtor only ── */}
      {isDebtor && <Panel title={tr("qr")}>
        {message && <div className="message">{message}</div>}
        {qr ? (
          <div className="qr-display-card">
            <div className="qr-display-card__ring">
              <QRCode value={qr.token} size={168} />
            </div>
            <div className="qr-token-pill">
              <span>{qr.token}</span>
            </div>
            <div className="qr-expiry">
              <Clock size={13} />
              <span>{formatExpiry(qr.expires_at)}</span>
            </div>
            <button className="primary-button" style={{ width: '100%', justifyContent: 'center' }} onClick={() => void rotate()}>
              <RotateCcw size={16} /><span>{tr("rotate")}</span>
            </button>
          </div>
        ) : (
          <div className="dash-loading"><div className="spinner" /></div>
        )}
      </Panel>}

      {/* ── Scan customer QR (creditor only) ── */}
      {isCreditor && (
        <Panel title={tr("scanCustomerQr")}>
          <p style={{ color: 'var(--text-secondary)', margin: '0 0 4px', fontSize: '0.88rem' }}>
            {tr("scanCustomerQrDesc")}
          </p>
          <Input label={tr("enterToken")} value={scanToken} onChange={setScanToken} />
          <button className="primary-button" style={{ width: '100%', justifyContent: 'center' }} onClick={() => void lookup()}>
            <Search size={16} /><span>{tr("lookup")}</span>
          </button>
          {scanError && <div className="message error">{scanError}</div>}

          {scanned && (
            <div className="qr-profile-card">
              <div className="qr-profile-card__top">
                <div className="qr-profile-card__avatar">{getInitials(scanned.name)}</div>
                <div className="qr-profile-card__info">
                  <strong className="qr-profile-card__name">{scanned.name}</strong>
                  <span className="qr-profile-card__phone">···· {scanned.phone.slice(-4)}</span>
                </div>
                <UserRound size={16} color="var(--text-muted)" />
              </div>

              <div className="qr-profile-card__score">
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                  <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                    {tr("commitmentIndicator")}
                  </span>
                  <strong style={{ fontSize: '0.82rem', color: 'var(--primary-dark)' }}>
                    {scanned.commitment_score} / 100
                  </strong>
                </div>
                <ScoreBar score={scanned.commitment_score} />
              </div>

              <div className="qr-profile-card__actions">
                <button className="primary-button" style={{ flex: 1, justifyContent: 'center' }} onClick={confirmCreateDebt}>
                  {tr("createDebtForPerson")}
                </button>
                <button className="ghost-button" onClick={dismissScanned}>
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
