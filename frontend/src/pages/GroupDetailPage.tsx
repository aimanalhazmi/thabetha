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

  useEffect(() => {
    void load();
  }, [id]);

  if (!id) return null;
  if (!detail) {
    return <section className="split"><Panel title={tr("groups")}>{message || tr("noData")}</Panel></section>;
  }

  const isOwner = user?.id === detail.owner_id;

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
      <Panel title={`${detail.name}`}>
        {message && <div className="message">{message}</div>}
        <p className="muted">
          <Crown size={14} /> {tr("groupsOwner")}: {isOwner ? "—" : detail.owner_id}
          {" · "}
          {detail.member_count} {tr("groupsMembers")}
        </p>
        {!isOwner && (
          <button className="ghost-button" disabled={busy} onClick={() => void handleLeave()}>
            <X size={14} /> <span>{tr("groupsLeave")}</span>
          </button>
        )}
        {isOwner && (
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            <button className="ghost-button" disabled={busy} onClick={() => { setShowRename((v) => !v); setShowTransfer(false); }}>
              <Edit2 size={14} /> <span>{tr("groupsRename")}</span>
            </button>
            <button className="ghost-button" disabled={busy} onClick={() => { setShowTransfer((v) => !v); setShowRename(false); }}>
              <Crown size={14} /> <span>{tr("groupsTransferOwnership")}</span>
            </button>
            <button className="ghost-button" disabled={busy} onClick={() => void handleDelete()}>
              <Trash2 size={14} /> <span>{tr("groupsDelete")}</span>
            </button>
          </div>
        )}
        {isOwner && showRename && (
          <div style={{ marginTop: 8, display: "flex", gap: 6 }}>
            <Input label={tr("groupsRename")} value={renameValue} onChange={setRenameValue} />
            <button className="primary-button" disabled={busy} onClick={() => void handleRename()}>
              <span>{tr("groupsRename")}</span>
            </button>
          </div>
        )}
        {isOwner && showTransfer && (
          <div style={{ marginTop: 8, display: "flex", gap: 6 }}>
            <Input label={tr("groupsTransferOwnership")} value={transferTarget} onChange={setTransferTarget} />
            <button className="primary-button" disabled={busy} onClick={() => void handleTransfer()}>
              <span>{tr("groupsTransferOwnership")}</span>
            </button>
          </div>
        )}
      </Panel>

      <Panel title={tr("groupsMembers")}>
        <ul className="simple-list">
          {detail.members.map((m) => (
            <li key={m.id} style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
              <span>
                <Users size={14} /> {m.name ?? m.user_id}
                {m.user_id === detail.owner_id && <span className="muted"> · {tr("groupsOwner")}</span>}
              </span>
              {typeof m.commitment_score === "number" && (
                <span className="muted">
                  {tr("commitmentIndicator")}: {m.commitment_score}
                </span>
              )}
            </li>
          ))}
        </ul>
      </Panel>

      {isOwner && (
        <Panel title={tr("groupsInvite")}>
          <div style={{ display: "flex", gap: 6, marginBottom: 8 }}>
            <button
              className={inviteMode === "email" ? "primary-button" : "ghost-button"}
              onClick={() => setInviteMode("email")}
              type="button"
            >
              <Mail size={14} /> Email
            </button>
            <button
              className={inviteMode === "phone" ? "primary-button" : "ghost-button"}
              onClick={() => setInviteMode("phone")}
              type="button"
            >
              <Phone size={14} /> Phone
            </button>
          </div>
          <Input label={tr("groupsInviteByEmailOrPhone")} value={inviteValue} onChange={setInviteValue} />
          <button className="primary-button" disabled={busy} onClick={() => void handleInvite()}>
            <UserPlus size={18} /> <span>{tr("groupsInvite")}</span>
          </button>

          {detail.pending_invites && detail.pending_invites.length > 0 && (
            <>
              <h3 style={{ marginTop: 16 }}>{tr("groupsPendingInvites")}</h3>
              <ul className="simple-list">
                {detail.pending_invites.map((p) => (
                  <li key={p.id} style={{ display: "flex", justifyContent: "space-between" }}>
                    <span>{p.name ?? p.user_id}</span>
                    <button className="ghost-button" disabled={busy} onClick={() => void handleRevoke(p.user_id)}>
                      <X size={12} /> <span>{tr("groupsRevokeInvite")}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </>
          )}
        </Panel>
      )}

      <Panel title={tr("groupsDebts")}>
        {debts.length === 0 && <p className="empty">{tr("noData")}</p>}
        <ul className="simple-list">
          {debts.map((d) => (
            <li key={d.id}>
              {d.debtor_name} · {d.amount} {d.currency} · {d.status}
            </li>
          ))}
        </ul>
      </Panel>

      <SettlementProposalPanel
        groupId={id}
        language={language}
        hasSettleableDebts={debts.some((d) => d.status === "active" || d.status === "overdue")}
      />
    </section>
  );
}
