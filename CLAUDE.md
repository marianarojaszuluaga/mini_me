# Instrucciones de proyecto — Mini me (orquestrador-360)

## Fuente de verdad para UX/UI: apple-design skills

Cualquier trabajo de diseño de interfaz en `dashboard/` (crear, restilar, auditar
UX/UI, o revisar usabilidad/claridad de flujo) debe basarse en la familia de
skills **`apple-design`** (instaladas en `~/.claude/skills/apple-design*`,
origen: https://github.com/s1gmamale1/apple-design-skills — clonado y auditado
contra este dashboard el 2026-09-11). No inventar convenciones de diseño nuevas
ad-hoc si esta guía ya cubre el caso: consultar el hub `apple-design` primero,
que enruta a `apple-design-foundations` (color/tipografía/layout),
`apple-design-interaction` (navegación, estados, feedback), `apple-design-motion`
(springs, scroll, gestos), `apple-design-tactics` (accesibilidad, 44pt targets),
etc. según lo que aplique.

Criterio central: **eje de restricción** (¿decoración o significado? — quitar
lo que solo decora) × **eje de superficie** — en este dashboard:
- **Landing** (`dashboard/src/pages/Landing.jsx`) = superficie **flagship/marketing**: el motion es la sustancia, no un extra (dentro de lo razonable para un producto B2B interno, no cinematográfico tipo apple.com).
- **AppShell/Sidebar/ProjectsView/LifecycleView** (dentro de `dashboard/src/components/`) = superficie **utilitaria**: motion casi invisible, springs ≤300ms, el foco es la tarea, no el efecto.

Antes de dar por "Apple-grade" o "resuelto" cualquier cambio de UI, correr el
restraint pass de `apple-design/references/restraint-and-antislop.md`: colores
semánticos (no hex fijo), un solo acento, producto real mostrado (no
placeholders abstractos), targets táctiles ≥44pt donde aplique, y
`prefers-reduced-motion` respetado en cualquier animación nueva.
