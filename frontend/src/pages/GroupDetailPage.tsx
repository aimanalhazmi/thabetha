import { Crown, Edit2, Mail, Phone, Trash2, UserPlus, Users, X } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { Input, Panel } from "../components/Layout";
import { SettlementProposalPanel } from "../components/SettlementProposalPanel";
import { errorCode, groups as groupsApi } from "../lib/api";
import { t, type TranslationKey } from "../lib/i18n";
import type { Debt, GroupDetail, Language } from "../lib/types";

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
};

function translateError(language: Language, err: unknown): string {
  const code = errorCode(err);
  if (code && ERROR_KEY[code]) return t(language, ERROR_KEY[code]);
  return err instanceof Error ? err.message : "Action failed";
}

function getInitials(name: string) {
  return name.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase();
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

  // ── Data fetching — untouched ─────────────────────────────────
  async function load() {
    if (!id) return;
    try {
      const [d, dbts] = await Promise.all([groupsApi.get(id), groupsApi.debts(id).catch(() => [] as Debt[])]);
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
              {isOwner ? tr("groupsOwner") : detail.owner_id}
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
            <Input label={tr("groupsTransferOwnership")} value={transferTarget} onChange={setTransferTarget} />
            <button className="primary-button" disabled={busy} onClick={() => void handleTransfer()}>
              <span>{tr("groupsTransferOwnership")}</span>
            </button>
          </div>
        )}
      </Panel>

      {/* Members */}
      <Panel title={tr("groupsMembers")}>
        <div className="groups-members-list">
          {detail.members.map((m) => (
            <div key={m.id} className="group-member-card">
              <div className="group-member-card__avatar">
                {getInitials(m.name ?? m.user_id)}
              </div>
              <div className="group-member-card__info">
                <strong>{m.name ?? m.user_id}</strong>
                {m.user_id === detail.owner_id && (
                  <span className="group-member-card__owner">
                    <Crown size={11} /> {tr("groupsOwner")}
                  </span>
                )}
              </div>
              {typeof m.commitment_score === "number" && (
                <span className="dash-count-badge">{m.commitment_score}</span>
              )}
            </div>
          ))}
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
                      <div className="group-invite-card__icon">{getInitials(p.name ?? p.user_id)}</div>
                      <span className="group-invite-card__name">{p.name ?? p.user_id}</span>
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

      {/* Group debts */}
      <Panel title={tr("groupsDebts")}>
        {debts.length === 0
          ? <p className="empty">{tr("noData")}</p>
          : (
            <div className="debt-stack">
              {debts.map((d) => (
                <div key={d.id} className={`debt-card debt-card--${d.status}`} style={{ padding: '12px 14px' }}>
                  <div className="debt-card__header">
                    <div className="debt-card__avatar">{getInitials(d.debtor_name)}</div>
                    <div className="debt-card__info">
                      <strong className="debt-card__name">{d.debtor_name}</strong>
                      <span className="debt-card__desc">{d.description}</span>
                    </div>
                    <div className="debt-card__right">
                      <span className="debt-card__amount">{d.amount} {d.currency}</span>
                      <span className={`status-badge ${d.status}`}>{d.status}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )
        }
      </Panel>

      <SettlementProposalPanel
        groupId={id}
        language={language}
        hasSettleableDebts={debts.some((d) => d.status === "active" || d.status === "overdue")}
      />
    </section>
  );
}
