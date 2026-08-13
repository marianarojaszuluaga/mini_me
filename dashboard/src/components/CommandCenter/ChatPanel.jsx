import React, { useEffect, useRef, useState } from "react";
import ApiClient from "../../api-client.js";

// Same key App.jsx uses to persist the app API key (localStorage) — ChatPanel
// isn't handed an `api` instance as a prop today (CommandCenterLayout is
// mounted as <CommandCenterLayout header={<Header />} /> with no api prop),
// so it builds its own ApiClient from the same stored key rather than
// inventing a new auth path.
const STORAGE_KEY = "ORQ_APP_KEY";

const KIND_LABELS = {
  project_brain: "Cerebro del proyecto",
  timeline: "Timeline",
  reconciliation: "Reconciliación",
  agent_invocation: "Invocación de agente",
  mar_memory: "Memoria de Mar",
  none: "Sin fuente"
};

function SourceList({ sources }) {
  if (!sources || sources.length === 0 || sources.every((s) => s.kind === "none")) {
    return null;
  }
  return (
    <div className="chat-sources">
      <div className="chat-sources-label">Fuentes citadas</div>
      <ul className="chat-sources-list">
        {sources
          .filter((s) => s.kind !== "none")
          .map((source, i) => (
            <li key={i} className="chat-source-item">
              <span className="chat-source-kind">{KIND_LABELS[source.kind] || source.kind}</span>
              {source.ref && <span className="chat-source-ref">{source.ref}</span>}
              {source.excerpt && <span className="chat-source-excerpt">{source.excerpt}</span>}
            </li>
          ))}
      </ul>
    </div>
  );
}

