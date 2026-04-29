import { AlertCircle, Eye, EyeOff, Mail, Shield, Store, UserRound } from 'lucide-react';
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
  const [showPassword, setShowPassword] = useState(false);

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

  const isSignupActive = mode === 'signup-type' || mode === 'signup-form';

  return (
    <div className="auth-page">
      <div className="auth-card">

        {/* ── Logo ── */}
        <div className="auth-brand-row">
          <div className="auth-logo-icon">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
              <rect x="4" y="3" width="16" height="18" rx="3" stroke="white" strokeWidth="1.7" />
              <path d="M8 11.5l2.5 2.5L16 8.5" stroke="white" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
          <h1 className="auth-app-name">{tr('appName')}</h1>
        </div>
        <p className="auth-tagline">{tr('tagline')}</p>

        {/* ── Verify mode ── */}
        {mode === 'verify' ? (
          <div className="verify-screen">
            <div className="verify-icon">
              <Mail size={32} />
            </div>
            <h2>{tr('emailVerification')}</h2>
            <p>{tr('emailVerificationDesc')}</p>
            <p className="verify-hint">{tr('inbucketDevHint')}</p>
            <button
              className="primary-button"
              onClick={() => { setMode('signin'); setError(''); }}
            >
              {tr('backToSignIn')}
            </button>
          </div>
        ) : (
          <>
            {/* ── Tab switcher ── */}
            <div className="auth-tabs">
              <button
                type="button"
                className={mode === 'signin' ? 'auth-tab active' : 'auth-tab'}
                onClick={() => { setMode('signin'); resetSignup(); setError(''); }}
              >
                {tr('signIn')}
              </button>
              <button
                type="button"
                className={isSignupActive ? 'auth-tab active' : 'auth-tab'}
                onClick={() => { if (mode === 'signin') { setMode('signup-type'); setError(''); } }}
              >
                {tr('signUp')}
              </button>
              <span className="auth-tab-indicator" data-pos={mode === 'signin' ? '0' : '1'} />
            </div>

            {/* ── Account type selection ── */}
            {mode === 'signup-type' && (
              <>
                <h2 className="auth-step-title">{tr('selectAccountType')}</h2>
                <p className="auth-step-sub">{tr('selectAccountTypeDesc')}</p>

                {error && (
                  <div className="auth-error">
                    <AlertCircle size={15} />
                    <span>{error}</span>
                  </div>
                )}

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
              </>
            )}

            {/* ── Sign-in / Sign-up forms ── */}
            {(mode === 'signin' || mode === 'signup-form') && (
              <>
                {mode === 'signup-form' && accountType && (
                  <div className="auth-signup-context">
                    <span className="auth-signup-role">
                      {accountType === 'creditor' ? tr('shopOwner') : tr('customer')}
                    </span>
                    <button type="button" className="link-button" onClick={() => setMode('signup-type')}>
                      {tr('back')}
                    </button>
                  </div>
                )}

                {error && (
                  <div className="auth-error">
                    <AlertCircle size={15} />
                    <span>{error}</span>
                  </div>
                )}

                {mode === 'signin' ? (
                  <form onSubmit={(e) => void handleSignIn(e)} className="auth-form">
                    <label className="field">
                      <span>{tr('email')}</span>
                      <input
                        type="email"
                        required
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        placeholder="name@example.com"
                      />
                    </label>
                    <label className="field">
                      <span>{tr('password')}</span>
                      <div className="password-field">
                        <input
                          type={showPassword ? 'text' : 'password'}
                          required
                          value={password}
                          onChange={(e) => setPassword(e.target.value)}
                          placeholder="••••••••"
                        />
                        <button
                          type="button"
                          className="eye-toggle"
                          onClick={() => setShowPassword((s) => !s)}
                          tabIndex={-1}
                        >
                          {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                        </button>
                      </div>
                    </label>
                    <button type="submit" className="primary-button" disabled={loading}>
                      {loading ? <span className="auth-spinner" /> : tr('signIn')}
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
                      <input
                        type="tel"
                        required
                        value={phone}
                        onChange={(e) => setPhone(e.target.value)}
                        placeholder={tr('phonePlaceholder')}
                      />
                    </label>
                    <label className="field">
                      <span>{tr('email')}</span>
                      <input
                        type="email"
                        required
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        placeholder="name@example.com"
                      />
                    </label>
                    <label className="field">
                      <span>{tr('password')}</span>
                      <div className="password-field">
                        <input
                          type={showPassword ? 'text' : 'password'}
                          required
                          minLength={6}
                          value={password}
                          onChange={(e) => setPassword(e.target.value)}
                          placeholder="••••••••"
                        />
                        <button
                          type="button"
                          className="eye-toggle"
                          onClick={() => setShowPassword((s) => !s)}
                          tabIndex={-1}
                        >
                          {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                        </button>
                      </div>
                    </label>

                    {accountType === 'creditor' && (
                      <>
                        <label className="field">
                          <span>{tr('taxId')} ({tr('optional')})</span>
                          <input type="text" value={taxId} onChange={(e) => setTaxId(e.target.value)} />
                        </label>
                        <label className="field">
                          <span>{tr('commercialRegistration')} ({tr('optional')})</span>
                          <input type="text" value={commercialReg} onChange={(e) => setCommercialReg(e.target.value)} />
                        </label>
                      </>
                    )}

                    <button type="submit" className="primary-button" disabled={loading}>
                      {loading ? <span className="auth-spinner" /> : tr('signUp')}
                    </button>
                  </form>
                )}
              </>
            )}
          </>
        )}

        {/* ── Trust badge ── */}
        <div className="auth-trust">
          <Shield size={13} />
          <span>{language === 'ar' ? 'مشفّر من طرف إلى طرف' : 'End-to-end encrypted'}</span>
        </div>

        {/* ── Language toggle ── */}
        <button className="ghost-button lang-toggle" onClick={onToggleLanguage}>
          {tr('switchLanguage')}
        </button>

      </div>
    </div>
  );
}
