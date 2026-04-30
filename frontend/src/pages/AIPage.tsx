import { Bot, MessageSquare, Plus, Send, Trash2, User } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { postMerchantChat } from '../lib/api';
import { t } from '../lib/i18n';
import type { ChatTurn, Language } from '../lib/types';
import { useAIChatHistory } from '../lib/useAIChatHistory';

const HISTORY_TURN_CAP = 10;

interface Props { language: Language }

export function AIPage({ language }: Props) {
  const tr = (key: Parameters<typeof t>[1]) => t(language, key);
  const { sessions, activeSessionId, activeSession, setActiveSessionId, createNewSession, updateSession, deleteSession } = useAIChatHistory();
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const turns = activeSession?.turns || [];
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const timezone = useMemo(() => {
    try {
      return Intl.DateTimeFormat().resolvedOptions().timeZone || 'Asia/Riyadh';
    } catch {
      return 'Asia/Riyadh';
    }
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [turns]);

  async function send() {
    const message = input.trim();
    if (!message || busy) return;
    setError(null);
    setBusy(true);
    const userTurn: ChatTurn = { role: 'user', content: message };
    const optimistic = [...turns, userTurn];
    updateSession(optimistic);
    setInput('');
    
    try {
      const history = optimistic.slice(-HISTORY_TURN_CAP - 1, -1);
      const res = await postMerchantChat({ message, history, locale: language, timezone });
      updateSession([...optimistic, { role: 'assistant', content: res.answer }]);
    } catch (err) {
      updateSession(turns); // Rollback
      setError(translateError(err, tr));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="ai-chat-layout">
      {/* Sidebar for Chat History */}
      <aside className="ai-chat-sidebar">
        <button className="new-chat-btn" onClick={createNewSession}>
          <Plus size={18} />
          <span>{tr('askMerchantBot')}</span>
        </button>
        <div className="ai-session-list">
          {sessions.map((session) => (
            <div 
              key={session.id} 
              className={`ai-session-item ${session.id === activeSessionId ? 'active' : ''}`}
              onClick={() => setActiveSessionId(session.id)}
            >
              <MessageSquare size={16} />
              <span className="ai-session-title">{session.title}</span>
              <button 
                className="ai-session-delete" 
                onClick={(e) => { e.stopPropagation(); deleteSession(session.id); }}
                title={tr('chatClear')}
              >
                <Trash2 size={14} />
              </button>
            </div>
          ))}
          {sessions.length === 0 && <p className="muted empty-sessions">{tr('chatNoData')}</p>}
        </div>
      </aside>

      {/* Main Chat Area */}
      <main className="ai-chat-main">
        <div className="ai-chat-header">
          <h2>{tr('merchantChatTitle')}</h2>
          <p>{tr('merchantChatSubtitle')}</p>
        </div>

        <div className="ai-chat-messages" role="log" aria-live="polite">
          {turns.length === 0 ? (
            <div className="ai-chat-empty-state">
              <div className="ai-chat-bot-icon">
                <Bot size={48} />
              </div>
              <h2>{tr('merchantChatTitle')}</h2>
              <p>{tr('chatLocaleHint')}</p>
            </div>
          ) : (
            turns.map((turn, idx) => (
              <div key={idx} className={`ai-message-wrapper ${turn.role}`}>
                <div className="ai-message-avatar">
                  {turn.role === 'user' ? <User size={20} /> : <Bot size={20} />}
                </div>
                <div className="ai-message-content">
                  <div className="ai-message-bubble">
                    {turn.content.split('\n').map((line, i) => <p key={i}>{line}</p>)}
                  </div>
                </div>
              </div>
            ))
          )}
          {busy && (
            <div className="ai-message-wrapper assistant loading">
               <div className="ai-message-avatar"><Bot size={20} /></div>
               <div className="ai-message-content">
                 <div className="ai-message-bubble typing-indicator">
                    <span></span><span></span><span></span>
                 </div>
               </div>
            </div>
          )}
          {error && <div className="message error ai-chat-error">{error}</div>}
          <div ref={messagesEndRef} />
        </div>

        <div className="ai-chat-input-area">
          <div className="ai-input-container">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={tr('chatPlaceholder')}
              rows={1}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  void send();
                }
              }}
              onInput={(e) => {
                const target = e.target as HTMLTextAreaElement;
                target.style.height = 'auto';
                target.style.height = `${Math.min(target.scrollHeight, 150)}px`;
              }}
            />
            <button 
              className="ai-send-btn" 
              onClick={() => void send()} 
              disabled={busy || !input.trim()}
            >
              <Send size={20} />
            </button>
          </div>
          <div className="ai-input-footer">
            Thabetha AI can make mistakes. Please verify important financial information.
          </div>
        </div>
      </main>
    </div>
  );
}

function translateError(err: unknown, tr: (key: Parameters<typeof t>[1]) => string): string {
  if (!(err instanceof Error)) return tr('chatErrorGeneric');
  const m = /^(\d{3}):/.exec(err.message);
  if (!m) return tr('chatErrorGeneric');
  switch (m[1]) {
    case '403': return tr('chatDisabled');
    case '429': return tr('chatQuotaExceeded');
    case '503': return tr('chatProviderUnavailable');
    default: return tr('chatErrorGeneric');
  }
}
