import { Bot, Send, Trash2 } from 'lucide-react';
import { useMemo, useState } from 'react';
import { Panel } from '../Layout';
import { postMerchantChat } from '../../lib/api';
import { t } from '../../lib/i18n';
import type { ChatTurn, Language } from '../../lib/types';

const HISTORY_TURN_CAP = 10;

interface Props {
  language: Language;
}

export function MerchantChatPanel({ language }: Props) {
  const tr = (key: Parameters<typeof t>[1]) => t(language, key);
  const [input, setInput] = useState('');
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const timezone = useMemo(() => {
    try {
      return Intl.DateTimeFormat().resolvedOptions().timeZone || 'Asia/Riyadh';
    } catch {
      return 'Asia/Riyadh';
    }
  }, []);

  async function send() {
    const message = input.trim();
    if (!message || busy) return;
    setError(null);
    setBusy(true);
    const userTurn: ChatTurn = { role: 'user', content: message };
    const optimistic = [...turns, userTurn];
    setTurns(optimistic);
    setInput('');
    try {
      const history = optimistic.slice(-HISTORY_TURN_CAP - 1, -1);
      const res = await postMerchantChat({ message, history, locale: language, timezone });
      setTurns([...optimistic, { role: 'assistant', content: res.answer }]);
    } catch (err) {
      // Roll back the optimistic user turn so retries don't pile up.
      setTurns(turns);
      setError(translateError(err, tr));
    } finally {
      setBusy(false);
    }
  }

  function clearChat() {
    setTurns([]);
    setError(null);
  }

  return (
    <Panel title={tr('merchantChatTitle')}>
      <p className="muted">{tr('merchantChatSubtitle')}</p>
      <div className="chat-transcript" role="log" aria-live="polite">
        {turns.length === 0 && <p className="muted">{tr('chatLocaleHint')}</p>}
        {turns.map((turn, idx) => (
          <div key={idx} className={`chat-turn chat-turn-${turn.role}`}>
            <strong>{turn.role === 'user' ? '🙂' : <Bot size={14} aria-hidden />}</strong>
            <span>{turn.content}</span>
          </div>
        ))}
      </div>
      {error && <div className="message error">{error}</div>}
      <textarea
        value={input}
        onChange={(e) => setInput(e.target.value)}
        placeholder={tr('chatPlaceholder')}
        rows={2}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            void send();
          }
        }}
      />
      <div className="row">
        <button className="primary-button" onClick={() => void send()} disabled={busy || !input.trim()}>
          <Send size={16} />
          <span>{tr('chatSend')}</span>
        </button>
        <button className="secondary-button" onClick={clearChat} disabled={busy || turns.length === 0}>
          <Trash2 size={16} />
          <span>{tr('chatClear')}</span>
        </button>
      </div>
    </Panel>
  );
}

function translateError(err: unknown, tr: (key: Parameters<typeof t>[1]) => string): string {
  if (!(err instanceof Error)) return tr('chatErrorGeneric');
  const m = /^(\d{3}):/.exec(err.message);
  if (!m) return tr('chatErrorGeneric');
  switch (m[1]) {
    case '403':
      return tr('chatDisabled');
    case '429':
      return tr('chatQuotaExceeded');
    case '503':
      return tr('chatProviderUnavailable');
    default:
      return tr('chatErrorGeneric');
  }
}
