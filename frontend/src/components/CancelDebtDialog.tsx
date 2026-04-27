import { useEffect, useRef, useState } from 'react';
import { apiRequest } from '../lib/api';
import { t } from '../lib/i18n';
import type { Debt, Language } from '../lib/types';

interface Props {
  debt: Debt;
  language: Language;
  onCancelled: (updated: Debt) => void;
  onClose: () => void;
}

export function CancelDebtDialog({ debt, language, onCancelled, onClose }: Props) {
  const tr = (key: Parameters<typeof t>[1]) => t(language, key);
  const [message, setMessage] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Focus the textarea on mount so a typing creditor doesn't need to click.
  useEffect(() => {
    textareaRef.current?.focus();
  }, []);

  // Close on Escape key.
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !submitting) onClose();
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [onClose, submitting]);

  const handleConfirm = async () => {
    setSubmitting(true);
    setError(null);
    try {
      const updated = await apiRequest<Debt>(`/debts/${debt.id}/cancel`, {
        method: 'POST',
        body: JSON.stringify({ message: message.trim() }),
      });
      onCancelled(updated);
      onClose();
    } catch (err: unknown) {
      const status = (err as { status?: number }).status;
      if (status === 409) {
        setError(tr('cancel_debt_state_changed'));
      } else {
        setError(language === 'ar' ? 'حدث خطأ، حاول مرة أخرى' : 'Something went wrong, please try again.');
      }
      setSubmitting(false);
    }
  };

  const isRtl = language === 'ar';

  return (
    <div
      role="presentation"
      style={{
        position: 'fixed', inset: 0, zIndex: 1000,
        background: 'rgba(0,0,0,0.45)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}
      onClick={(e) => { if (e.target === e.currentTarget && !submitting) onClose(); }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="cancel-dialog-title"
        dir={isRtl ? 'rtl' : 'ltr'}
        style={{
          background: 'var(--card-bg, #fff)',
          borderRadius: '0.75rem',
          padding: '1.5rem',
          width: 'min(90vw, 420px)',
          display: 'flex', flexDirection: 'column', gap: '1rem',
          boxShadow: '0 8px 32px rgba(0,0,0,0.18)',
        }}
      >
        <h2 id="cancel-dialog-title" style={{ margin: 0, fontSize: '1.1rem', fontWeight: 700 }}>
          {tr('cancel_debt_confirm_title')}
        </h2>

        <p style={{ margin: 0, fontSize: '0.95rem', color: 'var(--text-secondary, #555)' }}>
          {tr('cancel_debt_confirm_body')}
        </p>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
          <textarea
            ref={textareaRef}
            rows={3}
            maxLength={200}
            placeholder={tr('cancel_message_optional')}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            disabled={submitting}
            style={{
              resize: 'vertical',
              padding: '0.5rem 0.625rem',
              borderRadius: '0.375rem',
              border: '1px solid var(--border, #ccc)',
              fontSize: '0.9rem',
              fontFamily: 'inherit',
              direction: isRtl ? 'rtl' : 'ltr',
              width: '100%',
              boxSizing: 'border-box',
            }}
          />
          <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary, #888)', textAlign: isRtl ? 'left' : 'right' }}>
            {message.length}/200
          </span>
        </div>

        {error && (
          <p role="alert" style={{ margin: 0, color: 'var(--error, #c0392b)', fontSize: '0.875rem' }}>
            {error}
          </p>
        )}

        <div style={{ display: 'flex', gap: '0.625rem', justifyContent: isRtl ? 'flex-start' : 'flex-end' }}>
          <button
            type="button"
            onClick={onClose}
            disabled={submitting}
            style={{ padding: '0.5rem 1rem', borderRadius: '0.375rem', cursor: 'pointer' }}
          >
            {tr('cancel')}
          </button>
          <button
            type="button"
            onClick={() => void handleConfirm()}
            disabled={submitting}
            className="primary-button"
            style={{ padding: '0.5rem 1rem', borderRadius: '0.375rem', cursor: 'pointer' }}
          >
            {submitting ? '…' : tr('cancel_debt')}
          </button>
        </div>
      </div>
    </div>
  );
}
