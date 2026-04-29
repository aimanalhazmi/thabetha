import { useEffect, useState } from "react";
import { useAuth } from "../contexts/AuthContext";
import { Panel } from "./Layout";
import { SettlementReviewModal } from "./SettlementReviewModal";
import { errorCode, settlements } from "../lib/api";
import { t, type TranslationKey } from "../lib/i18n";
import type { Language, SettlementProposal } from "../lib/types";

interface Props {
  groupId: string;
  language: Language;
  /** True when the group has at least one active/overdue debt. */
  hasSettleableDebts: boolean;
}

const SETTLEMENT_ERROR_KEY: Record<string, TranslationKey> = {
  OpenProposalExists: "errorOpenProposalExists",
  MixedCurrency: "errorMixedCurrency",
  NothingToSettle: "errorNothingToSettle",
};

function expiryCountdown(expiresAt: string): string {
  const diff = new Date(expiresAt).getTime() - Date.now();
  if (diff <= 0) return "0h";
  const hours = Math.floor(diff / 3_600_000);
  const days = Math.floor(hours / 24);
  if (days > 0) return `${days}d ${hours % 24}h`;
  return `${hours}h`;
}

export function SettlementProposalPanel({ groupId, language, hasSettleableDebts }: Props) {
  const tr = (key: TranslationKey) => t(language, key);
  const { user } = useAuth();
  const [proposal, setProposal] = useState<SettlementProposal | null>(null);
  const [failedProposal, setFailedProposal] = useState<SettlementProposal | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    try {
      const [open, failed] = await Promise.all([
        settlements.list(groupId, "open"),
        settlements.list(groupId, "settlement_failed"),
      ]);
      setProposal(open.length > 0 ? open[0] : null);
      setFailedProposal(failed.length > 0 ? failed[0] : null);
    } catch {
      // Non-fatal — just leave proposal as null.
    }
  }

  useEffect(() => {
    void load();
  }, [groupId]);

  async function handleCreate() {
    setBusy(true);
    setError("");
    try {
      const created = await settlements.create(groupId);
      setProposal(created);
      setFailedProposal(null);
    } catch (err) {
      const code = errorCode(err);
      const key = code ? SETTLEMENT_ERROR_KEY[code] : undefined;
      setError(key ? tr(key) : (err instanceof Error ? err.message : tr("errorGeneric")));
    } finally {
      setBusy(false);
    }
  }

  const currentUserId = user?.id;

  return (
    <Panel title={tr("settlementProposedTitle")}>
      {error && <div className="message">{error}</div>}

      {/* settlement_failed banner — T034 */}
      {!proposal && failedProposal && (
        <div className="message" style={{ marginBottom: 12 }}>
          <span>{tr("settlementStatusFailed")}</span>
          <button
            className="ghost-button"
            disabled={busy}
            onClick={() => void handleCreate()}
            style={{ marginLeft: 12 }}
          >
            {tr("settlementCtaTryAgain")}
          </button>
        </div>
      )}

      {!proposal && (
        <>
          <button
            className="primary-button"
            disabled={busy || !hasSettleableDebts}
            onClick={() => void handleCreate()}
          >
            {tr("settlementCtaSettleGroup")}
          </button>
          {!hasSettleableDebts && (
            <p className="muted" style={{ marginTop: 6 }}>
              {tr("settlementCtaNothingToSettle")}
            </p>
          )}
        </>
      )}

      {proposal && (
        <div>
          <p className="muted">
            {tr("settlementStatusOpen")} · {tr("settlementExpiresIn")}: {expiryCountdown(proposal.expires_at)}
          </p>

          {proposal.transfers.length === 0 ? (
            <p className="muted">{tr("settlementStatusSettled")}</p>
          ) : (
            <>
              <p style={{ fontWeight: 600 }}>{tr("settlementTransfersHeading")}</p>
              <ul className="simple-list">
                {proposal.transfers.map((tf, i) => {
                  const myRole =
                    tf.payer_id === currentUserId
                      ? tr("settlementRolePayer")
                      : tf.receiver_id === currentUserId
                      ? tr("settlementRoleReceiver")
                      : tr("settlementRoleObserver");
                  return (
                    <li key={i} style={{ display: "flex", justifyContent: "space-between" }}>
                      <span>
                        {tf.payer_id} → {tf.receiver_id}: {tf.amount} {proposal.currency}
                      </span>
                      <span className="muted">{myRole}</span>
                    </li>
                  );
                })}
              </ul>
            </>
          )}

          {/* Confirmation roster for required parties */}
          {proposal.confirmations.length > 0 && (
            <>
              <p style={{ fontWeight: 600, marginTop: 12 }}>{tr("settlementConfirm")}</p>
              <ul className="simple-list">
                {proposal.confirmations.map((c) => (
                  <li key={c.user_id} style={{ display: "flex", justifyContent: "space-between" }}>
                    <span>{c.user_id}</span>
                    <span className="muted">{c.status}</span>
                  </li>
                ))}
              </ul>
            </>
          )}

          {/* Review link — T033 */}
          <button
            className="ghost-button"
            onClick={() => setShowModal(true)}
            style={{ marginTop: 12 }}
          >
            {tr("settlementReviewTitle")} →
          </button>
        </div>
      )}

      {/* Review modal — T033 */}
      {showModal && proposal && (
        <SettlementReviewModal
          groupId={groupId}
          proposal={proposal}
          language={language}
          onClose={() => setShowModal(false)}
          onUpdated={(updated) => {
            setProposal(updated.status === "open" ? updated : null);
            if (updated.status === "settlement_failed") setFailedProposal(updated);
          }}
        />
      )}
    </Panel>
  );
}
