import { Bot } from "lucide-react";
import { useState } from "react";
import { MerchantChatPanel } from "../components/ai/MerchantChatPanel";
import { Panel } from "../components/Layout";
import { aiVoiceDrafts } from "../lib/api";
import { humanizeError } from "../lib/errors";
import { t } from "../lib/i18n";
import type { Language, VoiceDraft } from "../lib/types";

interface Props { language: Language }

export function AIPage({ language }: Props) {
  const tr = (key: Parameters<typeof t>[1]) => t(language, key);
  const [transcript, setTranscript] = useState("على Ahmed 25 SAR groceries due 2026-05-01");
  const [voiceDraft, setVoiceDraft] = useState<VoiceDraft | null>(null);
  const [message, setMessage] = useState("");

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
      {message && <div className="message wide-panel">{message}</div>}
      <Panel title={tr("voiceTranscript")}>
        <textarea value={transcript} onChange={(e) => setTranscript(e.target.value)} />
        <button className="primary-button" onClick={() => void draftFromVoice()}>
          <Bot size={18} /><span>{tr("draft")}</span>
        </button>
        {voiceDraft && <pre>{JSON.stringify(voiceDraft, null, 2)}</pre>}
      </Panel>
      <MerchantChatPanel language={language} />
    </section>
  );
}
