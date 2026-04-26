import { Bot, ExternalLink } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Panel } from "../components/Layout";
import { useToast } from "../contexts/ToastContext";
import { apiRequest } from "../lib/api";
import { t } from "../lib/i18n";
import type { Language, VoiceDraft } from "../lib/types";

interface Props { language: Language }

export function AIPage({ language }: Props) {
  const tr = (key: Parameters<typeof t>[1]) => t(language, key);
  const { showToast } = useToast();
  const navigate = useNavigate();

  const [transcript, setTranscript] = useState(
    language === "ar" ? "على Ahmed مبلغ 25 ريال بقالة تاريخ الاستحقاق 2026-05-01" : "Ahmed owes 25 SAR groceries due 2026-05-01"
  );
  const [voiceDraft, setVoiceDraft] = useState<VoiceDraft | null>(null);
  const [draftLoading, setDraftLoading] = useState(false);

  const [chatMessage, setChatMessage] = useState(
    language === "ar" ? "أعطني ملخص الديون المتأخرة" : "Give me overdue summary"
  );
  const [chatAnswer, setChatAnswer] = useState("");
  const [chatLoading, setChatLoading] = useState(false);

  async function draftFromVoice() {
    setDraftLoading(true);
    setVoiceDraft(null);
    try {
      const draft = await apiRequest<VoiceDraft>("/ai/debt-draft-from-voice", {
        method: "POST",
        body: JSON.stringify({ transcript, default_currency: "SAR" }),
      });
      setVoiceDraft(draft);
      showToast(language === "ar" ? "تم استخراج المسودة" : "Draft extracted", "success");
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Failed", "error");
    } finally {
      setDraftLoading(false);
    }
  }

  async function askChatbot() {
    setChatLoading(true);
    setChatAnswer("");
    try {
      const resp = await apiRequest<{ answer: string }>("/ai/merchant-chat", {
        method: "POST",
        body: JSON.stringify({ message: chatMessage }),
      });
      setChatAnswer(resp.answer);
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Failed", "error");
    } finally {
      setChatLoading(false);
    }
  }

  function useDraft() {
    if (!voiceDraft) return;
    navigate("/debts", { state: { draftDebt: voiceDraft } });
  }

  return (
    <section className="split">
      {/* Voice → Draft */}
      <Panel title={tr("voiceTranscript")}>
        <p style={{ fontSize: "0.82rem", color: "var(--text-secondary)", marginBottom: "4px" }}>
          {language === "ar"
            ? "اكتب جملة بالعربية أو الإنجليزية لاستخراج بيانات الدين تلقائياً."
            : "Type a sentence to extract debt details automatically."}
        </p>
        <textarea
          value={transcript}
          onChange={(e) => setTranscript(e.target.value)}
          rows={3}
        />
        <button
          className="primary-button"
          disabled={draftLoading || !transcript.trim()}
          onClick={() => void draftFromVoice()}
        >
          <Bot size={18} />
          <span>{draftLoading ? "..." : tr("draft")}</span>
        </button>

        {voiceDraft && (
          <div className="draft-card">
            <div className="draft-card-header">
              <strong>{language === "ar" ? "المسودة المستخرجة" : "Extracted Draft"}</strong>
              <span className="confidence-badge" style={{
                background: voiceDraft.confidence >= 0.8
                  ? "var(--success-light)"
                  : voiceDraft.confidence >= 0.5
                    ? "var(--warning-light)"
                    : "var(--danger-light)",
                color: voiceDraft.confidence >= 0.8
                  ? "#047857"
                  : voiceDraft.confidence >= 0.5
                    ? "#b45309"
                    : "#b91c1c",
              }}>
                {tr("confidence")}: {Math.round(voiceDraft.confidence * 100)}%
              </span>
            </div>

            <div className="draft-fields">
              {voiceDraft.debtor_name && (
                <div className="draft-field">
                  <span>{tr("debtorName")}</span>
                  <strong>{voiceDraft.debtor_name}</strong>
                </div>
              )}
              {voiceDraft.amount && (
                <div className="draft-field">
                  <span>{tr("amount")}</span>
                  <strong>{voiceDraft.amount} {voiceDraft.currency}</strong>
                </div>
              )}
              {voiceDraft.description && (
                <div className="draft-field">
                  <span>{tr("description")}</span>
                  <strong>{voiceDraft.description}</strong>
                </div>
              )}
              {voiceDraft.due_date && (
                <div className="draft-field">
                  <span>{tr("dueDate")}</span>
                  <strong>{voiceDraft.due_date}</strong>
                </div>
              )}
            </div>

            <button className="primary-button" onClick={useDraft} style={{ marginTop: "8px" }}>
              <ExternalLink size={16} />
              <span>{tr("useDraft")}</span>
            </button>
          </div>
        )}
      </Panel>

      {/* Merchant chatbot */}
      <Panel title={tr("askMerchantBot")}>
        <p style={{ fontSize: "0.82rem", color: "var(--text-secondary)", marginBottom: "4px" }}>
          {language === "ar"
            ? "اسأل عن ديونك ومستحقاتك بلغة طبيعية."
            : "Ask about your debts and receivables in natural language."}
        </p>
        <textarea
          value={chatMessage}
          onChange={(e) => setChatMessage(e.target.value)}
          rows={3}
        />
        <button
          className="primary-button"
          disabled={chatLoading || !chatMessage.trim()}
          onClick={() => void askChatbot()}
        >
          <Bot size={18} />
          <span>{chatLoading ? "..." : tr("askMerchantBot")}</span>
        </button>
        {chatAnswer && (
          <div className="chat-answer">
            <p>{chatAnswer}</p>
          </div>
        )}
      </Panel>
    </section>
  );
}
