import { useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { apiRequest } from '../lib/api';
import { t } from '../lib/i18n';
import type { Debt, Language } from '../lib/types';

const POLL_INTERVAL_MS = 3000;
const POLL_TIMEOUT_MS = 60000;

export default function PaymentReturnPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const debtId = searchParams.get('debt_id');
  const language = (searchParams.get('lang') ?? 'ar') as Language;
  const tr = (k: Parameters<typeof t>[1]) => t(language, k);

  const [status, setStatus] = useState<'polling' | 'succeeded' | 'timeout'>('polling');
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!debtId) {
      navigate('/debts', { replace: true });
      return;
    }

    const stopPolling = () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };

    const poll = async () => {
      try {
        const debt = await apiRequest<Debt>(`/debts/${debtId}`);
        if (debt.status === 'paid') {
          stopPolling();
          setStatus('succeeded');
          setTimeout(() => { navigate('/debts', { replace: true }); }, 2000);
        }
      } catch {
        // Network hiccup — keep polling
      }
    };

    intervalRef.current = setInterval(() => { void poll(); }, POLL_INTERVAL_MS);
    timeoutRef.current = setTimeout(() => {
      stopPolling();
      setStatus('timeout');
      setTimeout(() => { navigate('/debts', { replace: true }); }, 3000);
    }, POLL_TIMEOUT_MS);

    void poll();

    return stopPolling;
  }, [debtId, navigate]);

  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '60vh' }}>
      <div style={{ maxWidth: 420, textAlign: 'center', padding: '2rem' }}>
        {status === 'polling' && (
          <p>{tr('paymentProcessing')}</p>
        )}
        {status === 'succeeded' && (
          <p style={{ fontWeight: 600 }}>
            {tr('paymentSucceeded')}
          </p>
        )}
        {status === 'timeout' && (
          <div>
            <p style={{ fontWeight: 600 }}>{tr('paymentPendingTitle')}</p>
            <p style={{ marginTop: '0.5rem' }}>{tr('paymentPendingBody')}</p>
          </div>
        )}
      </div>
    </div>
  );
}
