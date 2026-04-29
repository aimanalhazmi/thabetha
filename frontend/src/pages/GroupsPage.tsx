import { Check, Users, X } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Input, Panel } from "../components/Layout";
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

  async function load() {
    try {
      setGroups(await groupsApi.list());
    } catch (err) {
      setMessage(translateError(language, err));
    }
  }

  useEffect(() => {
    void load();
  }, []);

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

  const accepted = groups.filter((g) => g.member_status !== "pending");
  const pending = groups.filter((g) => g.member_status === "pending");

  return (
    <section className="split">
      <Panel title={tr("groupsMyGroups")}>
        {message && <div className="message">{message}</div>}
        <ul className="simple-list">
          {accepted.map((g) => (
            <li key={g.id}>
              <Link to={`/groups/${g.id}`}>
                <Users size={16} /> {g.name}
                <span className="muted"> · {g.member_count ?? 1} {tr("groupsMembers")}</span>
              </Link>
            </li>
          ))}
          {accepted.length === 0 && <p className="empty">{tr("groupsNoGroupsYet")}</p>}
        </ul>
      </Panel>

      <Panel title={tr("groupsCreateGroup")}>
        <Input label={tr("groupName")} value={groupName} onChange={setGroupName} />
        <button className="primary-button" onClick={() => void handleCreate()}>
          <Users size={18} /><span>{tr("groupsCreate")}</span>
        </button>
      </Panel>

      <Panel title={tr("groupsPendingInvitations")}>
        {pending.length === 0 && <p className="empty">{tr("groupsNoPendingInvitations")}</p>}
        <ul className="simple-list">
          {pending.map((g) => (
            <li key={g.id} style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
              <span>{g.name}</span>
              <span style={{ display: "flex", gap: 6 }}>
                <button
                  className="ghost-button"
                  disabled={busy === g.id}
                  onClick={() => void handleInvite("accept", g.id)}
                >
                  <Check size={14} /> <span>{tr("groupsAccept")}</span>
                </button>
                <button
                  className="ghost-button"
                  disabled={busy === g.id}
                  onClick={() => void handleInvite("decline", g.id)}
                >
                  <X size={14} /> <span>{tr("groupsDecline")}</span>
                </button>
              </span>
            </li>
          ))}
        </ul>
      </Panel>
    </section>
  );
}
