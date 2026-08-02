/**
 * Agent Registry
 *
 * Two agent families, one lookup table:
 *
 * 1. PM agents (santi, daniel) — prompts are inline. No canonical .md source
 *    exists for these; they predate the ia-hybrid-teams spec-kit and no
 *    equivalent file was ever authored for them.
 *
 * 2. Spec-kit agents (architect, fullstack-developer, gimena, gabi, gabriela,
 *    ...) — prompts are loaded VERBATIM from ia-hybrid-teams/agents/*.md at
 *    request time. We do not paraphrase or reinvent them: the .md file IS the
 *    system prompt, per ia-hybrid-teams/claude.md rule "no inventar... que no
 *    esté en la documentación".
 *
 *    gimena/gabi/gabriela used to run a simplified inline paraphrase instead
 *    of their real specs (Gimena-userstorywriter.md v1.6, Gabi-workplanner.md
 *    v1.1) — that violated the same verbatim principle applied to every other
 *    spec-kit agent, so they were moved here. gabriela is the one exception:
 *    her canonical file (Gabriela-ProjectBrain.md) is the Project Brain
 *    DOCUMENT TEMPLATE she maintains, not a behavior spec for "being
 *    Gabriela" — loading it as-is as a system prompt would tell the model
 *    "you are a template with blank fields," not "you are Gabriela." She
 *    stays inline, rewritten to require producing output in that template's
 *    exact structure instead of a looser one we made up.
 *
 *    hu-work-planner was retired (2026-08) — it and Gabi-workplanner.md are
 *    the same agent: the file's own body repeatedly self-identifies as
 *    "el agente hu-work-planner" even though the filename says Gabi. Two
 *    registry entries for one job was a real redundancy, not a naming quirk.
 *    Kept as "gabi" since that's what phaseContracts.js already wires into
 *    Fase 1 (Estimación) and Fase 2.
 *
 * SPEC_KIT_AGENTS_DIR must point at the ia-hybrid-teams `agents/` folder (or a
 * copy of it). If a folder isn't reachable, those agents are simply absent from
 * the registry (fail loud at invoke time, not at boot).
 *
 * "external" agents (milestone-writer, dod-definer, capacity-reconciler) are
 * derived from esquema-planeacion.md (Mariana's own reusable planning
 * playbook, outside ia-hybrid-teams) — same verbatim-load mechanism, separate
 * folder since they aren't part of that methodology repo. vic-release-notes
 * (a ported product-specific release-notes agent) was retired 2026-08 in
 * favor of the generic `daniel` — kept as one agent for release notes
 * instead of two with no rule for which to use.
 *
 * MODEL SELECTION: every agent has a declared model tier + max_tokens in
 * AGENT_MODEL_CONFIG below, instead of one hardcoded model for every call.
 * Mechanical/structured output (reports, video-evidence logging) gets haiku
 * and a small cap; planning/writing/judgment work gets sonnet and enough
 * room for a full document. Opus is deliberately not assigned by default
 * anywhere — available as a manual override for a specific high-stakes call,
 * not a standing cost commitment.
 */

const fs = require("fs");
const path = require("path");

const SPEC_KIT_AGENTS_DIR =
  process.env.SPEC_KIT_AGENTS_DIR || path.join(__dirname, "spec-kit-agents");
const EXTERNAL_AGENTS_DIR =
  process.env.EXTERNAL_AGENTS_DIR || path.join(__dirname, "external-agents");

