/**
 * Phase Contracts
 *
 * Transcribed from ia-hybrid-teams/spec-kit/PHASE_CONTRACTS.md — this is data,
 * not a reinterpretation. If the source doc changes, update this file to match.
 * Phase 5 (Deploy) has no agent participants in the source doc (it notes tooling
 * predominates there and recommends a future "Deployment Operator Agent" spec),
 * so its `agents` list stays empty here rather than inventing one.
 */

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
      "HUs/conceptos a construir (si aplica)"
    ],
    outputs: [
      "Conjunto de HUs para todos los módulos",
      "Scheduler final (módulos, HUs, timing, hitos, asignación de recursos)"
    ],
    agents: ["gabriela", "hu-work-planner", "gimena", "gina-scheduler"]
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
