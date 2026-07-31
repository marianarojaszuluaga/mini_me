/**
 * Phase Contracts
 *
 * Transcribed from ia-hybrid-teams/spec-kit/PHASE_CONTRACTS.md — this is data,
 * not a reinterpretation. If the source doc changes, update this file to match.
 * Phase 5 (Deploy) has no agent participants in the source doc (it notes tooling
 * predominates there and recommends a future "Deployment Operator Agent" spec),
 * so its `agents` list stays empty here rather than inventing one.
 *
 * Phase 1 (Planeación)'s internal structure is further transcribed from
 * `esquema-planeacion.md` (Mariana's own reusable planning playbook, not part
 * of ia-hybrid-teams) — see `planningSubPhases` below. That doc's "Regla de
 * oro" governs Fase 4 (Reconciliación): scope, time, and capacity cannot all
 * be fixed at once — if they don't reconcile, one has to give, in the
 * documented lever order (see capacity-reconciler agent).
 */

const PLANNING_SUB_PHASES = [
  {
    id: 0,
    key: "lock_scope",
    title: "Lock de alcance + baseline",
    objective: "Congelar qué es el MVP y medir lo ya avanzado",
    output: "Backlog del alcance + % de avance real",
    gate: "¿El alcance está congelado?",
    agent: "gimena"
  },
  {
    id: 1,
    key: "milestones",
    title: "Milestones (de cara al cliente)",
    objective: "Partir el alcance en hitos que digan 'qué vas a poder ver/hacer'",
    output: "Lista de milestones con su promesa de valor",
    gate: "¿Los milestones son demostrables y aprobados?",
    agent: "milestone-writer"
  },
  {
    id: 2,
    key: "dod",
    title: "Definition of Done",
    objective: "Definir 'terminado' objetivo: global + por milestone",
    output: "DoD global + DoD por milestone",
    gate: "¿El DoD es objetivo y acordado?",
    agent: "dod-definer"
  },
  {
    id: 3,
    key: "estimation",
    title: "Estimación",
    objective: "Dimensionar el esfuerzo por tarea/módulo",
    output: "Estimación preliminar contra capacidad",
    gate: null,
    agent: "gabi"
  },
  {
    id: 4,
    key: "reconciliation",
    title: "Reconciliación alcance ↔ capacidad ↔ fecha",
    objective: "Ver si cabe; si no, aplicar palancas — es un loop",
    output: "Brecha calculada + decisiones de ajuste",
    gate: "¿La brecha alcance↔capacidad↔fecha está cerrada o decidida? (el gate más importante)",
    agent: "capacity-reconciler"
  },
  {
    id: 5,
    key: "timeline",
    title: "Timeline",
    objective: "Ubicar tareas en el calendario: fechas internas vs cliente + buffer",
    output: "Cronograma / Gantt comprometible",
    gate: "¿El timeline es comprometible con buffer?",
    agent: "gina-scheduler"
  },
  {
    id: 6,
    key: "transversales",
    title: "Transversales",
    objective: "Cerrar lo que cruza todos los hitos",
    output: "Notas de multiplataforma, deploy, pruebas, seguridad",
    gate: null,
    // Cross-cutting by nature — auditor listed as the representative owner
    // for /orchestrate's single-agent-per-step mapping, but qa-integrator and
    // architect also contribute here per their own phase listings and can be
    // invoked directly regardless of this mapping.
    agent: "auditor"
  }
];

