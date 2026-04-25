import {
  Bell,
  Bot,
  Check,
  CreditCard,
  Languages,
  QrCode,
  RefreshCw,
  Store,
  UserRound,
  Users,
  WalletCards,
  X
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import QRCode from "react-qr-code";

import { apiRequest } from "./lib/api";
import { t, type TranslationKey } from "./lib/i18n";
import type { CreditorDashboard, Debt, DebtorDashboard, DemoUser, Group, Language, NotificationItem, Profile, QRToken, VoiceDraft } from "./lib/types";

type Tab = "dashboard" | "debts" | "profile" | "qr" | "groups" | "ai" | "notifications";

const demoUsers: DemoUser[] = [
  { id: "merchant-1", name: "Baqala Al Noor", phone: "+966500000001" },
  { id: "customer-1", name: "Ahmed", phone: "+966500000002" },
  { id: "friend-1", name: "Sara", phone: "+966500000003" }
];

const tabs: Array<{ id: Tab; icon: typeof WalletCards; label: TranslationKey }> = [
  { id: "dashboard", icon: WalletCards, label: "dashboard" },
  { id: "debts", icon: CreditCard, label: "debts" },
  { id: "profile", icon: UserRound, label: "profile" },
  { id: "qr", icon: QrCode, label: "qr" },
  { id: "groups", icon: Users, label: "groups" },
  { id: "ai", icon: Bot, label: "ai" },
  { id: "notifications", icon: Bell, label: "notifications" }
];

function App() {
  const [language, setLanguage] = useState<Language>("ar");
  const [currentUser, setCurrentUser] = useState<DemoUser>(demoUsers[0]);
  const [activeTab, setActiveTab] = useState<Tab>("dashboard");
  const [profile, setProfile] = useState<Profile | null>(null);
  const [qr, setQr] = useState<QRToken | null>(null);
  const [debts, setDebts] = useState<Debt[]>([]);
  const [debtorDashboard, setDebtorDashboard] = useState<DebtorDashboard | null>(null);
  const [creditorDashboard, setCreditorDashboard] = useState<CreditorDashboard | null>(null);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [groups, setGroups] = useState<Group[]>([]);
  const [message, setMessage] = useState<string>("");

  const [debtForm, setDebtForm] = useState({
    debtor_name: "Ahmed",
    debtor_id: "customer-1",
    amount: "25.00",
    currency: "SAR",
    description: "Groceries",
    due_date: new Date(Date.now() + 2 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10),
    notes: ""
  });
  const [businessForm, setBusinessForm] = useState({
    shop_name: "Baqala Al Noor",
    activity_type: "Grocery",
    location: "Riyadh",
    description: "Neighborhood grocery"
  });
  const [groupName, setGroupName] = useState("Family");
  const [invite, setInvite] = useState({ groupId: "", userId: "friend-1" });
  const [settlement, setSettlement] = useState({ groupId: "", debtorId: "friend-1", amount: "10.00", currency: "SAR", note: "Paid on behalf" });
  const [voiceTranscript, setVoiceTranscript] = useState("على Ahmed 25 SAR groceries due 2026-05-01");
  const [voiceDraft, setVoiceDraft] = useState<VoiceDraft | null>(null);
  const [chatMessage, setChatMessage] = useState("Give me overdue summary");
  const [chatAnswer, setChatAnswer] = useState("");

  const dir = language === "ar" ? "rtl" : "ltr";
  const translate = useCallback((key: TranslationKey) => t(language, key), [language]);

  useEffect(() => {
    document.documentElement.lang = language;
    document.documentElement.dir = dir;
  }, [dir, language]);

  const loadAll = useCallback(async () => {
    try {
      const [profileResponse, qrResponse, debtsResponse, debtorResponse, creditorResponse, notificationsResponse, groupsResponse] = await Promise.all([
        apiRequest<Profile>("/profiles/me", currentUser),
        apiRequest<QRToken>("/qr/current", currentUser),
        apiRequest<Debt[]>("/debts", currentUser),
        apiRequest<DebtorDashboard>("/dashboard/debtor", currentUser),
        apiRequest<CreditorDashboard>("/dashboard/creditor", currentUser),
        apiRequest<NotificationItem[]>("/notifications", currentUser),
        apiRequest<Group[]>("/groups", currentUser)
      ]);
      setProfile(profileResponse);
      setQr(qrResponse);
      setDebts(debtsResponse);
      setDebtorDashboard(debtorResponse);
      setCreditorDashboard(creditorResponse);
      setNotifications(notificationsResponse);
      setGroups(groupsResponse);
      setMessage("");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to load data");
    }
  }, [currentUser]);

  useEffect(() => {
    void loadAll();
  }, [loadAll]);

  const statusCounts = useMemo(() => {
    return debts.reduce<Record<string, number>>((acc, debt) => {
      acc[debt.status] = (acc[debt.status] ?? 0) + 1;
      return acc;
    }, {});
  }, [debts]);

  async function runMutation(action: () => Promise<unknown>, success: string) {
    try {
      await action();
      setMessage(success);
      await loadAll();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Action failed");
    }
  }

  async function createDebt() {
    await runMutation(
      () =>
        apiRequest<Debt>("/debts", currentUser, {
          method: "POST",
          body: JSON.stringify(debtForm)
        }),
      "Debt created"
    );
  }

  async function updateProfile(payload: Partial<Profile>) {
    await runMutation(
      () =>
        apiRequest<Profile>("/profiles/me", currentUser, {
          method: "PATCH",
          body: JSON.stringify(payload)
        }),
      "Profile saved"
    );
  }

  async function saveBusinessProfile() {
    await runMutation(
      () =>
        apiRequest("/profiles/business-profile", currentUser, {
          method: "POST",
          body: JSON.stringify(businessForm)
        }),
      "Business profile saved"
    );
  }

  async function createGroup() {
    await runMutation(
      () =>
        apiRequest<Group>("/groups", currentUser, {
          method: "POST",
          body: JSON.stringify({ name: groupName })
        }),
      "Group created"
    );
  }

  async function draftFromVoice() {
    await runMutation(async () => {
      const draft = await apiRequest<VoiceDraft>("/ai/debt-draft-from-voice", currentUser, {
        method: "POST",
        body: JSON.stringify({ transcript: voiceTranscript, default_currency: "SAR" })
      });
      setVoiceDraft(draft);
      setDebtForm((previous) => ({
        ...previous,
        debtor_name: draft.debtor_name ?? previous.debtor_name,
        amount: draft.amount ?? previous.amount,
        currency: draft.currency,
        description: draft.description ?? previous.description,
        due_date: draft.due_date ?? previous.due_date
      }));
    }, "Draft extracted");
  }

  async function askChatbot() {
    await runMutation(async () => {
      const response = await apiRequest<{ answer: string }>("/ai/merchant-chat", currentUser, {
        method: "POST",
        body: JSON.stringify({ message: chatMessage })
      });
      setChatAnswer(response.answer);
    }, "Summary ready");
  }

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <Store size={28} />
          <div>
            <strong>{translate("appName")}</strong>
            <span>Thabetha</span>
          </div>
        </div>

        <label className="field">
          <span>{translate("currentUser")}</span>
          <select value={currentUser.id} onChange={(event) => setCurrentUser(demoUsers.find((user) => user.id === event.target.value) ?? demoUsers[0])}>
            {demoUsers.map((user) => (
              <option key={user.id} value={user.id}>
                {user.name}
              </option>
            ))}
          </select>
        </label>

        <nav className="nav-list">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <button key={tab.id} className={activeTab === tab.id ? "active" : ""} onClick={() => setActiveTab(tab.id)}>
                <Icon size={18} />
                <span>{translate(tab.label)}</span>
              </button>
            );
          })}
        </nav>

        <button className="ghost-button" onClick={() => setLanguage(language === "ar" ? "en" : "ar")}>
          <Languages size={18} />
          <span>{language === "ar" ? "English" : "العربية"}</span>
        </button>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <span className="eyebrow">{currentUser.id}</span>
            <h1>{translate(tabs.find((tab) => tab.id === activeTab)?.label ?? "dashboard")}</h1>
          </div>
          <button className="icon-button" title={translate("refresh")} onClick={() => void loadAll()}>
            <RefreshCw size={18} />
          </button>
        </header>

        {message && <div className="message">{message}</div>}

        {activeTab === "dashboard" && (
          <section className="content-grid">
            <Stat label={translate("totalDebt")} value={`${debtorDashboard?.total_current_debt ?? "0"} SAR`} />
            <Stat label={translate("receivable")} value={`${creditorDashboard?.total_receivable ?? "0"} SAR`} />
            <Stat label={translate("overdue")} value={String((debtorDashboard?.overdue_count ?? 0) + (creditorDashboard?.overdue_count ?? 0))} />
            <Stat label={translate("trustScore")} value={String(profile?.trust_score ?? 50)} />
            <section className="wide-panel">
              <h2>{translate("debts")}</h2>
              <DebtList debts={debts.slice(0, 6)} emptyText={translate("noData")} />
            </section>
            <section className="panel">
              <h2>{translate("notifications")}</h2>
              <List rows={notifications.slice(0, 5).map((item) => `${item.title}: ${item.body}`)} emptyText={translate("noData")} />
            </section>
          </section>
        )}

        {activeTab === "debts" && (
          <section className="split">
            <Panel title={translate("createDebt")}>
              <Input label={translate("debtorName")} value={debtForm.debtor_name} onChange={(value) => setDebtForm({ ...debtForm, debtor_name: value })} />
              <Input label={translate("debtorId")} value={debtForm.debtor_id} onChange={(value) => setDebtForm({ ...debtForm, debtor_id: value })} />
              <Input label={translate("amount")} value={debtForm.amount} onChange={(value) => setDebtForm({ ...debtForm, amount: value })} />
              <Input label={translate("currency")} value={debtForm.currency} onChange={(value) => setDebtForm({ ...debtForm, currency: value })} />
              <Input label={translate("description")} value={debtForm.description} onChange={(value) => setDebtForm({ ...debtForm, description: value })} />
              <Input label={translate("dueDate")} type="date" value={debtForm.due_date} onChange={(value) => setDebtForm({ ...debtForm, due_date: value })} />
              <button className="primary-button" onClick={() => void createDebt()}>
                <CreditCard size={18} />
                <span>{translate("create")}</span>
              </button>
            </Panel>
            <Panel title={`${translate("debts")} (${debts.length})`}>
              <div className="status-row">
                <span>{translate("active")}: {statusCounts.active ?? 0}</span>
                <span>{translate("overdue")}: {statusCounts.overdue ?? 0}</span>
                <span>{translate("paid")}: {statusCounts.paid ?? 0}</span>
              </div>
              <div className="debt-stack">
                {debts.map((debt) => (
                  <article key={debt.id} className="debt-item">
                    <div>
                      <strong>{debt.debtor_name}</strong>
                      <span>{debt.description}</span>
                    </div>
                    <b>{debt.amount} {debt.currency}</b>
                    <small>{debt.status}</small>
                    <div className="actions">
                      <button onClick={() => void runMutation(() => apiRequest(`/debts/${debt.id}/accept`, currentUser, { method: "POST" }), "Debt accepted")}>
                        <Check size={16} />
                        <span>{translate("accept")}</span>
                      </button>
                      <button onClick={() => void runMutation(() => apiRequest(`/debts/${debt.id}/reject`, currentUser, { method: "POST", body: JSON.stringify({ message: "Rejected" }) }), "Debt rejected")}>
                        <X size={16} />
                        <span>{translate("reject")}</span>
                      </button>
                      <button onClick={() => void runMutation(() => apiRequest(`/debts/${debt.id}/mark-paid`, currentUser, { method: "POST", body: JSON.stringify({ note: "Paid offline" }) }), "Payment requested")}>
                        <WalletCards size={16} />
                        <span>{translate("markPaid")}</span>
                      </button>
                      <button onClick={() => void runMutation(() => apiRequest(`/debts/${debt.id}/confirm-payment`, currentUser, { method: "POST" }), "Payment confirmed")}>
                        <Check size={16} />
                        <span>{translate("confirmPayment")}</span>
                      </button>
                    </div>
                  </article>
                ))}
                {debts.length === 0 && <p className="empty">{translate("noData")}</p>}
              </div>
            </Panel>
          </section>
        )}

        {activeTab === "profile" && profile && (
          <section className="split">
            <Panel title={translate("profile")}>
              <Input label="Name" value={profile.name} onChange={(value) => setProfile({ ...profile, name: value })} />
              <Input label="Phone" value={profile.phone} onChange={(value) => setProfile({ ...profile, phone: value })} />
              <label className="check-row">
                <input type="checkbox" checked={profile.ai_enabled} onChange={(event) => setProfile({ ...profile, ai_enabled: event.target.checked })} />
                <span>{translate("aiEnabled")}</span>
              </label>
              <label className="check-row">
                <input type="checkbox" checked={profile.whatsapp_enabled} onChange={(event) => setProfile({ ...profile, whatsapp_enabled: event.target.checked })} />
                <span>{translate("whatsapp")}</span>
              </label>
              <button className="primary-button" onClick={() => void updateProfile(profile)}>
                <Check size={18} />
                <span>{translate("save")}</span>
              </button>
            </Panel>
            <Panel title={translate("businessProfile")}>
              <Input label={translate("shopName")} value={businessForm.shop_name} onChange={(value) => setBusinessForm({ ...businessForm, shop_name: value })} />
              <Input label={translate("activityType")} value={businessForm.activity_type} onChange={(value) => setBusinessForm({ ...businessForm, activity_type: value })} />
              <Input label={translate("location")} value={businessForm.location} onChange={(value) => setBusinessForm({ ...businessForm, location: value })} />
              <Input label={translate("description")} value={businessForm.description} onChange={(value) => setBusinessForm({ ...businessForm, description: value })} />
              <button className="primary-button" onClick={() => void saveBusinessProfile()}>
                <Store size={18} />
                <span>{translate("save")}</span>
              </button>
            </Panel>
          </section>
        )}

        {activeTab === "qr" && (
          <Panel title={translate("qr")}>
            {qr && (
              <div className="qr-layout">
                <div className="qr-box">
                  <QRCode value={qr.token} size={180} />
                </div>
                <div>
                  <p className="token">{qr.token}</p>
                  <p>{new Date(qr.expires_at).toLocaleString()}</p>
                  <button className="primary-button" onClick={() => void runMutation(() => apiRequest("/qr/rotate", currentUser, { method: "POST" }), "QR rotated")}>
                    <QrCode size={18} />
                    <span>{translate("rotate")}</span>
                  </button>
                </div>
              </div>
            )}
          </Panel>
        )}

        {activeTab === "groups" && (
          <section className="split">
            <Panel title={translate("groups")}>
              <Input label={translate("groupName")} value={groupName} onChange={setGroupName} />
              <button className="primary-button" onClick={() => void createGroup()}>
                <Users size={18} />
                <span>{translate("create")}</span>
              </button>
              <List rows={groups.map((group) => `${group.name} · ${group.id}`)} emptyText={translate("noData")} />
            </Panel>
            <Panel title={translate("inviteUser")}>
              <Input label="Group ID" value={invite.groupId} onChange={(value) => setInvite({ ...invite, groupId: value })} />
              <Input label={translate("inviteUser")} value={invite.userId} onChange={(value) => setInvite({ ...invite, userId: value })} />
              <button className="primary-button" onClick={() => void runMutation(() => apiRequest(`/groups/${invite.groupId}/invite`, currentUser, { method: "POST", body: JSON.stringify({ user_id: invite.userId }) }), "Invitation sent")}>
                <Users size={18} />
                <span>{translate("create")}</span>
              </button>
              <button className="ghost-button" onClick={() => void runMutation(() => apiRequest(`/groups/${invite.groupId}/accept`, currentUser, { method: "POST" }), "Invitation accepted")}>
                <Check size={18} />
                <span>{translate("acceptInvite")}</span>
              </button>
              <Input label="Settlement group" value={settlement.groupId} onChange={(value) => setSettlement({ ...settlement, groupId: value })} />
              <Input label={translate("debtorId")} value={settlement.debtorId} onChange={(value) => setSettlement({ ...settlement, debtorId: value })} />
              <Input label={translate("amount")} value={settlement.amount} onChange={(value) => setSettlement({ ...settlement, amount: value })} />
              <button className="ghost-button" onClick={() => void runMutation(() => apiRequest(`/groups/${settlement.groupId}/settlements`, currentUser, { method: "POST", body: JSON.stringify({ debtor_id: settlement.debtorId, amount: settlement.amount, currency: settlement.currency, note: settlement.note }) }), "Settlement recorded")}>
                <WalletCards size={18} />
                <span>{translate("save")}</span>
              </button>
            </Panel>
          </section>
        )}

        {activeTab === "ai" && (
          <section className="split">
            <Panel title={translate("voiceTranscript")}>
              <textarea value={voiceTranscript} onChange={(event) => setVoiceTranscript(event.target.value)} />
              <button className="primary-button" onClick={() => void draftFromVoice()}>
                <Bot size={18} />
                <span>{translate("draft")}</span>
              </button>
              {voiceDraft && <pre>{JSON.stringify(voiceDraft, null, 2)}</pre>}
            </Panel>
            <Panel title={translate("askMerchantBot")}>
              <textarea value={chatMessage} onChange={(event) => setChatMessage(event.target.value)} />
              <button className="primary-button" onClick={() => void askChatbot()}>
                <Bot size={18} />
                <span>{translate("askMerchantBot")}</span>
              </button>
              {chatAnswer && <p className="answer">{chatAnswer}</p>}
            </Panel>
          </section>
        )}

        {activeTab === "notifications" && (
          <Panel title={translate("notifications")}>
            <div className="debt-stack">
              {notifications.map((item) => (
                <article key={item.id} className={item.read_at ? "debt-item read" : "debt-item"}>
                  <div>
                    <strong>{item.title}</strong>
                    <span>{item.body}</span>
                  </div>
                  <button onClick={() => void runMutation(() => apiRequest(`/notifications/${item.id}/read`, currentUser, { method: "POST" }), "Notification read")}>
                    <Check size={16} />
                    <span>{translate("save")}</span>
                  </button>
                </article>
              ))}
              {notifications.length === 0 && <p className="empty">{translate("noData")}</p>}
            </div>
          </Panel>
        )}
      </section>
    </main>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <section className="stat">
      <span>{label}</span>
      <strong>{value}</strong>
    </section>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="panel">
      <h2>{title}</h2>
      {children}
    </section>
  );
}

function Input({ label, value, onChange, type = "text" }: { label: string; value: string; onChange: (value: string) => void; type?: string }) {
  return (
    <label className="field">
      <span>{label}</span>
      <input type={type} value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}

function DebtList({ debts, emptyText }: { debts: Debt[]; emptyText: string }) {
  if (debts.length === 0) {
    return <p className="empty">{emptyText}</p>;
  }
  return (
    <div className="compact-list">
      {debts.map((debt) => (
        <div key={debt.id}>
          <strong>{debt.debtor_name}</strong>
          <span>{debt.amount} {debt.currency}</span>
          <small>{debt.status}</small>
        </div>
      ))}
    </div>
  );
}

function List({ rows, emptyText }: { rows: string[]; emptyText: string }) {
  if (rows.length === 0) {
    return <p className="empty">{emptyText}</p>;
  }
  return (
    <ul className="simple-list">
      {rows.map((row) => (
        <li key={row}>{row}</li>
      ))}
    </ul>
  );
}

export default App;

