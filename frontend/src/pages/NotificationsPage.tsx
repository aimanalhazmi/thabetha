import { Bell, Check } from "lucide-react";
import { useEffect, useState } from "react";
import { WhatsAppDeliveryBadge } from "../components/WhatsAppDeliveryBadge";
import { apiRequest } from "../lib/api";
import { humanizeError } from "../lib/errors";
import { t } from "../lib/i18n";
import type { Language, NotificationItem } from "../lib/types";

interface Props { language: Language }

export function NotificationsPage({ language }: Props) {
  const tr = (key: Parameters<typeof t>[1]) => t(language, key);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [message, setMessage] = useState("");
  const [markingRead, setMarkingRead] = useState(false);

  // ── Data fetching — untouched ─────────────────────────────────
  async function load() {
    try {
      setNotifications(await apiRequest<NotificationItem[]>("/notifications"));
    } catch (err) {
      setMessage(humanizeError(err, language, 'loadNotifications'));
    }
  }

  useEffect(() => { void load(); }, []);

  // ── Handlers — untouched ──────────────────────────────────────
  async function markRead(id: string) {
    setMarkingRead(true);
    try {
      await apiRequest(`/notifications/${id}/read`, { method: "POST" });
      await load();
    } catch (err) {
      setMessage(humanizeError(err, language, 'transition'));
    } finally {
      setMarkingRead(false);
    }
  }

  // Batches the same API call as markRead for each unread item, one load() at the end.
  async function markAllRead() {
    const unread = notifications.filter(n => !n.read_at);
    if (unread.length === 0) return;
    setMarkingRead(true);
    try {
      await Promise.all(
        unread.map(n => apiRequest(`/notifications/${n.id}/read`, { method: "POST" }))
      );
      await load();
    } catch (err) {
      setMessage(humanizeError(err, language, 'transition'));
    } finally {
      setMarkingRead(false);
    }
  }

  const unreadCount = notifications.filter(n => !n.read_at).length;

  function formatDate(iso: string) {
    try {
      return new Date(iso).toLocaleDateString(
        language === 'ar' ? 'ar-SA' : 'en-GB',
        { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }
      );
    } catch { return iso; }
  }

  const markAllLabel = language === 'ar' ? 'تحديد الكل كمقروء' : 'Mark all read';

  return (
    <section className="notif-page">
      {message && <div className="message">{message}</div>}

      {/* Page header */}
      <div className="notif-page-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <Bell size={18} color="var(--text-secondary)" />
          <h2 className="debts-page__title">
            {tr('notifications')}
            {unreadCount > 0 && <span className="dash-unread-badge">{unreadCount}</span>}
          </h2>
        </div>
        {unreadCount > 0 && (
          <button
            className="ghost-button"
            disabled={markingRead}
            onClick={() => void markAllRead()}
          >
            <Check size={14} />
            <span>{markingRead ? '…' : markAllLabel}</span>
          </button>
        )}
      </div>

      {/* Notification cards */}
      <div className="notif-list">
        {notifications.map((item) => (
          <article
            key={item.id}
            className={`notif-card${item.read_at ? ' notif-card--read' : ' notif-card--unread'}`}
          >
            {!item.read_at && <span className="notif-card__dot" />}

            <div className="notif-card__content">
              <div className="notif-card__header">
                <strong className="notif-card__title">{item.title}</strong>
                <span className="notif-card__date">{formatDate(item.created_at)}</span>
              </div>
              <p className="notif-card__body">{item.body}</p>
              {item.whatsapp_status && item.whatsapp_status !== 'not_attempted' && (
                <WhatsAppDeliveryBadge
                  status={item.whatsapp_status}
                  failedReason={item.whatsapp_failed_reason}
                  language={language}
                />
              )}
            </div>

            {!item.read_at && (
              <button
                className="notif-card__action"
                disabled={markingRead}
                title={tr('save')}
                onClick={() => void markRead(item.id)}
              >
                <Check size={15} />
              </button>
            )}
          </article>
        ))}
        {notifications.length === 0 && <p className="empty">{tr('noNotificationsYet')}</p>}
      </div>
    </section>
  );
}