const PHASES = [
  {
    id: 1,
    key: "planning",
    title: "Planeación y Scheduler",
    diagram: "diagrams/phase1_planning.mmd",
    inputs: [
      "Conversación/brief en .txt",
      "database design.sql",
      "Arquitectura (documentos)",
      "Notas técnicas adicionales",
      "HUs/conceptos a construir (si aplica)",
      "Marco del proyecto: alcance, fechas, capacidad (esquema-planeacion.md §2)"
    ],
    outputs: [
      "Backlog del alcance + baseline de avance",
      "Milestones de cara al cliente",
      "Definition of Done (global + por milestone)",
      "Estimación preliminar",
      "Brecha alcance↔capacidad↔fecha cerrada o decidida",
      "Timeline/Gantt comprometible con buffer",
      "Notas transversales (multiplataforma, deploy, pruebas, seguridad)"
    ],
    agents: [
      "gabriela",
      "hu-work-planner",
      "gimena",
      "gina-scheduler",
      "gabi",
      "milestone-writer",
      "dod-definer",
      "capacity-reconciler"
    ],
    planningSubPhases: PLANNING_SUB_PHASES
  },
  {
    id: 2,
    key: "backend",
    title: "Backend Development + API Documentation",
    diagram: "diagrams/phase2_backend.mmd",
    inputs: [
      "HUs y requerimientos técnicos de Leaders",
      "DB/data needs (DBML)",
      "Contratos de autenticación y endpoints (si existen)"
    ],
    outputs: [
      "Implementación validada",
      "OpenAPI/Swagger URL del backend",
      "Reportes de pruebas automatizadas de API"
    ],
    agents: ["data-engineer", "gabi", "architect", "auditor", "fixed-errors", "qa-integrator"]
  },
  {
    id: 3,
    key: "frontend",
    title: "Frontend Web o App (Integración UI)",
    diagram: [
      "diagrams/phase3_a_frontend_web.mmd",
      "diagrams/phase3_b_frontend_app.mmd"
    ],
    inputs: [
      "HUs y UI/UX requirements de Leaders",
      "Figma design file",
      "Contratos API (OpenAPI/Swagger) del backend"
    ],
    outputs: [
      "Frontend funcional (web o app)",
      "Unit tests",
      "Swagger/OpenAPI API URL",
      "Reportes E2E (si aplica)"
    ],
    agents: ["fullstack-developer", "flutter-developer", "auditor", "fixed-errors", "integration"]
  },
  {
    id: 4,
    key: "integration_quality",
    title: "Integración & Calidad (Sonar + MCP Integration + Videos)",
    diagram: "diagrams/phase4_integration_test.mmd",
    inputs: [
      "Backend OpenAPI/Swagger",
      "Frontend web y/o app",
      "Suite de pruebas unitarias y/o contratos"
    ],
    outputs: [
      "Gate de calidad Sonar",
      "Validación de estándares de pruebas unitarias",
      "Resultados de MCP integration testing",
      "Videos/screenshots de ejecuciones",
      "Recomendación Go/No-Go"
    ],
    agents: [
      "sonar-quality-gate",
      "unit-test-standards-reviewer",
      "mcp-integration-tester",
      "test-video-recorder",
      "quality-report-generator"
    ]
  },
  {
    id: 5,
    key: "deploy",
    title: "Despliegue CI/CD (Containers o Apps)",
    diagram: [
      "diagrams/phase5_a_deploy_cicd_container.mmd",
      "diagrams/phase5_b_deploy_cicd_app.mmd"
    ],
    inputs: [
      "Artefactos construidos y aprobados (backend/frontends)",
      "Secrets/certs (IaC + CI/CD)",
      "Configuración de pipeline (Jenkins/CodeMagic)"
    ],
    outputs: [
      "Servicio desplegado o app publicada en tiendas",
      "Evidencia de logs y/o estado del pipeline",
      "Información de disponibilidad por entorno"
    ],
    agents: [],
    note:
      "En esta fase predominan herramientas/automatización, no necesariamente agentes Claude. " +
      "ia-hybrid-teams recomienda crear un 'Deployment Operator Agent' — no existe todavía, no se inventa aquí."
  }
];

function listPhases() {
  return PHASES;
}

function getPhase(idOrKey) {
  return PHASES.find((p) => p.id === Number(idOrKey) || p.key === idOrKey) || null;
}

module.exports = { listPhases, getPhase };
