import { Check, CreditCard, WalletCards, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Input, Panel } from "../components/Layout";
import { apiRequest } from "../lib/api";
import { t } from "../lib/i18n";
import type { Debt, Language } from "../lib/types";

interface Props { language: Language }

export function DebtsPage({ language }: Props) {
  const tr = (key: Parameters<typeof t>[1]) => t(language, key);
  const [debts, setDebts] = useState<Debt[]>([]);
  const [message, setMessage] = useState("");
  const [debtForm, setDebtForm] = useState({
    debtor_name: "",
    debtor_id: "",
    amount: "25.00",
    currency: "SAR",
    description: "",
    due_date: new Date(Date.now() + 7 * 86400000).toISOString().slice(0, 10),
    notes: "",
  });

  async function load() {
    try {
      const data = await apiRequest<Debt[]>("/debts");
      setDebts(data);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Failed to load");
    }
  }

  useEffect(() => { void load(); }, []);

  async function runAction(action: () => Promise<unknown>, success: string) {
    try {
      await action();
      setMessage(success);
      await load();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Action failed");
    }
  }

  const statusCounts = useMemo(() =>
    debts.reduce<Record<string, number>>((acc, d) => { acc[d.status] = (acc[d.status] ?? 0) + 1; return acc; }, {}),
    [debts]
  );

  return (
    <section className="split">
      <Panel title={tr("createDebt")}>
        {message && <div className="message">{message}</div>}
        <Input label={tr("debtorName")} value={debtForm.debtor_name} onChange={(v) => setDebtForm({ ...debtForm, debtor_name: v })} />
        <Input label={tr("debtorId")} value={debtForm.debtor_id} onChange={(v) => setDebtForm({ ...debtForm, debtor_id: v })} />
        <Input label={tr("amount")} value={debtForm.amount} onChange={(v) => setDebtForm({ ...debtForm, amount: v })} />
        <Input label={tr("currency")} value={debtForm.currency} onChange={(v) => setDebtForm({ ...debtForm, currency: v })} />
        <Input label={tr("description")} value={debtForm.description} onChange={(v) => setDebtForm({ ...debtForm, description: v })} />
        <Input label={tr("dueDate")} type="date" value={debtForm.due_date} onChange={(v) => setDebtForm({ ...debtForm, due_date: v })} />
        <button
          className="primary-button"
          onClick={() => void runAction(() => apiRequest<Debt>("/debts", { method: "POST", body: JSON.stringify(debtForm) }), "Debt created")}
        >
          <CreditCard size={18} />
          <span>{tr("create")}</span>
        </button>
      </Panel>
      <Panel title={`${tr("debts")} (${debts.length})`}>
        <div className="status-row">
          <span>{tr("active")}: {statusCounts.active ?? 0}</span>
          <span>{tr("overdue")}: {statusCounts.overdue ?? 0}</span>
          <span>{tr("paid")}: {statusCounts.paid ?? 0}</span>
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
                <button onClick={() => void runAction(() => apiRequest(`/debts/${debt.id}/accept`, { method: "POST" }), "Debt accepted")}>
                  <Check size={16} /><span>{tr("accept")}</span>
                </button>
                <button onClick={() => void runAction(() => apiRequest(`/debts/${debt.id}/reject`, { method: "POST", body: JSON.stringify({ message: "Rejected" }) }), "Debt rejected")}>
                  <X size={16} /><span>{tr("reject")}</span>
                </button>
                <button onClick={() => void runAction(() => apiRequest(`/debts/${debt.id}/mark-paid`, { method: "POST", body: JSON.stringify({ note: "Paid offline" }) }), "Payment requested")}>
                  <WalletCards size={16} /><span>{tr("markPaid")}</span>
                </button>
                <button onClick={() => void runAction(() => apiRequest(`/debts/${debt.id}/confirm-payment`, { method: "POST" }), "Payment confirmed")}>
                  <Check size={16} /><span>{tr("confirmPayment")}</span>
                </button>
              </div>
            </article>
          ))}
          {debts.length === 0 && <p className="empty">{tr("noData")}</p>}
        </div>
      </Panel>
    </section>
  );
}
