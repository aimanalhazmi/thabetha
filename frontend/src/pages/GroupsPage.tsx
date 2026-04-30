import { Check, ChevronRight, Plus, Users, X } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Input } from "../components/Layout";
import { errorCode, groups as groupsApi } from "../lib/api";
import { t, type TranslationKey } from "../lib/i18n";
import type { Group, Language } from "../lib/types";

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

export function GroupsPage({ language }: Props) {
  const tr = (key: TranslationKey) => t(language, key);
  const [groups, setGroups] = useState<Group[]>([]);
  const [groupName, setGroupName] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState<string | null>(null);

  // ── Data fetching — untouched ─────────────────────────────────
  async function load() {
    try {
      setGroups(await groupsApi.list());
    } catch (err) {
      setMessage(translateError(language, err));
    }
  }

  useEffect(() => { void load(); }, []);

  // ── Handlers — untouched ──────────────────────────────────────
  async function handleCreate() {
    if (!groupName.trim()) return;
    try {
      await groupsApi.create({ name: groupName.trim() });
      setGroupName("");
      setMessage("");
      await load();
    } catch (err) {
      setMessage(translateError(language, err));
    }
  }

  async function handleInvite(action: "accept" | "decline", id: string) {
    setBusy(id);
    setMessage("");
    try {
      if (action === "accept") await groupsApi.accept(id);
      else await groupsApi.decline(id);
      await load();
    } catch (err) {
      setMessage(translateError(language, err));
    } finally {
      setBusy(null);
    }
  }

  const accepted = groups.filter((g) => g.member_status === "accepted" || g.member_status == null);
  const pending = groups.filter((g) => g.member_status === "pending");

  return (
    <section className="groups-page">
      {message && <div className="message" style={{ gridColumn: '1 / -1' }}>{message}</div>}

      {/* My groups — main column */}
      <div className="groups-main">
        <div className="debts-page__header">
          <h2 className="debts-page__title">
            {tr("groupsMyGroups")}
            <span className="dash-count-badge">{accepted.length}</span>
          </h2>
        </div>

        <div className="groups-list">
          {accepted.map((g) => (
            <Link key={g.id} to={`/groups/${g.id}`} className="group-card">
              <div className="group-card__icon">
                <Users size={18} />
              </div>
              <div className="group-card__info">
                <strong className="group-card__name">{g.name}</strong>
                <span className="group-card__meta">{g.member_count ?? 1} {tr("groupsMembers")}</span>
              </div>
              <ChevronRight size={16} color="var(--text-muted)" className="group-card__arrow" />
            </Link>
          ))}
          {accepted.length === 0 && <p className="empty">{tr("groupsNoGroupsYet")}</p>}
        </div>
      </div>

      {/* Sidebar — create + pending */}
      <div className="groups-sidebar">
        {/* Create group */}
        <div className="create-debt-section">
          <div className="create-debt-section__label">{tr("groupsCreateGroup")}</div>
          <Input label={tr("groupName")} value={groupName} onChange={setGroupName} />
          <button
            className="primary-button"
            style={{ width: '100%', justifyContent: 'center' }}
            onClick={() => void handleCreate()}
          >
            <Plus size={16} /><span>{tr("groupsCreate")}</span>
          </button>
        </div>

        {/* Pending invitations */}
        {pending.length > 0 && (
          <div className="create-debt-section">
            <div className="create-debt-section__label" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              {tr("groupsPendingInvitations")}
              <span className="dash-unread-badge">{pending.length}</span>
            </div>
            <div className="groups-invites">
              {pending.map((g) => (
                <div key={g.id} className="group-invite-card">
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <div className="group-invite-card__icon"><Users size={14} /></div>
                    <span className="group-invite-card__name">{g.name}</span>
                  </div>
                  <div style={{ display: 'flex', gap: 6 }}>
                    <button
                      className="primary-button"
                      style={{ padding: '5px 10px', fontSize: '0.78rem' }}
                      disabled={busy === g.id}
                      onClick={() => void handleInvite("accept", g.id)}
                    >
                      <Check size={13} /><span>{tr("groupsAccept")}</span>
                    </button>
                    <button
                      className="ghost-button"
                      style={{ padding: '5px 10px', fontSize: '0.78rem' }}
                      disabled={busy === g.id}
                      onClick={() => void handleInvite("decline", g.id)}
                    >
                      <X size={13} /><span>{tr("groupsDecline")}</span>
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
