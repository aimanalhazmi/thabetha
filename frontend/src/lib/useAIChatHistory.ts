import { useState, useEffect } from 'react';
import type { ChatTurn } from './types';

export interface ChatSession {
  id: string;
  title: string;
  turns: ChatTurn[];
  updatedAt: string;
}

const STORAGE_KEY = 'thabetha_ai_chat_sessions';

export function useAIChatHistory() {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);

  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        setSessions(JSON.parse(stored));
      }
    } catch (err) {
      console.error('Failed to load chat sessions', err);
    }
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
    } catch (err) {
      console.error('Failed to save chat sessions', err);
    }
  }, [sessions]);

  const activeSession = sessions.find(s => s.id === activeSessionId) || null;

  const createNewSession = () => {
    setActiveSessionId(null);
  };

  const updateSession = (turns: ChatTurn[]) => {
    if (turns.length === 0) return;
    
    if (activeSessionId) {
      setSessions(prev => prev.map(s => {
        if (s.id === activeSessionId) {
          return { ...s, turns, updatedAt: new Date().toISOString() };
        }
        return s;
      }).sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()));
    } else {
      const newSession: ChatSession = {
        id: crypto.randomUUID(),
        title: turns[0].content.slice(0, 30) + (turns[0].content.length > 30 ? '...' : ''),
        turns,
        updatedAt: new Date().toISOString(),
      };
      setSessions(prev => [newSession, ...prev]);
      setActiveSessionId(newSession.id);
    }
  };

  const deleteSession = (id: string) => {
    setSessions(prev => prev.filter(s => s.id !== id));
    if (activeSessionId === id) {
      setActiveSessionId(null);
    }
  };

  return {
    sessions,
    activeSessionId,
    activeSession,
    setActiveSessionId,
    createNewSession,
    updateSession,
    deleteSession
  };
}
