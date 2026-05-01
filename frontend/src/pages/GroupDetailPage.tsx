import { Check, Crown, Edit2, Mail, Phone, Trash2, UserPlus, Users, X } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { Input, Panel } from "../components/Layout";
import { SettlementProposalPanel } from "../components/SettlementProposalPanel";
import { errorCode, groups as groupsApi } from "../lib/api";
import { formatCurrency, t, type TranslationKey } from "../lib/i18n";
import type { Debt, DebtStatus, GroupDetail, Language } from "../lib/types";

interface Props { language: Language }

const ERROR_KEY: Record<string, TranslationKey> = {
  NotPlatformUser: "errorNotPlatformUser",
  AlreadyMember: "errorAlreadyMember",
  InviteToSelf: "errorInviteToSelf",
  GroupFull: "errorGroupFull",
  OwnerCannotLeave: "errorOwnerCannotLeave",
  NotAGroupMember: "errorNotAGroupMember",
  NotGroupOwner: "errorNotGroupOwner",
  GroupHasDebts: "errorGroupHasDebts",
  GroupTagLocked: "errorGroupTagLocked",
  NotInSharedGroup: "errorNotInSharedGroup",
  SameOwner: "errorSameOwner",
  NoPendingInvite: "errorNoPendingInvite",
  IdentifierAmbiguous: "errorIdentifierAmbiguous",
  CreditorRoleRequired: "errorCreditorRoleRequired",
  OpenProposalExists: "errorOpenProposalExists",
  MixedCurrency: "errorMixedCurrency",
  NothingToSettle: "errorNothingToSettle",
  NotARequiredParty: "errorNotARequiredParty",
  AlreadyResponded: "errorAlreadyResponded",
  ProposalNotOpen: "errorProposalNotOpen",
  StaleSnapshot: "errorStaleSnapshot",
  LeaveBlockedByOpenProposal: "errorLeaveBlockedByOpenProposal",
};

function translateError(language: Language, err: unknown): string {
  const code = errorCode(err);
  if (code && ERROR_KEY[code]) return t(language, ERROR_KEY[code]);
  return err instanceof Error ? err.message : "Action failed";
}

function getInitials(name: string) {
  return name.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase();
}

function statusLabel(tr: (key: TranslationKey) => string, statusValue: DebtStatus): string {
  if (statusValue === "pending_confirmation") return tr("pendingConfirmation");
  if (statusValue === "active") return tr("active");
  if (statusValue === "edit_requested") return tr("editRequested");
  if (statusValue === "overdue") return tr("overdue");
  if (statusValue === "payment_pending_confirmation") return tr("paymentPendingConfirmation");
  if (statusValue === "paid") return tr("paid");
  return tr("cancelled");
}

const overviewStatusRows: Array<[DebtStatus, TranslationKey]> = [
  ["active", "groupsTotalActiveDebt"],
  ["pending_confirmation", "groupsTotalPendingDebt"],
  ["paid", "groupsTotalPaidDebt"],
  ["overdue", "groupsTotalOverdueDebt"],
  ["cancelled", "groupsTotalCancelledDebt"],
];

function overviewStatusTotal(totals: Partial<Record<DebtStatus, string>> | undefined, statusValue: DebtStatus): string {
  if (!totals) return "0";
  if (statusValue !== "pending_confirmation") return totals[statusValue] ?? "0";
  const pending =
    parseFloat(totals.pending_confirmation ?? "0") +
    parseFloat(totals.edit_requested ?? "0") +
    parseFloat(totals.payment_pending_confirmation ?? "0");
  return String(pending);
}

