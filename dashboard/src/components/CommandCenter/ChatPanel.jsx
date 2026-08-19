import React, { useEffect, useRef, useState } from "react";
import ApiClient from "../../api-client.js";
import { AlertIcon } from "../icons.jsx";
import "./command-center.css";

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

// Real system-wide reconciliation alerts + gap total for the status rail's
// "Sistema" group — same computation AnalyticsDrillDown already uses
// (reconciliationRuns[].gaps_found), never a fabricated number.
function useSystemRailData(api) {
  const [reconciliationRuns, setReconciliationRuns] = useState([]);

  useEffect(() => {
    if (!api) return;
    api
      .getMetricsSummary()
      .then((summary) => setReconciliationRuns(summary.reconciliationRuns || []))
      .catch(() => setReconciliationRuns([]));
  }, [api]);

  const gapsTotal = reconciliationRuns.reduce((acc, r) => acc + (r.gaps_found || 0), 0);
  const alerts = reconciliationRuns.filter((r) => (r.gaps_found || 0) > 0).slice(-5);
  return { gapsTotal, alerts };
}

function StatusRail({ api, purpose, turnCount, tokenCount }) {
  const { gapsTotal, alerts } = useSystemRailData(api);
  return (
    <aside className="chat-status-rail">
      <div className="rail-group session">
        <div className="rail-group-label">Esta conversación</div>
        <div className="rail-group-sub">{purpose}</div>
        <div className="rail-metric-grid">
          <div className="rail-card">
            <div className="rail-metric-value">{turnCount}</div>
            <div className="rail-metric-label">Turnos</div>
          </div>
          <div className="rail-card">
            <div className="rail-metric-value">{tokenCount > 0 ? tokenCount.toLocaleString("es") : "0"}</div>
            <div className="rail-metric-label">Tokens usados</div>
          </div>
        </div>
      </div>
      <div className="rail-group">
        <div className="rail-group-label">Sistema (todos los proyectos)</div>
        <div className="rail-metric-grid" style={{ marginBottom: 14 }}>
          <div className="rail-card">
            <div className="rail-metric-value rail-metric-empty">—</div>
            <div className="rail-metric-label">Uso hoy</div>
          </div>
          <div className="rail-card">
            <div className="rail-metric-value">{gapsTotal}</div>
            <div className="rail-metric-label">Gaps totales</div>
          </div>
        </div>
        <div className="rail-section-label">Alertas de reconciliación</div>
        <div className="rail-alert-list">
          {alerts.length === 0 && <div className="rail-alert-text">Sin alertas abiertas.</div>}
          {alerts.map((run, i) => (
            <div key={i} className="rail-alert-row">
              <span className="pill pill-red">
                <span className="pill-dot" />
                {run.gaps_found} gaps
              </span>
              <span className="rail-alert-text">{run.project_id || run.project_name || "—"}</span>
            </div>
          ))}
        </div>
      </div>
    </aside>
  );
}

// Turns a full ChatSession's `turns` (role_user_message + assistant_message
// pairs, snake_case from the backend) back into the flat message list the
// UI renders — used when switching into an existing tab.
function turnsToMessages(turns) {
  const messages = [];
  for (const turn of turns || []) {
    messages.push({ id: `${turn.id}-u`, role: "user", text: turn.role_user_message ?? turn.roleUserMessage ?? "" });
    messages.push({
      id: turn.id,
      role: "jarvis",
      text: turn.assistant_message ?? turn.assistantMessage ?? "",
      sources: turn.sources_cited ?? turn.sourcesCited ?? [],
      declaredUnknown: turn.declared_unknown ?? turn.declaredUnknown ?? false
    });
  }
  return messages;
}

function sessionTokenTotal(turns) {
  return (turns || []).reduce(
    (acc, t) => acc + (t.input_tokens ?? t.inputTokens ?? 0) + (t.output_tokens ?? t.outputTokens ?? 0),
    0
  );
}

