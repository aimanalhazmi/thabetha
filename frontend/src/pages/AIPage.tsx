import { Bot } from "lucide-react";
import { useState } from "react";
import { Panel } from "../components/Layout";
import { apiRequest } from "../lib/api";
import { t } from "../lib/i18n";
import type { Language, VoiceDraft } from "../lib/types";

interface Props { language: Language }

export function AIPage({ language }: Props) {
  const tr = (key: Parameters<typeof t>[1]) => t(language, key);
  const [transcript, setTranscript] = useState("على Ahmed 25 SAR groceries due 2026-05-01");
  const [voiceDraft, setVoiceDraft] = useState<VoiceDraft | null>(null);
  const [chatMessage, setChatMessage] = useState("Give me overdue summary");
  const [chatAnswer, setChatAnswer] = useState("");
  const [message, setMessage] = useState("");

  async function draftFromVoice() {
    try {
      const draft = await apiRequest<VoiceDraft>("/ai/debt-draft-from-voice", { method: "POST", body: JSON.stringify({ transcript, default_currency: "SAR" }) });
      setVoiceDraft(draft);
      setMessage("Draft extracted");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Failed");
    }
  }

  async function askChatbot() {
    try {
      const resp = await apiRequest<{ answer: string }>("/ai/merchant-chat", { method: "POST", body: JSON.stringify({ message: chatMessage }) });
      setChatAnswer(resp.answer);
      setMessage("Summary ready");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Failed");
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
      <Panel title={tr("askMerchantBot")}>
        <textarea value={chatMessage} onChange={(e) => setChatMessage(e.target.value)} />
        <button className="primary-button" onClick={() => void askChatbot()}>
          <Bot size={18} /><span>{tr("askMerchantBot")}</span>
        </button>
        {chatAnswer && <p className="answer">{chatAnswer}</p>}
      </Panel>
    </section>
  );
}
