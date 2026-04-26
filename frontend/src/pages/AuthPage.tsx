import { Mail, Store, UserRound } from 'lucide-react';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { t } from '../lib/i18n';
import type { AccountType, Language } from '../lib/types';

interface Props {
  language: Language;
  onToggleLanguage: () => void;
}

export function AuthPage({ language, onToggleLanguage }: Props) {
  const [mode, setMode] = useState<'signin' | 'signup-type' | 'signup-form' | 'verify'>('signin');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { signIn, signUp } = useAuth();
  const navigate = useNavigate();

  // Fields
  const [accountType, setAccountType] = useState<AccountType | null>(null);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [taxId, setTaxId] = useState('');
  const [commercialReg, setCommercialReg] = useState('');

  const tr = (key: Parameters<typeof t>[1]) => t(language, key);

  async function handleSignIn(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await signIn(email, password);
      navigate('/dashboard');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sign in failed');
    } finally {
      setLoading(false);
    }
  }

  async function handleSignUp(e: React.FormEvent) {
    e.preventDefault();
    if (!accountType) return;
    setError('');
    setLoading(true);
    try {
      const result = await signUp({
        name,
        phone,
        email,
        password,
        account_type: accountType,
        tax_id: accountType === 'creditor' && taxId ? taxId : undefined,
        commercial_registration: accountType === 'creditor' && commercialReg ? commercialReg : undefined,
      });
      if (result.needsVerification) {
        setMode('verify');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sign up failed');
    } finally {
      setLoading(false);
    }
  }

  function resetSignup() {
    setAccountType(null);
    setName(''); setPhone(''); setEmail(''); setPassword('');
    setTaxId(''); setCommercialReg('');
    setError('');
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-brand">
          <div className="brand-icon">
            <Store size={24} />
          </div>
          <h1>{tr('appName')}</h1>
        </div>

        {mode === 'verify' ? (
          <div className="verify-screen">
            <div className="verify-icon">
              <Mail size={32} />
            </div>
            <h2>{tr('emailVerification')}</h2>
            <p>{tr('emailVerificationDesc')}</p>
            <p style={{ fontSize: '0.8rem', color: '#64748b' }}>
              {language === 'ar'
                ? `📧 تحقق من Inbucket على المنفذ 55324`
                : `📧 Check Inbucket at localhost:55324`}
            </p>
            <button
              className="primary-button"
              onClick={() => { setMode('signin'); setError(''); }}
            >
              {tr('backToSignIn')}
            </button>
          </div>
        ) : mode === 'signup-type' ? (
          <>
            <h2>{tr('selectAccountType')}</h2>
            <p style={{ color: '#64748b', marginTop: '-0.25rem' }}>{tr('selectAccountTypeDesc')}</p>

            {error && <div className="message error">{error}</div>}

            <div className="account-type-grid">
              <button
                type="button"
                className={`account-type-card${accountType === 'creditor' ? ' selected' : ''}`}
                onClick={() => setAccountType('creditor')}
              >
                <Store size={28} />
                <strong>{tr('shopOwner')}</strong>
                <span>{tr('shopOwnerDesc')}</span>
              </button>
              <button
                type="button"
                className={`account-type-card${accountType === 'debtor' ? ' selected' : ''}`}
                onClick={() => setAccountType('debtor')}
              >
                <UserRound size={28} />
                <strong>{tr('customer')}</strong>
                <span>{tr('customerDesc')}</span>
              </button>
            </div>

            <button
              className="primary-button"
              disabled={!accountType}
              onClick={() => { setError(''); setMode('signup-form'); }}
            >
              {tr('continueAction')}
            </button>

            <p className="auth-toggle">
              {tr('alreadyHaveAccount')}{' '}
              <button
                className="link-button"
                onClick={() => { setMode('signin'); resetSignup(); }}
              >
                {tr('signIn')}
              </button>
            </p>
          </>
        ) : (
          <>
            <h2>{mode === 'signin' ? tr('welcomeBack') : tr('createAccount')}</h2>
            {mode === 'signup-form' && accountType && (
              <p style={{ color: '#64748b', marginTop: '-0.25rem' }}>
                {accountType === 'creditor' ? tr('shopOwner') : tr('customer')}
                {' · '}
                <button className="link-button" onClick={() => setMode('signup-type')}>{tr('back')}</button>
              </p>
            )}

            {error && <div className="message error">{error}</div>}

            {mode === 'signin' ? (
              <form onSubmit={(e) => void handleSignIn(e)} className="auth-form">
                <label className="field">
                  <span>{tr('email')}</span>
                  <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
                </label>
                <label className="field">
                  <span>{tr('password')}</span>
                  <input type="password" required value={password} onChange={(e) => setPassword(e.target.value)} />
                </label>
                <button type="submit" className="primary-button" disabled={loading}>
                  {loading ? '...' : tr('signIn')}
                </button>
              </form>
            ) : (
              <form onSubmit={(e) => void handleSignUp(e)} className="auth-form">
                <label className="field">
                  <span>{tr('name')}</span>
                  <input type="text" required value={name} onChange={(e) => setName(e.target.value)} />
                </label>
                <label className="field">
                  <span>{tr('phone')}</span>
                  <input type="tel" required value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+966500000000" />
                </label>
                <label className="field">
                  <span>{tr('email')}</span>
                  <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
                </label>
                <label className="field">
                  <span>{tr('password')}</span>
                  <input type="password" required minLength={6} value={password} onChange={(e) => setPassword(e.target.value)} />
                </label>

                {accountType === 'creditor' && (
                  <>
                    <label className="field">
                      <span>{tr('taxId')} ({language === 'ar' ? 'اختياري' : 'optional'})</span>
                      <input type="text" value={taxId} onChange={(e) => setTaxId(e.target.value)} />
                    </label>
                    <label className="field">
                      <span>{tr('commercialRegistration')} ({language === 'ar' ? 'اختياري' : 'optional'})</span>
                      <input type="text" value={commercialReg} onChange={(e) => setCommercialReg(e.target.value)} />
                    </label>
                  </>
                )}

                <button type="submit" className="primary-button" disabled={loading}>
                  {loading ? '...' : tr('signUp')}
                </button>
              </form>
            )}

            <p className="auth-toggle">
              {mode === 'signin' ? tr('dontHaveAccount') : tr('alreadyHaveAccount')}
              {' '}
              <button
                className="link-button"
                onClick={() => {
                  if (mode === 'signin') { setMode('signup-type'); setError(''); }
                  else { setMode('signin'); resetSignup(); }
                }}
              >
                {mode === 'signin' ? tr('signUp') : tr('signIn')}
              </button>
            </p>
          </>
        )}

        <button className="ghost-button lang-toggle" onClick={onToggleLanguage}>
          {language === 'ar' ? 'English' : 'العربية'}
        </button>
      </div>
    </div>
  );
}
