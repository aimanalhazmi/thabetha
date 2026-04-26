import { Check, Users, WalletCards } from "lucide-react";
import { useEffect, useState } from "react";
import { Input, Panel } from "../components/Layout";
import { useToast } from "../contexts/ToastContext";
import { apiRequest } from "../lib/api";
import { t } from "../lib/i18n";
import type { Group, Language } from "../lib/types";

interface Props { language: Language }

export function GroupsPage({ language }: Props) {
  const tr = (key: Parameters<typeof t>[1]) => t(language, key);
  const { showToast } = useToast();
  const [groups, setGroups] = useState<Group[]>([]);
  const [groupName, setGroupName] = useState("");
  const [inviteGroupId, setInviteGroupId] = useState("");
  const [inviteUserId, setInviteUserId] = useState("");
  const [acceptGroupId, setAcceptGroupId] = useState("");
  const [settlementGroupId, setSettlementGroupId] = useState("");
  const [settlement, setSettlement] = useState({ debtorId: "", amount: "10.00", currency: "SAR", note: "" });
  const [loading, setLoading] = useState<Record<string, boolean>>({});

  async function load() {
    try { setGroups(await apiRequest<Group[]>("/groups")); } catch { /* ignored */ }
  }

  useEffect(() => { void load(); }, []);

  async function runAction(key: string, action: () => Promise<unknown>, success: string) {
    setLoading(prev => ({ ...prev, [key]: true }));
    try {
      await action();
      showToast(success, "success");
      await load();
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Action failed", "error");
    } finally {
      setLoading(prev => ({ ...prev, [key]: false }));
    }
  }

  return (
    <section className="split">
      <Panel title={tr("groups")}>
        {/* Create group */}
        <Input label={tr("groupName")} value={groupName} onChange={setGroupName} />
        <button
          className="primary-button"
          disabled={!groupName.trim() || loading["create"]}
          onClick={() => void runAction(
            "create",
            () => apiRequest("/groups", { method: "POST", body: JSON.stringify({ name: groupName }) }).then(() => setGroupName("")),
            language === "ar" ? "تم إنشاء المجموعة" : "Group created",
          )}
        >
          <Users size={18} />
          <span>{loading["create"] ? "..." : tr("create")}</span>
        </button>

        {/* Group list */}
        {groups.length > 0 ? (
          <ul className="simple-list" style={{ marginTop: "12px" }}>
            {groups.map((g) => (
              <li key={g.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "8px" }}>
                <strong>{g.name}</strong>
                <code
                  style={{ fontSize: "0.7rem", color: "var(--text-muted)", cursor: "pointer" }}
                  title={language === "ar" ? "انقر لنسخ المعرّف" : "Click to copy ID"}
                  onClick={() => void navigator.clipboard.writeText(g.id).then(() => showToast(language === "ar" ? "تم نسخ المعرّف" : "ID copied", "info"))}
                >
                  {g.id.slice(0, 8)}…
                </code>
              </li>
            ))}
          </ul>
        ) : (
          <p className="empty">{tr("noData")}</p>
        )}
      </Panel>

      <Panel title={language === "ar" ? "إدارة الأعضاء والتسويات" : "Members & Settlements"}>
        {/* Invite */}
        <strong style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
          {tr("inviteUser")}
        </strong>
        <label className="field">
          <span>{language === "ar" ? "المجموعة" : "Group"}</span>
          <select value={inviteGroupId} onChange={(e) => setInviteGroupId(e.target.value)}>
            <option value="">{language === "ar" ? "اختر مجموعة..." : "Select a group..."}</option>
            {groups.map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}
          </select>
        </label>
        <Input
          label={tr("inviteUser")}
          value={inviteUserId}
          onChange={setInviteUserId}
          placeholder={language === "ar" ? "معرّف المستخدم" : "User ID"}
        />
        <button
          className="primary-button"
          disabled={!inviteGroupId || !inviteUserId.trim() || loading["invite"]}
          onClick={() => void runAction(
            "invite",
            () => apiRequest(`/groups/${inviteGroupId}/invite`, { method: "POST", body: JSON.stringify({ user_id: inviteUserId }) }).then(() => setInviteUserId("")),
            language === "ar" ? "تم إرسال الدعوة" : "Invitation sent",
          )}
        >
          <Users size={18} />
          <span>{loading["invite"] ? "..." : tr("inviteUser")}</span>
        </button>

        <hr style={{ margin: "14px 0", borderColor: "var(--border-light)" }} />

        {/* Accept invite */}
        <strong style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
          {tr("acceptInvite")}
        </strong>
        <Input
          label={language === "ar" ? "معرّف المجموعة المُدعى إليها" : "Group ID you were invited to"}
          value={acceptGroupId}
          onChange={setAcceptGroupId}
          placeholder={language === "ar" ? "الصق معرّف المجموعة هنا" : "Paste group ID here"}
        />
        <button
          className="ghost-button"
          disabled={!acceptGroupId.trim() || loading["accept"]}
          onClick={() => void runAction(
            "accept",
            () => apiRequest(`/groups/${acceptGroupId}/accept`, { method: "POST" }).then(() => setAcceptGroupId("")),
            language === "ar" ? "تم قبول الدعوة" : "Invitation accepted",
          )}
        >
          <Check size={18} />
          <span>{loading["accept"] ? "..." : tr("acceptInvite")}</span>
        </button>

        <hr style={{ margin: "14px 0", borderColor: "var(--border-light)" }} />

        {/* Settlement */}
        <strong style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
          {language === "ar" ? "تسوية ديون المجموعة" : "Group Settlement"}
        </strong>
        <label className="field">
          <span>{language === "ar" ? "المجموعة" : "Group"}</span>
          <select value={settlementGroupId} onChange={(e) => setSettlementGroupId(e.target.value)}>
            <option value="">{language === "ar" ? "اختر مجموعة..." : "Select a group..."}</option>
            {groups.map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}
          </select>
        </label>
        <Input
          label={tr("debtorId")}
          value={settlement.debtorId}
          onChange={(v) => setSettlement({ ...settlement, debtorId: v })}
          placeholder={language === "ar" ? "معرّف المدين" : "Debtor user ID"}
        />
        <Input
          label={tr("amount")}
          value={settlement.amount}
          onChange={(v) => setSettlement({ ...settlement, amount: v })}
        />
        <button
          className="ghost-button"
          disabled={!settlementGroupId || !settlement.debtorId.trim() || loading["settle"]}
          onClick={() => void runAction(
            "settle",
            () => apiRequest(`/groups/${settlementGroupId}/settlements`, {
              method: "POST",
              body: JSON.stringify({ debtor_id: settlement.debtorId, amount: settlement.amount, currency: settlement.currency, note: settlement.note }),
            }),
            language === "ar" ? "تم تسجيل التسوية" : "Settlement recorded",
          )}
        >
          <WalletCards size={18} />
          <span>{loading["settle"] ? "..." : tr("save")}</span>
        </button>
      </Panel>
    </section>
  );
}