// canon agent_id -> source .md filename (per ia-hybrid-teams/spec-kit/AGENT_REGISTRY.md,
// corrected where the registry doc itself is wrong — see file header)
const SPEC_KIT_FILES = {
  architect: "architect.md",
  "fullstack-developer": "fullstack-developer.md",
  "flutter-developer": "flutter-developer.md",
  "data-engineer": "data-engineer.md",
  auditor: "auditor.md",
  "fixed-errors": "fixed-errors.md",
  gimena: "Gimena-userstorywriter.md",
  gabi: "Gabi-workplanner.md",
  // NOTE: AGENT_REGISTRY.md references "gimena-scheduler.md" but the actual file
  // in agents/ is "Gina-scheduler.md" — this is a pre-existing inconsistency in
  // ia-hybrid-teams itself, not something introduced here. Pointing at the real file.
  "gina-scheduler": "Gina-scheduler.md",
  "qa-integrator": "qa-integrator.md",
  integration: "integration.md",
  "sonar-quality-gate": "sonar-quality-gate.md",
  "mcp-integration-tester": "mcp-integration-tester.md",
  "test-video-recorder": "test-video-recorder.md",
  "unit-test-standards-reviewer": "unit-test-standards-reviewer.md",
  "quality-report-generator": "quality-report-generator.md"
};

const PM_AGENT_PROMPTS = {
  // Gabriela stays inline (see file header for why) but now targets the real
  // V2.0.0 Project Brain template structure (Gabriela-ProjectBrain.md) instead
  // of a looser, made-up section list.
  gabriela: (input, context) => `Eres GABRIELA, guardiana del Project Brain.

Tu responsabilidad es mantener el Project Brain del proyecto siguiendo EXACTAMENTE
la estructura del template canónico (ia-hybrid-teams/agents/Gabriela-ProjectBrain.md,
V2.0.0), no una estructura libre:

1. Strategic Definition & Governance (Executive Summary, Stakeholders and Approvers)
2. Scope Management (Scope Matrix In/Out por módulo)
3. Timeline & Milestones (Start/End Date, Delivery Roadmap con status)
4. Dynamic Knowledge & Meeting Logs (Master Meeting Doc, Change Log / Decision Log)
5. Functional Requirements (Key Characteristics, Critical Business Rules)

IMPORTANTE:
1. Archivo: project_brain_[project_name].md
2. Ante cualquier discrepancia entre este documento y el Decision Log, gana el Decision Log
3. Los agentes gimena/gabi consultan este documento ANTES de cualquier decisión
4. Responde SOLO en JSON

CONTEXTO: ${JSON.stringify(context)}
INPUT: ${input}

Proporciona resumen del Project Brain siguiendo esa estructura de 5 secciones.`,

  // Santi is the on-demand path: paste a raw transcript in the dashboard and get
  // an acta back. The real, automated path is the "Proyecto Actas" Google Apps
  // Script (Calendar → transcript → Gemini → Doc + email draft) — Santi does not
  // run in that flow. What DOES run for both paths is buildActaIngestPrompt()
  // below, which is how either acta's content reaches the Project Brain.
  santi: (input, context) => `Eres SANTI, especialista en documentación de reuniones técnicas.
Tu trabajo es transformar transcripciones en actas profesionales:
- Estructura: Notas (H2/H3) + Action Items ☐ + Alertas + RedFlags
- Formato: H1 (Título), H2 (Secciones), H3 (Numeradas en subsecciones)
- Accionables con ☐ [Tarea] [[Owner] DUE: [Fecha]]
- Output: Acta profesional lista para Google Docs

IMPORTANTE:
1. Lenguaje directo y técnico
2. Prohibido 'X mencionó que'
3. Marca ambigüedades con [POR CONFIRMAR]
4. Responde SOLO en JSON

CONTEXTO: ${JSON.stringify(context)}
INPUT: ${input}

Genera acta de reunión profesional.`,

  daniel: (input, context) => `Eres DANIEL, especialista en Release Notes.
Tu trabajo es generar dos versiones:
1. Bitbucket (Técnico): commits, package versions, contributors
2. Basecamp (Client-friendly): sin términos técnicos

IMPORTANTE:
1. Bitbucket: Incluir todos los commits funcionales
2. Basecamp: Máximo 2-4 oraciones por item, lenguaje plano
3. Responde SOLO en JSON

CONTEXTO: ${JSON.stringify(context)}
INPUT: ${input}

Genera ambas versiones de release notes.`
};