export function GroupDetailPage({ language }: Props) {
  const tr = (key: TranslationKey) => t(language, key);
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [detail, setDetail] = useState<GroupDetail | null>(null);
  const [debts, setDebts] = useState<Debt[]>([]);
  const [message, setMessage] = useState("");
  const [inviteMode, setInviteMode] = useState<"email" | "phone">("email");
  const [inviteValue, setInviteValue] = useState("");
  const [busy, setBusy] = useState(false);
  const [renameValue, setRenameValue] = useState("");
  const [showRename, setShowRename] = useState(false);
  const [transferTarget, setTransferTarget] = useState("");
  const [showTransfer, setShowTransfer] = useState(false);

  // ── Data fetching ────────────────────────────────────────────
  async function load() {
    if (!id) return;
    try {
      const [d, dbts] = await Promise.all([
        groupsApi.get(id),
        groupsApi.debts(id).catch(() => [] as Debt[]),
      ]);
      setDetail(d);
      setDebts(dbts);
    } catch (err) {
      setMessage(translateError(language, err));
    }
  }

  useEffect(() => { void load(); }, [id]);

  if (!id) return null;
  if (!detail) {
    return (
      <section className="split">
        <Panel title={tr("groups")}>
          {message ? <div className="message error">{message}</div> : <div className="dash-loading"><div className="spinner" /></div>}
        </Panel>
      </section>
    );
  }

  const isOwner = user?.id === detail.owner_id;
  const overview = detail.debt_overview;
  const displayDebts = overview?.member_debts.flatMap((m) => m.debts) ?? debts;
  const currency = displayDebts[0]?.currency ?? "SAR";
  const ownerMember = detail.members.find((member) => member.user_id === detail.owner_id);

  // ── Handlers — untouched ──────────────────────────────────────
  async function run(action: () => Promise<unknown>) {
    setBusy(true);
    setMessage("");
    try {
      await action();
      await load();
    } catch (err) {
      setMessage(translateError(language, err));
    } finally {
      setBusy(false);
    }
  }

  async function handleInvite() {
    if (!inviteValue.trim()) return;
    const body = inviteMode === "email" ? { email: inviteValue.trim() } : { phone: inviteValue.trim() };
    await run(async () => {
      await groupsApi.invite(id!, body);
      setInviteValue("");
    });
  }

  async function handleLeave() {
    await run(async () => {
      await groupsApi.leave(id!);
      navigate("/groups");
    });
  }

  async function handleDelete() {
    await run(async () => {
      await groupsApi.delete(id!);
      navigate("/groups");
    });
  }

  async function handleRevoke(userId: string) {
    await run(() => groupsApi.revokeInvite(id!, userId));
  }

  async function handleRename() {
    if (!renameValue.trim()) return;
    await run(async () => {
      await groupsApi.rename(id!, renameValue.trim());
      setRenameValue("");
      setShowRename(false);
    });
  }

  async function handleTransfer() {
    if (!transferTarget.trim()) return;
    await run(async () => {
      await groupsApi.transferOwnership(id!, transferTarget.trim());
      setTransferTarget("");
      setShowTransfer(false);
    });
  }

  async function handleBulkConfirm() {
    await run(async () => {
      const confirmed = await groupsApi.bulkConfirmPayments(id!);
      const text = tr("groupsBulkConfirmedCount").replace("{count}", String(confirmed.length));
      setMessage(text);
    });
  }

  // Is current user the creditor of any debt in this group awaiting payment confirmation?
  const hasPendingPayments = debts.some(
    (d) => d.creditor_id === user?.id && d.status === "payment_pending_confirmation",
  );

  // Are there any settleable (active/overdue) debts in this group?
  const hasSettleableDebts = debts.some(
    (d) => d.status === "active" || d.status === "overdue",
  );

  return (
    <section className="split">
      {/* Group info + owner actions */}
      <Panel title={detail.name}>
        {message && <div className="message">{message}</div>}

        {/* Meta row */}
        <div className="group-detail-meta">
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <Crown size={14} color="var(--warning)" />
            <span style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
              {isOwner ? tr("groupsOwner") : ownerMember?.name ?? ownerMember?.email ?? ownerMember?.phone ?? tr("groupsOwner")}
            </span>
          </div>
          <span className="dash-count-badge">
            <Users size={11} style={{ marginInlineEnd: 3 }} />
            {detail.member_count} {tr("groupsMembers")}
          </span>
        </div>

        {/* Member actions */}
        {!isOwner && (
          <button className="ghost-button" disabled={busy} onClick={() => void handleLeave()}>
            <X size={14} /><span>{tr("groupsLeave")}</span>
          </button>
        )}

        {isOwner && (
          <div className="group-action-row">
            <button
              className="ghost-button"
              disabled={busy}
              onClick={() => { setShowRename((v) => !v); setShowTransfer(false); }}
            >
              <Edit2 size={13} /><span>{tr("groupsRename")}</span>
            </button>
            <button
              className="ghost-button"
              disabled={busy}
              onClick={() => { setShowTransfer((v) => !v); setShowRename(false); }}
            >
              <Crown size={13} /><span>{tr("groupsTransferOwnership")}</span>
            </button>
            <button
              className="ghost-button"
              style={{ color: 'var(--danger)' }}
              disabled={busy}
              onClick={() => void handleDelete()}
            >
              <Trash2 size={13} /><span>{tr("groupsDelete")}</span>
            </button>
          </div>
        )}

        {isOwner && showRename && (
          <div className="create-debt-section" style={{ marginTop: 4 }}>
            <div className="create-debt-section__label">{tr("groupsRename")}</div>
            <Input label={tr("groupName")} value={renameValue} onChange={setRenameValue} />
            <button className="primary-button" disabled={busy} onClick={() => void handleRename()}>
              <span>{tr("groupsRename")}</span>
            </button>
          </div>
        )}

        {isOwner && showTransfer && (
          <div className="create-debt-section" style={{ marginTop: 4 }}>
            <div className="create-debt-section__label">{tr("groupsTransferOwnership")}</div>
            <label className="field">
              <span>{tr("groupsTransferOwnership")}</span>
              <select value={transferTarget} onChange={(event) => setTransferTarget(event.target.value)}>
                <option value="">{tr("noData")}</option>
                {detail.members
                  .filter((member) => member.user_id !== detail.owner_id)
                  .map((member) => (
                    <option key={member.user_id} value={member.user_id}>
                      {member.name ?? member.email ?? member.phone ?? tr("noData")}
                    </option>
                  ))}
              </select>
            </label>
            <button className="primary-button" disabled={busy} onClick={() => void handleTransfer()}>
              <span>{tr("groupsTransferOwnership")}</span>
            </button>
          </div>
        )}
      </Panel>

      {/* Members */}
      <Panel title={tr("groupsMembers")}>
        <div className="groups-members-list">
          {detail.members.filter(m => m.user_id !== detail.owner_id).length === 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8, padding: '20px 0', color: 'var(--text-muted)', fontSize: '0.88rem', textAlign: 'center' }}>
              <Users size={28} strokeWidth={1.4} />
              <span>{tr("groupsNoMembersYet")}</span>
            </div>
          ) : (
            detail.members.filter(m => m.user_id !== detail.owner_id).map((m) => (
              <div key={m.id} className="group-member-card">
                <div className="group-member-card__avatar">
                  {getInitials(m.name ?? m.email ?? m.phone ?? "?")}
                </div>
                <div className="group-member-card__info">
                  <strong>{m.name ?? m.email ?? m.phone ?? tr("noData")}</strong>
                  {(m.email || m.phone) && <span>{m.email ?? m.phone}</span>}
                </div>
                {typeof m.commitment_score === "number" && (
                  <span className="dash-count-badge">{m.commitment_score}</span>
                )}
              </div>
            ))
          )}
        </div>
      </Panel>

      {/* Invite panel (owner only) */}
      {isOwner && (
        <Panel title={tr("groupsInvite")}>
          <div className="filter-tabs" style={{ marginBottom: 8 }}>
            <button
              className={`filter-tab${inviteMode === "email" ? " active" : ""}`}
              onClick={() => setInviteMode("email")}
              type="button"
            >
              <Mail size={13} /><span>{tr("email")}</span>
            </button>
            <button
              className={`filter-tab${inviteMode === "phone" ? " active" : ""}`}
              onClick={() => setInviteMode("phone")}
              type="button"
            >
              <Phone size={13} /><span>{tr("phone")}</span>
            </button>
          </div>
          <Input label={tr("groupsInviteByEmailOrPhone")} value={inviteValue} onChange={setInviteValue} />
          <button
            className="primary-button"
            style={{ width: '100%', justifyContent: 'center' }}
            disabled={busy}
            onClick={() => void handleInvite()}
          >
            <UserPlus size={16} /><span>{tr("groupsInvite")}</span>
          </button>

          {detail.pending_invites && detail.pending_invites.length > 0 && (
            <div style={{ marginTop: 12 }}>
              <div className="create-debt-section__label" style={{ marginBottom: 8 }}>
                {tr("groupsPendingInvites")}
              </div>
              <div className="groups-invites">
                {detail.pending_invites.map((p) => (
                  <div key={p.id} className="group-invite-card">
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <div className="group-invite-card__icon">{getInitials(p.name ?? p.email ?? p.phone ?? "?")}</div>
                      <span className="group-invite-card__name">{p.name ?? p.email ?? p.phone ?? tr("noData")}</span>
                    </div>
                    <button
                      className="ghost-button"
                      style={{ padding: '5px 10px', fontSize: '0.78rem', color: 'var(--danger)' }}
                      disabled={busy}
                      onClick={() => void handleRevoke(p.user_id)}
                    >
                      <X size={13} /><span>{tr("groupsRevokeInvite")}</span>
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </Panel>
      )}

      {/* Group overview */}
      <Panel title={tr("groupsTotalDebt")}>
        <div className="stats-grid compact">
          <div className="stat-card">
            <span>{tr("groupsTotalAmountOwed")}</span>
            <strong>{formatCurrency(overview?.total_current_owed ?? "0", language, currency)}</strong>
          </div>
        </div>
        <div className="create-debt-section__label" style={{ marginTop: 12 }}>
          {tr("groupsDebtStatusOverview")}
        </div>
        <div className="stats-grid compact">
          {overviewStatusRows.map(([statusValue, labelKey]) => (
            <div key={statusValue} className="stat-card">
              <span>{tr(labelKey)}</span>
              <strong>{formatCurrency(overviewStatusTotal(overview?.status_totals, statusValue), language, currency)}</strong>
            </div>
          ))}
        </div>
      </Panel>

      <Panel title={tr("groupsMembersDebts")}>
        {!overview || overview.member_debts.length === 0 ? (
          <p className="empty">{tr("noData")}</p>
        ) : (
          <div className="debt-stack">
            {overview.member_debts
              .filter((m) => m.user_id !== detail.owner_id)
              .map((member) => (
                <div key={member.user_id} className="group-member-card">
                  <div className="group-member-card__avatar">
                    {getInitials(member.name ?? member.email ?? member.phone ?? "?")}
                  </div>
                  <div className="group-member-card__info">
                    <strong>{member.name ?? member.email ?? member.phone ?? tr("noData")}</strong>
                    <span>{formatCurrency(member.total_owed, language, currency)}</span>
                  </div>
                  <span className="dash-count-badge">{member.debts.length}</span>
                </div>
              ))}
          </div>
        )}
      </Panel>

      {/* Group debts */}
      <Panel title={tr("groupsDebts")}>
        {hasPendingPayments && (
          <button
            className="primary-button"
            style={{ width: "100%", justifyContent: "center", marginBottom: 10 }}
            disabled={busy}
            onClick={() => void handleBulkConfirm()}
          >
            <Check size={16} /><span>{tr("groupsBulkConfirmPayments")}</span>
          </button>
        )}
        {displayDebts.length === 0
          ? <p className="empty">{tr("noData")}</p>
          : (
            <div className="debt-stack">
              {displayDebts.map((d) => (
                <div key={d.id} className={`debt-card debt-card--${d.status}`} style={{ padding: '12px 14px' }}>
                  <div className="debt-card__header">
                    <div className="debt-card__avatar">{getInitials(d.debtor_name)}</div>
                    <div className="debt-card__info">
                      <strong className="debt-card__name">{d.debtor_name}</strong>
                      <span className="debt-card__desc">{d.description}</span>
                    </div>
                    <div className="debt-card__right">
                      <span className="debt-card__amount">{formatCurrency(d.amount, language, d.currency)}</span>
                      <span className={`status-badge ${d.status}`}>{statusLabel(tr, d.status)}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )
        }
      </Panel>

      {/* Settlement proposal */}
      <SettlementProposalPanel
        groupId={id}
        language={language}
        hasSettleableDebts={hasSettleableDebts}
      />

    </section>
  );
}
