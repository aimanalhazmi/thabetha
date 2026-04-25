import { Check, Users, WalletCards } from "lucide-react";
import { useEffect, useState } from "react";
import { Input, Panel } from "../components/Layout";
import { apiRequest } from "../lib/api";
import { t } from "../lib/i18n";
import type { Group, Language } from "../lib/types";

interface Props { language: Language }

export function GroupsPage({ language }: Props) {
  const tr = (key: Parameters<typeof t>[1]) => t(language, key);
  const [groups, setGroups] = useState<Group[]>([]);
  const [message, setMessage] = useState("");
  const [groupName, setGroupName] = useState("");
  const [invite, setInvite] = useState({ groupId: "", userId: "" });
  const [settlement, setSettlement] = useState({ groupId: "", debtorId: "", amount: "10.00", currency: "SAR", note: "" });

  async function load() {
    try { setGroups(await apiRequest<Group[]>("/groups")); } catch { /* ignored */ }
  }

  useEffect(() => { void load(); }, []);

  async function runAction(action: () => Promise<unknown>, success: string) {
    try { await action(); setMessage(success); await load(); }
    catch (err) { setMessage(err instanceof Error ? err.message : "Action failed"); }
  }

  return (
    <section className="split">
      <Panel title={tr("groups")}>
        {message && <div className="message">{message}</div>}
        <Input label={tr("groupName")} value={groupName} onChange={setGroupName} />
        <button className="primary-button" onClick={() => void runAction(() => apiRequest("/groups", { method: "POST", body: JSON.stringify({ name: groupName }) }), "Group created")}>
          <Users size={18} /><span>{tr("create")}</span>
        </button>
        <ul className="simple-list">
          {groups.map((g) => <li key={g.id}>{g.name} · {g.id}</li>)}
          {groups.length === 0 && <p className="empty">{tr("noData")}</p>}
        </ul>
      </Panel>
      <Panel title={tr("inviteUser")}>
        <Input label="Group ID" value={invite.groupId} onChange={(v) => setInvite({ ...invite, groupId: v })} />
        <Input label={tr("inviteUser")} value={invite.userId} onChange={(v) => setInvite({ ...invite, userId: v })} />
        <button className="primary-button" onClick={() => void runAction(() => apiRequest(`/groups/${invite.groupId}/invite`, { method: "POST", body: JSON.stringify({ user_id: invite.userId }) }), "Invitation sent")}>
          <Users size={18} /><span>{tr("create")}</span>
        </button>
        <button className="ghost-button" onClick={() => void runAction(() => apiRequest(`/groups/${invite.groupId}/accept`, { method: "POST" }), "Invitation accepted")}>
          <Check size={18} /><span>{tr("acceptInvite")}</span>
        </button>
        <hr />
        <Input label="Settlement Group ID" value={settlement.groupId} onChange={(v) => setSettlement({ ...settlement, groupId: v })} />
        <Input label={tr("debtorId")} value={settlement.debtorId} onChange={(v) => setSettlement({ ...settlement, debtorId: v })} />
        <Input label={tr("amount")} value={settlement.amount} onChange={(v) => setSettlement({ ...settlement, amount: v })} />
        <button className="ghost-button" onClick={() => void runAction(() => apiRequest(`/groups/${settlement.groupId}/settlements`, { method: "POST", body: JSON.stringify({ debtor_id: settlement.debtorId, amount: settlement.amount, currency: settlement.currency, note: settlement.note }) }), "Settlement recorded")}>
          <WalletCards size={18} /><span>{tr("save")}</span>
        </button>
      </Panel>
    </section>
  );
}