export default function ChatPanel({ api: apiProp } = {}) {
  const [messages, setMessages] = useState([]); // { id, role: 'user'|'jarvis', text, sources?, declaredUnknown? }
  const [input, setInput] = useState("");
  const [conversationId, setConversationId] = useState(null);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState("");
  // SPEC_JARVIS.md §11: sessions must start and end deliberately in the UI,
  // not implicitly on the first/last message. `purposeDraft` is the pending
  // "why are you opening this session" answer required before any message
  // can be sent; `sessionEnded` locks the panel once "Terminar sesión" fires,
  // forcing a fresh purpose (and thus a fresh conversation_id) to continue.
  const [purposeDraft, setPurposeDraft] = useState("");
  const [pendingPurpose, setPendingPurpose] = useState(null);
  const [isEndingSession, setIsEndingSession] = useState(false);
  const [sessionEnded, setSessionEnded] = useState(false);
  const scrollRef = useRef(null);
  const apiRef = useRef(null);

  if (apiProp) {
    apiRef.current = apiProp;
  } else if (!apiRef.current) {
    const appKey = localStorage.getItem(STORAGE_KEY) || "";
    apiRef.current = new ApiClient(appKey);
  }

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isSending]);

  const handleStartSession = () => {
    const purpose = purposeDraft.trim();
    if (!purpose) return;
    // Opening is itself deliberate — no message sent yet, no conversationId
    // minted yet either. The first real POST /jarvis/chat (in handleSend)
    // is what actually creates the session, carrying this purpose.
    setSessionEnded(false);
    setMessages([]);
    setConversationId(null);
    setPendingPurpose(purpose);
    setPurposeDraft("");
  };

  const handleEndSession = async () => {
    if (!conversationId || isEndingSession) return;
    setIsEndingSession(true);
    setError("");
    try {
      await apiRef.current.closeChatSession(conversationId);
      setSessionEnded(true);
      setConversationId(null);
      setPendingPurpose(null);
    } catch (err) {
      setError(err.message || "Error al terminar la sesión.");
    } finally {
      setIsEndingSession(false);
    }
  };

  const handleSend = async () => {
    const text = input.trim();
    if (!text || isSending || sessionEnded) return;
    if (!conversationId && !pendingPurpose) return; // must start a session first

    const userMessage = { id: `u-${Date.now()}`, role: "user", text };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setError("");
    setIsSending(true);

    try {
      // Purpose only travels on the message that actually opens the
      // session (conversationId still null) — every later message on the
      // same session must NOT resend it, since session_manager treats
      // conversation_id + purpose as "open a new one".
      const purpose = conversationId ? undefined : pendingPurpose;
      const response = await apiRef.current.sendChatMessage(conversationId, text, purpose);
      // Shape per app/schemas/chat.py ChatTurnResponse: { conversationId, version,
      // turn: { assistantMessage, sourcesCited, declaredUnknown }, sessionStatus,
      // newConversationId }. The FastAPI models are snake_case in Python but the
      // dashboard's existing ApiClient methods assume the JSON body already
      // matches what's read here — falling back across camelCase/snake_case
      // keys since we can't confirm the JSON alias config from the frontend side.
      const turn = response.turn || {};
      const assistantText =
        turn.assistantMessage ?? turn.assistant_message ?? "(sin respuesta)";
      const sources = turn.sourcesCited ?? turn.sources_cited ?? [];
      const declaredUnknown = turn.declaredUnknown ?? turn.declared_unknown ?? false;
      const newConversationId =
        response.conversationId ?? response.conversation_id ?? conversationId;

      setConversationId(newConversationId);
      setMessages((prev) => [
        ...prev,
        {
          id: turn.id || `j-${Date.now()}`,
          role: "jarvis",
          text: assistantText,
          sources,
          declaredUnknown
        }
      ]);
    } catch (err) {
      setError(err.message || "Error al enviar el mensaje a Jarvis.");
    } finally {
      setIsSending(false);
    }
  };

  const handleKeyDown = (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSend();
    }
  };

  const handlePurposeKeyDown = (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleStartSession();
    }
  };

  // No active/pending session yet, or the previous one was explicitly ended
  // — force naming a purpose before any message can go out.
  if (!conversationId && pendingPurpose === null) {
    return (
      <div className="chat-panel">
        <div className="chat-history chat-history-empty">
          <div className="chat-empty-state">
            {sessionEnded
              ? "Sesión anterior terminada. Dale un propósito a la nueva conversación para empezar."
              : "Antes de empezar, dale un propósito a esta conversación con Jarvis."}
          </div>
        </div>
        {error && <div className="flag">⚠️ {error}</div>}
        <div className="chat-input-row">
          <textarea
            className="chat-input"
            value={purposeDraft}
            onChange={(event) => setPurposeDraft(event.target.value)}
            onKeyDown={handlePurposeKeyDown}
            placeholder="Ej.: revisar el estado del sprint actual"
            rows={2}
          />
          <button
            type="button"
            className="chat-send-button"
            onClick={handleStartSession}
            disabled={!purposeDraft.trim()}
          >
            Iniciar sesión
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="chat-panel">
      <div className="chat-panel-toolbar">
        <span className="chat-panel-purpose">Propósito: {pendingPurpose || "—"}</span>
        <button
          type="button"
          className="chat-end-button"
          onClick={handleEndSession}
          disabled={!conversationId || isEndingSession}
        >
          {isEndingSession ? "Terminando..." : "Terminar sesión"}
        </button>
      </div>
      <div className="chat-history" ref={scrollRef}>
        {messages.length === 0 && (
          <div className="chat-empty-state">Pregúntale algo a Jarvis sobre tus proyectos.</div>
        )}
        {messages.map((message) => (
          <div
            key={message.id}
            className={`chat-message chat-message-${message.role}`}
          >
            <div className="chat-message-author">
              {message.role === "user" ? "Tú" : "Jarvis"}
            </div>
            <div className="chat-message-text">{message.text}</div>
            {message.role === "jarvis" && message.declaredUnknown && (
              <div className="chat-message-unknown">Jarvis indicó que no tiene información suficiente.</div>
            )}
            {message.role === "jarvis" && <SourceList sources={message.sources} />}
          </div>
        ))}
        {isSending && (
          <div className="chat-message chat-message-jarvis chat-message-typing">
            <div className="chat-message-author">Jarvis</div>
            <div className="chat-message-text">escribiendo...</div>
          </div>
        )}
      </div>

      {error && <div className="flag">⚠️ {error}</div>}

      <div className="chat-input-row">
        <textarea
          className="chat-input"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Escribe tu pregunta para Jarvis..."
          rows={2}
          disabled={isSending}
        />
        <button
          type="button"
          className="chat-send-button"
          onClick={handleSend}
          disabled={isSending || !input.trim()}
        >
          Enviar
        </button>
      </div>
    </div>
  );
}
