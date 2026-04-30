import { Bot, Sparkles } from "lucide-react";
import { useState } from "react";
import { MerchantChatPanel } from "../components/ai/MerchantChatPanel";
import { Panel } from "../components/Layout";
import { aiVoiceDrafts } from "../lib/api";
import { humanizeError } from "../lib/errors";
import { t } from "../lib/i18n";
import type { Language, VoiceDraft } from "../lib/types";

interface Props { language: Language }

const CONFIDENCE_COLOR = (c: number) =>
  c >= 0.8 ? 'var(--success)' : c >= 0.5 ? 'var(--warning)' : 'var(--danger)';

export function AIPage({ language }: Props) {
  const tr = (key: Parameters<typeof t>[1]) => t(language, key);
  const [transcript, setTranscript] = useState("على Ahmed 25 SAR groceries due 2026-05-01");
  const [voiceDraft, setVoiceDraft] = useState<VoiceDraft | null>(null);
  const [message, setMessage] = useState("");

  // ── Handler — untouched ───────────────────────────────────────
  async function draftFromVoice() {
    try {
      const draft = await aiVoiceDrafts.fromTranscript(transcript);
      setVoiceDraft(draft);
      setMessage("Draft extracted");
    } catch (err) {
      setMessage(humanizeError(err, language, "aiVoiceDraft"));
    }
  }

  return (
    <section className="split">
      {message && <div className="message" style={{ gridColumn: '1 / -1' }}>{message}</div>}

      {/* Voice transcript panel */}
      <Panel title={tr("voiceTranscript")}>
        <div className="ai-transcript-panel">
          <textarea
            className="ai-transcript-panel__input"
            value={transcript}
            onChange={(e) => setTranscript(e.target.value)}
            rows={4}
          />
          <button
            className="primary-button"
            style={{ width: '100%', justifyContent: 'center' }}
            onClick={() => void draftFromVoice()}
          >
            <Bot size={18} /><span>{tr("draft")}</span>
          </button>
        </div>

        {/* Voice draft result */}
        {voiceDraft && (
          <div className="voice-draft-result">
            <div className="voice-draft-result__header">
              <Sparkles size={15} color="var(--primary)" />
              <span>{tr("voiceDraftTranscript")}</span>
              <div className="voice-draft-result__confidence">
                <span style={{ color: CONFIDENCE_COLOR(voiceDraft.confidence) }}>
                  {Math.round(voiceDraft.confidence * 100)}%
                </span>
              </div>
            </div>

            <p className="voice-draft-result__transcript">{voiceDraft.raw_transcript}</p>

            <div className="voice-draft-result__fields">
              {(
                [
                  ['debtorName', voiceDraft.debtor_name],
                  ['amount', voiceDraft.amount ? `${voiceDraft.amount} ${voiceDraft.currency}` : null],
                  ['description', voiceDraft.description],
                  ['dueDate', voiceDraft.due_date],
                ] as [Parameters<typeof t>[1], string | null][]
              ).map(([key, val]) => (
                <div key={String(key)} className="voice-draft-result__row">
                  <span className="voice-draft-result__label">{tr(key)}</span>
                  <span className={`voice-draft-result__val${!val ? ' voice-draft-result__val--missing' : ''}`}>
                    {val ?? '—'}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </Panel>

      {/* Merchant chat — untouched component */}
      <MerchantChatPanel language={language} />
    </section>
  );
}
