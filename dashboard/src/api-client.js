/**
 * ApiClient — Orquestrador 360 Dashboard
 *
 * Talks to the MAP server (backend FastAPI, single process; all routes
 * unprefixed except the Orchestrator which lives under /orchestrator/*)
 * via an app-issued API key (Bearer token). This is NOT the Anthropic key.
 *
 * Extracted from App.jsx so other screens/components can import it directly:
 *   import ApiClient from "./api-client.js";
 */

export default class ApiClient {
  constructor(apiKey) {
    this.apiKey = apiKey;
    this.baseUrl = import.meta.env.VITE_API_URL || "http://localhost:3001";
  }

  async request(path, options = {}) {
    const response = await fetch(`${this.baseUrl}${path}`, {
      ...options,
      headers: {
        Authorization: `Bearer ${this.apiKey}`,
        "Content-Type": "application/json",
        ...(options.headers || {})
      }
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      // BUG-011 fix: FastAPI's HTTPException always serializes as
      // {"detail": "..."} — the old `body.error` lookup never matched,
      // so users only ever saw the generic fallback message.
      throw new Error(body.detail || body.error || `${path} failed (${response.status})`);
    }
    return response.json();
  }

  // ---- existing (kept identical to preserve current behavior) ----

  getPhases() {
    return this.request("/phases");
  }

  getAgents() {
    return this.request("/agents");
  }

  getProjects() {
    return this.request("/projects");
  }

  getProject(id) {
    return this.request(`/projects/${id}`);
  }

  createProject(data) {
    return this.request("/projects", { method: "POST", body: JSON.stringify(data) });
  }

  linkBasecampProject(projectId, accountId, basecampProjectId) {
    return this.request(`/projects/${projectId}/basecamp`, {
      method: "PUT",
      body: JSON.stringify({ account_id: accountId, project_id: basecampProjectId })
    });
  }

  unlinkBasecampProject(projectId) {
    return this.request(`/projects/${projectId}/basecamp`, { method: "DELETE" });
  }

  getProjectSprint(projectId) {
    return this.request(`/projects/${projectId}/sprint`);
  }

  invokeAgent(agentName, projectId, input, context) {
    return this.request(`/agents/${agentName}/invoke`, {
      method: "POST",
      body: JSON.stringify({ projectId, input, context })
    });
  }

  evaluate(agentName, output, context) {
    return this.request("/evaluate", {
      method: "POST",
      body: JSON.stringify({ agentName, output, context })
    });
  }

  // ---- new: repositories ----

  listProjectRepositories(projectId) {
    return this.request(`/projects/${projectId}/repositories`);
  }

  connectRepository(projectId, data) {
    return this.request(`/projects/${projectId}/repositories`, {
      method: "POST",
      body: JSON.stringify(data)
    });
  }

  // BUG-009: real retry — same sync the connect-time digest and the 3h
  // cron use, not a UI-only "looks retried" state.
  retryRepositorySync(projectId, repoId) {
    return this.request(`/projects/${projectId}/repositories/${repoId}/sync`, {
      method: "POST"
    });
  }

  addRepositoryBranch(projectId, repoId, branch) {
    return this.request(`/projects/${projectId}/repositories/${repoId}/branches`, {
      method: "POST",
      body: JSON.stringify({ branch })
    });
  }

  // ---- new: auth profiles ----

  listAuthProfiles() {
    return this.request("/auth-profiles");
  }

  createAuthProfile(data) {
    return this.request("/auth-profiles", { method: "POST", body: JSON.stringify(data) });
  }

  // ---- new: timeline ----

  getTimeline(projectId) {
    return this.request(`/projects/${projectId}/timeline`);
  }

  // ---- new: reconciliation ----

  getReconciliation(projectId) {
    return this.request(`/projects/${projectId}/reconciliation`);
  }

  runReconciliation(projectId) {
    return this.request(`/projects/${projectId}/reconciliation/run`, { method: "POST" });
  }

  // ---- new: jarvis chat ----

  sendChatMessage(conversationId, message, purpose, projectId) {
    // BUG-004 fix: app/schemas/chat.py::ChatRequest is snake_case with no
    // alias_generator, and `purpose` is mandatory for a brand-new session
    // (session_manager.open_or_resume raises 400 "purpose is required"
    // otherwise) — both were missing from this call.
    return this.request("/jarvis/chat", {
      method: "POST",
      body: JSON.stringify({
        conversation_id: conversationId,
        message,
        ...(conversationId ? {} : { purpose, project_id: projectId || undefined })
      })
    });
  }

  closeChatSession(conversationId) {
    return this.request(`/jarvis/chat/${conversationId}/close`, { method: "POST" });
  }

  listChatSessions(status = "open") {
    return this.request(`/jarvis/sessions?status=${encodeURIComponent(status)}`);
  }

  getChatSession(conversationId) {
    return this.request(`/jarvis/sessions/${conversationId}`);
  }

  // ---- new: Mar memory ----

  listMarMemory() {
    return this.request("/mar/memory");
  }

  upsertMarMemoryEntry(entry) {
    return this.request("/mar/memory", { method: "POST", body: JSON.stringify(entry) });
  }

  deleteMarMemoryEntry(id) {
    return this.request(`/mar/memory/${id}`, { method: "DELETE" });
  }

  // ---- new: metrics ----

  getMetricsSummary(projectId) {
    return this.request(`/metrics/summary${projectId ? `?project_id=${encodeURIComponent(projectId)}` : ""}`);
  }

  getAgentEvaluations() {
    return this.request("/metrics/agent-evaluations");
  }

  getReconciliationRuns() {
    return this.request("/metrics/reconciliation-runs");
  }

  getUsageEvents() {
    return this.request("/metrics/usage-events");
  }

  getOutputCounts() {
    return this.request("/metrics/output-counts");
  }

  getMetricsEvents(filters = {}) {
    const query = new URLSearchParams(filters).toString();
    return this.request(`/metrics/events${query ? `?${query}` : ""}`);
  }

  // ---- new: changelog ----

  listChangelog() {
    return this.request("/changelog");
  }

  approveChangelogEntry(id) {
    return this.request(`/changelog/${id}/approve`, { method: "POST" });
  }
}