const EXTERNAL_AGENT_FILES = {
  // Derived from esquema-planeacion.md (Mariana's own reusable planning
  // playbook), covering the 3 sub-phases of Planeación (Fase 1 of
  // PHASE_CONTRACTS.md) that had no owning agent: Milestones, DoD, and the
  // scope↔capacity↔date Reconciliation gate. See phaseContracts.js's
  // planningSubPhases for how they chain together.
  "milestone-writer": "milestone-writer.md",
  "dod-definer": "dod-definer.md",
  "capacity-reconciler": "capacity-reconciler.md"
};

// ============================================================================
// MODEL SELECTION — declared per agent, not one hardcoded model for everyone
// ============================================================================

const MODEL_IDS = {
  haiku: "claude-3-5-haiku-20241022",
  sonnet: "claude-3-5-sonnet-20241022"
};

const DEFAULT_MODEL_CONFIG = { tier: "sonnet", maxTokens: 2000 };

// tier: "haiku" for mechanical/structured output (low reasoning, low
// ambiguity); "sonnet" for planning/writing/judgment work. maxTokens sized to
// how long the actual documented output format runs — Gimena/Gabi's real
// specs produce long, multi-section documents; report/log agents don't.
const AGENT_MODEL_CONFIG = {
  gimena: { tier: "sonnet", maxTokens: 4000 },
  gabi: { tier: "sonnet", maxTokens: 4000 },
  gabriela: { tier: "sonnet", maxTokens: 3000 },
  santi: { tier: "sonnet", maxTokens: 2500 },
  daniel: { tier: "sonnet", maxTokens: 3000 },
  architect: { tier: "sonnet", maxTokens: 3000 },
  "fullstack-developer": { tier: "sonnet", maxTokens: 3000 },
  "flutter-developer": { tier: "sonnet", maxTokens: 3000 },
  "data-engineer": { tier: "sonnet", maxTokens: 3000 },
  auditor: { tier: "sonnet", maxTokens: 3000 },
  "fixed-errors": { tier: "sonnet", maxTokens: 2500 },
  "gina-scheduler": { tier: "sonnet", maxTokens: 2500 },
  "qa-integrator": { tier: "sonnet", maxTokens: 2500 },
  integration: { tier: "sonnet", maxTokens: 2500 },
  "sonar-quality-gate": { tier: "sonnet", maxTokens: 2000 },
  "mcp-integration-tester": { tier: "sonnet", maxTokens: 2000 },
  // Mechanical: catalogs/documents evidence that already exists, doesn't
  // reason about quality — haiku + a small cap.
  "test-video-recorder": { tier: "haiku", maxTokens: 1000 },
  "unit-test-standards-reviewer": { tier: "sonnet", maxTokens: 2000 },
  // Mechanical: aggregates already-computed results into a report, doesn't
  // generate new judgment — haiku is enough.
  "quality-report-generator": { tier: "haiku", maxTokens: 1500 },
  "milestone-writer": { tier: "sonnet", maxTokens: 2500 },
  "dod-definer": { tier: "sonnet", maxTokens: 2500 },
  // "El gate más importante" per esquema-planeacion.md — keep sonnet even
  // though it's structured, the lever tradeoffs need real judgment.
  "capacity-reconciler": { tier: "sonnet", maxTokens: 2500 }
};

function getModelConfig(agentId) {
  const config = AGENT_MODEL_CONFIG[agentId] || DEFAULT_MODEL_CONFIG;
  return { model: MODEL_IDS[config.tier], maxTokens: config.maxTokens, tier: config.tier };
}

function loadSpecKitPrompt(agentId) {
  const filename = SPEC_KIT_FILES[agentId];
  if (!filename) return null;

  const filePath = path.join(SPEC_KIT_AGENTS_DIR, filename);
  if (!fs.existsSync(filePath)) {
    throw new Error(
      `Spec-kit agent "${agentId}" registered but source file missing: ${filePath}. ` +
        `Set SPEC_KIT_AGENTS_DIR to your ia-hybrid-teams/agents folder.`
    );
  }
  return fs.readFileSync(filePath, "utf8");
}

