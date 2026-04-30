import { Plus } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { t } from '../lib/i18n';
import type { Language } from '../lib/types';

interface Props { language: Language }

export function FAB({ language }: Props) {
  const navigate = useNavigate();
  const { user } = useAuth();
  if (!user) return null;
  const isCreditor = user.account_type === 'creditor' || user.account_type === 'both' || user.account_type === 'business';
  if (!isCreditor) return null;
  const label = t(language, 'fab_create_debt');
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={() => navigate('/debts/new')}
      style={{
        position: 'fixed',
        insetInlineEnd: '1.5rem',
        bottom: '1.5rem',
        width: 56,
        height: 56,
        borderRadius: '50%',
        border: 'none',
        background: 'var(--accent, #2563eb)',
        color: '#fff',
        boxShadow: '0 6px 20px rgba(0,0,0,0.18)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        cursor: 'pointer',
        zIndex: 50,
      }}
    >
      <Plus size={26} />
    </button>
  );
}
