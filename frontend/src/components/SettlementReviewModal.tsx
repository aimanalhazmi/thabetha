import { useState } from "react";
import { useAuth } from "../contexts/AuthContext";
import { errorCode, settlements } from "../lib/api";
import { t, type TranslationKey } from "../lib/i18n";
import type { Language, SettlementProposal } from "../lib/types";

interface Props {
  groupId: string;
  proposal: SettlementProposal;
  language: Language;
  onClose: () => void;
  onUpdated: (updated: SettlementProposal) => void;
}

function expiryCountdown(expiresAt: string): string {
  const diff = new Date(expiresAt).getTime() - Date.now();
  if (diff <= 0) return "0h";
  const hours = Math.floor(diff / 3_600_000);
  const days = Math.floor(hours / 24);
  if (days > 0) return `${days}d ${hours % 24}h`;
  return `${hours}h`;
}

export function SettlementReviewModal({ groupId, proposal, language, onClose, onUpdated }: Props) {
  const tr = (key: TranslationKey) => t(language, key);
  const { user } = useAuth();
  const [busy, setBusy] = useState(false);
  const [raceBanner, setRaceBanner] = useState("");

  const currentUserId = user?.id;
  const myConfirmation = proposal.confirmations.find((c) => c.user_id === currentUserId);
  const isPending = myConfirmation?.status === "pending";

  async function handleAction(action: "confirm" | "reject") {
    setBusy(true);
    setRaceBanner("");
    try {
      const updated = await (action === "confirm"
        ? settlements.confirm(groupId, proposal.id)
        : settlements.reject(groupId, proposal.id));
      onUpdated(updated);
      onClose();
    } catch (err) {
      const code = errorCode(err);
      if (code === "ProposalNotOpen") {
        // Race: another party already rejected — refresh and show banner.
        try {
          const refreshed = await settlements.get(groupId, proposal.id);
          onUpdated(refreshed);
        } catch {
          // ignore
        }
        setRaceBanner(tr("errorProposalNotOpen"));
      } else {
        setRaceBanner(err instanceof Error ? err.message : tr("errorGeneric"));
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.45)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 1000,
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        style={{
          background: "var(--surface, #fff)",
          borderRadius: 12,
          padding: "24px",
          maxWidth: 480,
          width: "90%",
          maxHeight: "80vh",
          overflowY: "auto",
        }}
      >
        <h2 style={{ margin: "0 0 8px" }}>{tr("settlementReviewTitle")}</h2>

        {raceBanner && (
          <div className="message" style={{ marginBottom: 12 }}>
            {raceBanner}
          </div>
        )}

        <p className="muted" style={{ margin: "0 0 16px" }}>
          {tr("settlementExpiresIn")}: {expiryCountdown(proposal.expires_at)}
        </p>

        {/* Transfer list */}
        {proposal.transfers.length > 0 && (
          <>
            <p style={{ fontWeight: 600, margin: "0 0 8px" }}>{tr("settlementTransfersHeading")}</p>
            <ul className="simple-list" style={{ marginBottom: 16 }}>
              {proposal.transfers.map((tf, i) => {
                const myRole =
                  tf.payer_id === currentUserId
                    ? tr("settlementRolePayer")
                    : tf.receiver_id === currentUserId
                    ? tr("settlementRoleReceiver")
                    : tr("settlementRoleObserver");
                const isInvolved = tf.payer_id === currentUserId || tf.receiver_id === currentUserId;
                return (
                  <li
                    key={i}
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      fontWeight: isInvolved ? 600 : undefined,
                      padding: "4px 0",
                    }}
                  >
                    <span>
                      {tf.payer_id} → {tf.receiver_id}:{" "}
                      <strong>
                        {tf.amount} {proposal.currency}
                      </strong>
                    </span>
                    <span className="muted">{myRole}</span>
                  </li>
                );
              })}
            </ul>
          </>
        )}

        {/* Confirmation roster */}
        {proposal.confirmations.length > 0 && (
          <>
            <p style={{ fontWeight: 600, margin: "0 0 8px" }}>{tr("settlementConfirm")}</p>
            <ul className="simple-list" style={{ marginBottom: 16 }}>
              {proposal.confirmations.map((c) => (
                <li
                  key={c.user_id}
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    fontWeight: c.user_id === currentUserId ? 600 : undefined,
                    padding: "4px 0",
                  }}
                >
                  <span>{c.user_id}</span>
                  <span className="muted">{c.status}</span>
                </li>
              ))}
            </ul>
          </>
        )}

        {/* Action buttons for pending required parties only */}
        {isPending && proposal.status === "open" && (
          <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
            <button
              className="primary-button"
              disabled={busy}
              onClick={() => void handleAction("confirm")}
              style={{ flex: 1 }}
            >
              {tr("settlementConfirm")}
            </button>
            <button
              className="secondary-button"
              disabled={busy}
              onClick={() => void handleAction("reject")}
              style={{ flex: 1 }}
            >
              {tr("settlementReject")}
            </button>
          </div>
        )}

        <button
          className="ghost-button"
          onClick={onClose}
          style={{ marginTop: 16, width: "100%" }}
        >
          ✕
        </button>
      </div>
    </div>
  );
}
