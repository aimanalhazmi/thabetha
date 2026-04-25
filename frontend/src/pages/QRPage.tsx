import { QrCode } from "lucide-react";
import { useEffect, useState } from "react";
import QRCode from "react-qr-code";
import { Panel } from "../components/Layout";
import { apiRequest } from "../lib/api";
import { t } from "../lib/i18n";
import type { Language, QRToken } from "../lib/types";

interface Props { language: Language }

export function QRPage({ language }: Props) {
  const tr = (key: Parameters<typeof t>[1]) => t(language, key);
  const [qr, setQr] = useState<QRToken | null>(null);
  const [message, setMessage] = useState("");

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

  return (
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
  );
}