export default function ChatPanel({ api: apiProp, projects = [] } = {}) {
  const [messages, setMessages] = useState([]); // { id, role: 'user'|'jarvis', text, sources?, declaredUnknown? }
  const [input, setInput] = useState("");
  const [conversationId, setConversationId] = useState(null);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState("");
  const [tokenTotal, setTokenTotal] = useState(0);
  // SPEC_JARVIS.md §11: sessions must start and end deliberately in the UI,
  // not implicitly on the first/last message. `purposeDraft` is the pending
  // "why are you opening this session" answer required before any message
  // can be sent; `sessionEnded` locks the panel once "Terminar sesión" fires,
  // forcing a fresh purpose (and thus a fresh conversation_id) to continue.
  const [purposeDraft, setPurposeDraft] = useState("");
  const [pendingPurpose, setPendingPurpose] = useState(null);
  const [pendingProjectId, setPendingProjectId] = useState("");
  const [isEndingSession, setIsEndingSession] = useState(false);
  const [sessionEnded, setSessionEnded] = useState(false);
  // Real chat-tabs bar (mockup fidelity, 2026-08-19): open sessions listed
  // via GET /jarvis/sessions, switching tabs loads that session's real
  // turns via GET /jarvis/sessions/{id} — never a client-only fake tab.
  const [sessions, setSessions] = useState([]);
  const scrollRef = useRef(null);
  const apiRef = useRef(null);

  if (apiProp) {
    apiRef.current = apiProp;
  } else if (!apiRef.current) {
    const appKey = localStorage.getItem(STORAGE_KEY) || "";
    apiRef.current = new ApiClient(appKey);
  }

  const loadSessions = () => {
    apiRef.current
      .listChatSessions("open")
      .then(setSessions)
      .catch(() => setSessions([]));
  };

  useEffect(() => {
    loadSessions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isSending]);

  const projectName = (projectId) => projects.find((p) => p.id === projectId)?.name || projectId;

  const handleNewTab = () => {
    setSessionEnded(false);
    setMessages([]);
    setConversationId(null);
    setPendingPurpose(null);
    setPurposeDraft("");
    setPendingProjectId("");
    setTokenTotal(0);
    setError("");
  };

  const handleSwitchTab = async (session) => {
    setError("");
    try {
      const full = await apiRef.current.getChatSession(session.id);
      setConversationId(full.id);
      setPendingPurpose(full.purpose);
      setPendingProjectId(full.project_id ?? full.projectId ?? "");
      setMessages(turnsToMessages(full.turns));
      setTokenTotal(sessionTokenTotal(full.turns));
      setSessionEnded(false);
    } catch (err) {
      setError(err.message || "No se pudo cargar esa conversación.");
    }
  };

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
    setTokenTotal(0);
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
      loadSessions();
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
      const isNewSession = !conversationId;
      const response = await apiRef.current.sendChatMessage(conversationId, text, purpose, pendingProjectId);
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
      const turnTokens = (turn.input_tokens ?? turn.inputTokens ?? 0) + (turn.output_tokens ?? turn.outputTokens ?? 0);
      setTokenTotal((prev) => prev + turnTokens);
      if (isNewSession) loadSessions();
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

  const isNewTabActive = !conversationId;
  const tabsBar = (
    <div className="chat-tabs">
      {sessions.map((session) => (
        <button
          key={session.id}
          className={`chat-tab ${session.id === conversationId ? "active" : ""}`}
          onClick={() => handleSwitchTab(session)}
        >
          {session.project_id && <span className="chat-tab-project">{projectName(session.project_id)}</span>}
          {session.purpose}
        </button>
      ))}
      <button
        className={`chat-tab chat-tab-new ${isNewTabActive ? "active" : ""}`}
        onClick={handleNewTab}
        title="Nueva conversación"
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 5v14M5 12h14" />
        </svg>
      </button>
    </div>
  );

  // No active/pending session yet, or the previous one was explicitly ended
  // — force naming a purpose before any message can go out.
  if (!conversationId && pendingPurpose === null) {
    return (
      <div className="chat-panel">
        {tabsBar}
        <div className="chat-history chat-history-empty">
          <div className="chat-empty-state">
            {sessionEnded
              ? "Sesión anterior terminada. Dale un propósito a la nueva conversación para empezar."
              : "Antes de empezar, dale un propósito a esta conversación con Jarvis."}
          </div>
        </div>
        {error && <div className="flag">{AlertIcon} {error}</div>}
        {projects.length > 0 && (
          <div className="chat-project-picker">
            <label>Proyecto (opcional)</label>
            <select value={pendingProjectId} onChange={(e) => setPendingProjectId(e.target.value)}>
              <option value="">Sin proyecto puntual</option>
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name || p.id}
                </option>
              ))}
            </select>
          </div>
        )}
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

  const turnCount = messages.filter((m) => m.role === "jarvis").length;

  return (
    <div className="chat-panel">
      {tabsBar}
      <div className="chat-panel-toolbar">
        <span className="chat-panel-purpose">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 2a5 5 0 015 5v3a5 5 0 01-10 0V7a5 5 0 015-5z" />
            <path d="M19 10v2a7 7 0 01-14 0v-2M12 19v3" />
          </svg>
          Propósito: {pendingPurpose || "—"}
        </span>
        <button
          type="button"
          className="chat-end-button"
          onClick={handleEndSession}
          disabled={!conversationId || isEndingSession}
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="5" y="5" width="14" height="14" rx="2" />
          </svg>
          {isEndingSession ? "Terminando..." : "Terminar sesión"}
        </button>
      </div>

      <div className="chat-body">
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

        <StatusRail api={apiRef.current} purpose={pendingPurpose || "—"} turnCount={turnCount} tokenCount={tokenTotal} />
      </div>

      {error && <div className="flag">{AlertIcon} {error}</div>}

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
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" />
          </svg>
          Enviar
        </button>
      </div>
    </div>
  );
}
