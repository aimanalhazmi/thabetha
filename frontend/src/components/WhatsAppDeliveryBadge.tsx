import { t, type TranslationKey } from '../lib/i18n';
import type { Language, WhatsAppDeliveryStatus, WhatsAppFailedReason } from '../lib/types';

interface Props {
  status: WhatsAppDeliveryStatus | undefined;
  failedReason?: WhatsAppFailedReason | null;
  language: Language;
}

const STATUS_KEY: Record<Exclude<WhatsAppDeliveryStatus, 'not_attempted'>, TranslationKey> = {
  attempted_unknown: 'whatsapp_status_attempted',
  delivered: 'whatsapp_status_delivered',
  failed: 'whatsapp_status_failed',
};

const STATUS_TONE: Record<Exclude<WhatsAppDeliveryStatus, 'not_attempted'>, string> = {
  attempted_unknown: 'bg-amber-50 text-amber-800 ring-amber-200',
  delivered: 'bg-emerald-50 text-emerald-800 ring-emerald-200',
  failed: 'bg-rose-50 text-rose-800 ring-rose-200',
};

export function WhatsAppDeliveryBadge({ status, failedReason, language }: Props) {
  if (!status || status === 'not_attempted') return null;
  const label = t(language, STATUS_KEY[status]);
  const reasonKey = failedReason ? (`whatsapp_failed_reason_${failedReason}` as TranslationKey) : null;
  const reasonLabel = reasonKey ? t(language, reasonKey) : null;
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs ring-1 ${STATUS_TONE[status]}`}
      title={reasonLabel ?? undefined}
    >
      {label}
      {status === 'failed' && reasonLabel ? <span aria-hidden="true">— {reasonLabel}</span> : null}
    </span>
  );
}
