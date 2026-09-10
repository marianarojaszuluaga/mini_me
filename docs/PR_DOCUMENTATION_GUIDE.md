# Guía: cómo documentar un PR en orquestrador-360

Contexto: pedido de Angela Forero (CTO) en la reunión QA/KPI del 2026-09-10 —
PRs con resumen funcional + detalle técnico, corto y sin relleno. La plantilla
vive en `.github/pull_request_template.md` y GitHub la precarga sola al abrir
un PR.

## 1. Pedirle a Claude Code el resumen del diff antes de abrir el PR

Prompt sugerido (ajusta el rango de commits si tu rama tiene más de uno):

```
Resume el diff de esta rama contra main en el formato de
.github/pull_request_template.md: "Resumen funcional" (lenguaje de producto,
sin jerga técnica) y "Detalle técnico" (archivos clave, decisiones de
arquitectura, breaking changes). Sé breve — bullets, no párrafos.
```

Claude Code ya tiene acceso a `git diff`/`git log` en la sesión, así que no
hace falta pegar el diff a mano. Revisa el resultado antes de pegarlo en el
PR — el resumen funcional en particular necesita criterio humano sobre qué le
importa a quien lo lee (PM, otra dev, la propia Angela).

## 2. Dónde vive el conocimiento compartido del equipo

Tres opciones evaluadas:

### (a) `.claude/agents/` — subagentes locales al repo
Definiciones de subagentes de Claude Code, atadas a este repo. Ventaja: se
versiona junto con el código que describen, cero fricción para quien ya usa
Claude Code aquí. Desventaja: no portable a otras herramientas (Cursor,
Copilot, otro CLI) ni a otros repos de ImagineApps sin copiar/pegar.

### (b) `.agents/` — convención genérica, portable
Mismo contenido, pero bajo una carpeta sin acoplarse a una herramienta
específica. Mejor candidato cuando el conocimiento (prompts de agentes,
convenciones de equipo) debe ser reusable entre repos y entre herramientas —
es lo que ya se usa para compartir con `ia-hybrid-teams`.

### (c) Activar GitHub Wiki (como Finanz Butik)
**Recomendación: no activarlo, por ahora.**

Este repo ya tiene documentación viva versionada junto al código:
`SPEC_JARVIS.md`, los `PLAN-*.md`, y `qa/` (reportes de QA sweep). Esa
documentación:
- se revisa en el mismo PR que el código que describe (un Wiki no pasa por
  review de PR, se edita aparte y se desincroniza fácil),
- vive en el historial de git (blame, versiones, revert), cosa que el Wiki
  de GitHub hace peor (su propio git interno es secundario, casi nadie lo
  clona),
- ya es el hábito del equipo — moverla a Wiki es puro costo de migración sin
  un problema concreto que resuelva.

No hay evidencia en este momento de que el Wiki de Finanz Butik sea mejor
que este esquema — no hemos visto su Wiki, ni un caso donde `SPEC_JARVIS.md`/
`PLAN-*.md`/`qa/` se hayan quedado cortos. Si en el futuro aparece una razón
concreta (por ejemplo: gente no-técnica que necesita editar documentación sin
tocar el repo), vale la pena reabrir la discusión — pero activarlo "porque
Finanz Butik lo hace" duplicaría información que ya vive en un solo lugar,
sin necesidad real detectada.

**Conclusión:** para lo genérico/portable entre proyectos de ImagineApps →
`.agents/` (o el `ia-hybrid-teams/spec-kit` compartido). Para lo específico de
este repo → seguir en `SPEC_JARVIS.md` / `PLAN-*.md` / `qa/`, no Wiki.
