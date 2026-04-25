import { useEffect, useState } from "react";
import { Panel, Stat } from "../components/Layout";
import { apiRequest } from "../lib/api";
import { t } from "../lib/i18n";
import type { CreditorDashboard, Debt, DebtorDashboard, Language, NotificationItem, Profile } from "../lib/types";

interface Props {
  language: Language;
  message: string;
}

export function DashboardPage({ language, message }: Props) {
  const tr = (key: Parameters<typeof t>[1]) => t(language, key);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [debtorDash, setDebtorDash] = useState<DebtorDashboard | null>(null);
  const [creditorDash, setCreditorDash] = useState<CreditorDashboard | null>(null);
  const [debts, setDebts] = useState<Debt[]>([]);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);

  useEffect(() => {
    void Promise.all([
      apiRequest<Profile>("/profiles/me").then(setProfile),
      apiRequest<Debt[]>("/debts").then(setDebts),
      apiRequest<DebtorDashboard>("/dashboard/debtor").then(setDebtorDash),
      apiRequest<CreditorDashboard>("/dashboard/creditor").then(setCreditorDash),
      apiRequest<NotificationItem[]>("/notifications").then(setNotifications),
    ]).catch(() => {});
  }, []);

  return (
    <section className="content-grid">
      {message && <div className="message wide-panel">{message}</div>}
      <Stat label={tr("totalDebt")} value={`${debtorDash?.total_current_debt ?? "0"} SAR`} />
      <Stat label={tr("receivable")} value={`${creditorDash?.total_receivable ?? "0"} SAR`} />
      <Stat label={tr("overdue")} value={String((debtorDash?.overdue_count ?? 0) + (creditorDash?.overdue_count ?? 0))} />
      <Stat label={tr("trustScore")} value={String(profile?.trust_score ?? 50)} />
      <section className="wide-panel">
        <h2>{tr("debts")}</h2>
        <div className="compact-list">
          {debts.slice(0, 6).map((d) => (
            <div key={d.id}>
              <strong>{d.debtor_name}</strong>
              <span>{d.amount} {d.currency}</span>
              <small>{d.status}</small>
            </div>
          ))}
          {debts.length === 0 && <p className="empty">{tr("noData")}</p>}
        </div>
      </section>
      <Panel title={tr("notifications")}>
        <ul className="simple-list">
          {notifications.slice(0, 5).map((n) => (
            <li key={n.id}>{n.title}: {n.body}</li>
          ))}
          {notifications.length === 0 && <p className="empty">{tr("noData")}</p>}
        </ul>
      </Panel>
    </section>
  );
}