function loadExternalPrompt(agentId) {
  const filename = EXTERNAL_AGENT_FILES[agentId];
  if (!filename) return null;

  const filePath = path.join(EXTERNAL_AGENTS_DIR, filename);
  if (!fs.existsSync(filePath)) {
    throw new Error(
      `External agent "${agentId}" registered but source file missing: ${filePath}. ` +
        `Set EXTERNAL_AGENTS_DIR if you moved it.`
    );
  }
  return fs.readFileSync(filePath, "utf8");
}

/**
 * Returns the system prompt + human message for a given agent invocation.
 * Throws if the agent is unknown.
 */
function buildPrompt(agentId, input, context) {
  if (PM_AGENT_PROMPTS[agentId]) {
    return {
      system: null,
      user: PM_AGENT_PROMPTS[agentId](input, context)
    };
  }

  if (SPEC_KIT_FILES[agentId]) {
    const systemPrompt = loadSpecKitPrompt(agentId);
    return {
      system: systemPrompt,
      user: `CONTEXTO: ${JSON.stringify(context || {})}\nINPUT: ${input}\n\nResponde siguiendo estrictamente tu rol, comportamiento y restricciones definidos arriba.`
    };
  }

  if (EXTERNAL_AGENT_FILES[agentId]) {
    const systemPrompt = loadExternalPrompt(agentId);
    return {
      system: systemPrompt,
      user: `CONTEXT: ${JSON.stringify(context || {})}\nINPUT: ${input}\n\nFollow your role and rules exactly as defined above.`
    };
  }

  return null;
}

/**
 * Gabriela's acta-ingestion prompt: given an acta's content (from either Santi
 * or the Proyecto Actas Apps Script), extract decisions → Decision Log and
 * risks/blockers → Alerts. Strict JSON, no invented content when the acta has
 * neither.
 */
function buildActaIngestPrompt(actaContent, metadata) {
  return `Eres GABRIELA, guardiana del Project Brain.

Acaba de generarse un acta de reunión. Tu tarea es analizarla y extraer, en JSON estricto:

1. "decisions": decisiones o acuerdos tomados en la reunión, para el Decision Log del proyecto.
   Cada una: { "decision": "...", "context": "..." }
2. "alerts": riesgos, bloqueos o temas que requieren atención del equipo.
   Cada una: { "alert": "...", "severity": "LOW|MEDIUM|HIGH" }

Si no hay decisiones o alertas claras en el acta, devuelve arrays vacíos. No inventes
contenido que no esté explícito o claramente implícito en el acta.

METADATA:
${JSON.stringify(metadata || {}, null, 2)}

CONTENIDO DEL ACTA:
${actaContent}

Responde SOLO con este JSON, sin texto adicional:
{
  "decisions": [{ "decision": "...", "context": "..." }],
  "alerts": [{ "alert": "...", "severity": "LOW|MEDIUM|HIGH" }]
}`;
}

function listAgents() {
  return [
    ...Object.keys(PM_AGENT_PROMPTS).map((id) => ({ id, family: "pm" })),
    ...Object.keys(SPEC_KIT_FILES).map((id) => ({ id, family: "spec-kit" })),
    ...Object.keys(EXTERNAL_AGENT_FILES).map((id) => ({ id, family: "external" }))
  ];
}

function isKnownAgent(agentId) {
  return !!(PM_AGENT_PROMPTS[agentId] || SPEC_KIT_FILES[agentId] || EXTERNAL_AGENT_FILES[agentId]);
}

module.exports = {
  buildPrompt,
  buildActaIngestPrompt,
  getModelConfig,
  listAgents,
  isKnownAgent,
  SPEC_KIT_AGENTS_DIR,
  EXTERNAL_AGENTS_DIR
};
