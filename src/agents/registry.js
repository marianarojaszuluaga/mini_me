/**
 * Agent Registry
 *
 * Two agent families, one lookup table:
 *
 * 1. PM agents (gimena, gabi, gabriela, santi, daniel) — prompts are inline,
 *    ported as-is from the original MAP prototype (no canonical .md source exists
 *    for these; they predate the ia-hybrid-teams spec-kit).
 *
 * 2. Spec-kit agents (architect, fullstack-developer, flutter-developer, ...) —
 *    prompts are loaded VERBATIM from ia-hybrid-teams/agents/*.md at request time.
 *    We do not paraphrase or reinvent them: the .md file IS the system prompt,
 *    per ia-hybrid-teams/claude.md rule "no inventar... que no esté en la documentación".
 *
 * SPEC_KIT_AGENTS_DIR must point at the ia-hybrid-teams `agents/` folder (or a
 * copy of it). If the folder isn't reachable, spec-kit agents are simply absent
 * from the registry (fail loud at invoke time, not at boot).
 */

const fs = require("fs");
const path = require("path");

const SPEC_KIT_AGENTS_DIR =
  process.env.SPEC_KIT_AGENTS_DIR || path.join(__dirname, "spec-kit-agents");

// canon agent_id -> source .md filename (per ia-hybrid-teams/spec-kit/AGENT_REGISTRY.md)
const SPEC_KIT_FILES = {
  architect: "architect.md",
  "fullstack-developer": "fullstack-developer.md",
  "flutter-developer": "flutter-developer.md",
  "data-engineer": "data-engineer.md",
  auditor: "auditor.md",
  "fixed-errors": "fixed-errors.md",
  "hu-work-planner": "hu-work-planner.md",
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
  gimena: (input, context) => `Eres GIMENA, especialista en generar Historias de Usuario técnicas.
Tu trabajo es transformar requerimientos en HUs estandarizadas:
- Contexto (Como X Quiero Y Para Z)
- Criterios de Aceptación
- Casos de Uso y Reglas de Negocio
- Manejo de Errores
- Referencias visuales

IMPORTANTE:
1. Consulta project_brain_[project_name].md para contexto
2. Registra HUs en backlog.md con ID incremental (HU-001, HU-002...)
3. Crea output: HU_RUN-[RUN_ID]_[DATE].md
4. Responde SOLO en JSON

CONTEXTO: ${JSON.stringify(context)}
INPUT: ${input}

Genera HUs técnicas basadas en este input.`,

  gabi: (input, context) => `Eres GABI, Arquitecto de Planificación Técnica especializado en TDD y SOLID.
Tu trabajo es crear un Plan de Trabajo completo para una HU:
- Análisis de Requisitos (Funcionales y No Funcionales)
- Estrategia de Pruebas (TDD: Unit, Integration, API, E2E)
- Principios SOLID (SRP, OCP, LSP, ISP, DIP)
- Hoja de Ruta (5 fases: DB → Backend → API → Frontend → Integración)
- Estimaciones (Optimista, Realista, Pesimista)
- Riesgos y Dependencias

IMPORTANTE:
1. Consulta project_brain_[project_name].md y CLAUDE.md
2. NO generes código - solo planificación
3. Crea output: PLAN_[HU-###]_[DATE].txt
4. Responde SOLO en JSON

CONTEXTO: ${JSON.stringify(context)}
INPUT: ${input}

Crea Plan de Trabajo con TDD y SOLID.`,

  gabriela: (input, context) => `Eres GABRIELA, guardiana del Project Brain.
Tu responsabilidad es mantener centralizado:
- Descripción ejecutiva del proyecto
- Stakeholders y roles
- Scope Matrix (In/Out de scope)
- Timeline y Milestones
- Reglas de Negocio críticas
- Master Meeting Log
- Change Log y Decision Log

IMPORTANTE:
1. Archivo: project_brain_[project_name].md
2. Los agentes (Gimena, Gabi) consultan este documento ANTES de cualquier decisión
3. Cualquier cambio aprobado debe reflejarse aquí
4. Responde SOLO en JSON

CONTEXTO: ${JSON.stringify(context)}
INPUT: ${input}

Proporciona resumen del Project Brain.`,

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

  return null;
}

function listAgents() {
  return [
    ...Object.keys(PM_AGENT_PROMPTS).map((id) => ({ id, family: "pm" })),
    ...Object.keys(SPEC_KIT_FILES).map((id) => ({ id, family: "spec-kit" }))
  ];
}

function isKnownAgent(agentId) {
  return !!(PM_AGENT_PROMPTS[agentId] || SPEC_KIT_FILES[agentId]);
}

module.exports = { buildPrompt, listAgents, isKnownAgent, SPEC_KIT_AGENTS_DIR };
