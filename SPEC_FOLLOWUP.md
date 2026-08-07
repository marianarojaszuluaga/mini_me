# SPEC — Follow Up (pilar del rol PDM)
> **Status**: Inventario generalizado — sin código, sin agentes todavía
> **Fuente**: "Metologías (All)" (doc interno Imagine Apps, sección Operaciones) — filtrado a
> lo portable a cualquier empresa. Lo específico de Imagine Apps (Basecamp, Ops Hub, Gabriela,
> nombres de canal, personas, "Imaginer", links a documentos) se removió explícitamente.
> **Creado**: Agosto 2026

---

## Marco: los 3 pilares del rol PDM

- **Planning** — mayormente cubierto por Orquestrador 360 (`gimena`, `milestone-writer`,
  `dod-definer`, `gabi`, `capacity-reconciler`, `gina-scheduler`) + `SPEC_COTIZADOR.md`.
- **Follow Up** — este documento. Sin cubrir todavía.
- **Delivery** — pendiente (QA, Releases, Entregas Parciales/Finales, Garantía).

Follow Up tiene dos naturalezas distintas que no deberían tratarse igual:
- **Gestión de personas** (1:1, planes de mejora/crecimiento, onboarding/offboarding, duplas) —
  requiere criterio humano, no es automatizable de fondo.
- **Reporte hacia cliente/gerencia** (status, alertas, NPS, demos) — más mecánico/recurrente,
  mejor candidato a asistencia por agente.

---

## Cliente

### Demo semanal
**Propósito:** Validar avance tangible con feedback inmediato.
**Cuándo:** Cadencia semanal, requiere una versión estable para mostrar.
**Pasos:** Preparar entorno con datos reales/de ejemplo → presentar funcionalidades
terminadas → grabar sesión + transcripción → documentar acuerdos y próximos pasos.
**Entregable:** Grabación + transcripción + acta de compromisos.

---

## Interno — Equipo (gestión de personas)

### Daily
**Propósito:** Inspeccionar avance hacia el objetivo del sprint, adaptar el plan en equipo.
**Cuándo:** Diario, sesión corta (≤15 min) o async.
**Pasos:** Sincronización a hora fija → cada persona comparte avance del día anterior →
identificar bloqueos → adaptar el plan de las próximas 24h → escalar lo que requiera ayuda
externa.
**Entregable:** Plan adaptado + registro de bloqueos.

### 1:1
**Propósito:** Espacio seguro de alineación humana y operativa, compromisos bidireccionales.
**Cuándo:** Cadencia mensual por reporte directo.
**Pasos (3 fases):** (1) chequeo humano — energía, balance — antes de temas de trabajo;
(2) diagnóstico operativo — fricciones de proceso, fallas de liderazgo; (3) crecimiento —
conectar tareas actuales con plan de carrera. Luego: definir compromisos bidireccionales
(qué hace la persona, qué desbloquea el líder) → documentar/compartir resumen → seguimiento
asíncrono durante el mes.
**Entregable:** Resumen de compromisos bidireccionales.

### Planes de Mejora
**Propósito:** Convertir brechas de desempeño en un plan de acción con seguimiento real.
**Cuándo:** Cuando hay brechas persistentes (~2 meses); cierra con evaluación tras ~4 semanas.
**Pasos:** Identificar fortalezas y brechas → definir objetivos claros → diseñar acciones
específicas con responsable y plazo → definir KPIs de éxito → check-ins periódicos →
cierre/evaluación al final del período.
**Entregable:** Plan firmado + resultado de KPIs al cierre.

### Planes de Crecimiento
**Propósito:** Estructurar el camino de talento de alto desempeño hacia un rol de mayor impacto.
**Cuándo:** Tras evaluación sobresaliente o cuando la persona "topó techo" en su rol actual.
**Pasos:** Validar que domina su rol actual sin fricciones → definir el rol destino →
construir un mapa de hitos medibles → presentar el plan y acordar KPIs (sin prometer
ascenso automático) → acompañamiento continuo → evaluación final (demo de operación en el
nuevo nivel).
**Entregable:** Plan firmado + evaluación final.

### Pulso de Operaciones (mejora continua de método)
**Propósito:** Alinear la cultura/método operativo resolviendo cuellos de botella y
escalando innovaciones probadas.
**Cuándo:** Sesión periódica (ej. semanal), a partir de un backlog de puntos de dolor o
innovaciones detectadas.
**Pasos:** Elegir el tema del backlog → dar contexto previo al equipo → facilitar sesión
colaborativa → co-crear la solución → capturar feedback → actualizar la documentación
oficial del proceso.
**Entregable:** Documentación de proceso actualizada + comunicación del cambio.

### Onboarding (de personas nuevas al equipo)
**Propósito:** Integrar efectivamente a un nuevo miembro del equipo.
**Cuándo:** Al confirmarse la contratación; termina cuando la persona tiene autonomía y
metas claras para su primer mes.
**Pasos:** Confirmar que el onboarding administrativo esté listo → conversación de cultura →
provisionar accesos a herramientas → definir horarios/expectativas de disponibilidad →
presentación al equipo + contexto del proyecto → compartir base de conocimiento de
referencia → definir metas de los primeros 30 días → alineación técnica con el líder técnico.
**Entregable:** Persona con accesos, contexto y metas del primer mes.

### Offboarding (de personas que salen del equipo)
**Propósito:** Cierre operativo limpio + insight honesto sobre la experiencia de salida.
**Cuándo:** Tras confirmación formal de salida; segunda etapa días después de la salida.
**Pasos — Etapa 1 (líder directo, últimos días):** mapear estado de cada tarea → asegurar que
el conocimiento informal quede documentado → transferir propiedad de tableros/repos/carpetas →
revocar accesos → confirmar devolución de equipos.
**Pasos — Etapa 2 (persona neutral, ej. RRHH, días después):** entrevista de salida enfocada
en seguridad psicológica → sintetizar insights → compartir con liderazgo.
**Entregable:** Checklist de handoff aprobado + bitácora de salida (confidencial).

### Empalme de duplas (continuidad/backup)
**Propósito:** Continuidad operativa mitigando la dependencia de una sola persona en un
proyecto.
**Cuándo:** Al asignar una dupla a un proyecto.
**Pasos:** Sincronizar agendas para la sesión de traspaso → revisar juntos el contexto del
proyecto → transferir conocimiento técnico/funcional en detalle → compartir estado actual
(en curso, bloqueos, riesgos) → verificar que ambos tengan accesos → documentar acuerdos →
dar seguimiento a la dupla en el tiempo.
**Entregable:** Documento de empalme + ambas personas con autonomía operativa completa.

**Skills clave que hacen que esto funcione** (portable, no depende de herramienta):
comunicación clara y constante, documentación disciplinada, responsabilidad compartida,
transferencia real de conocimiento (el "cómo" y el "por qué"), visibilidad del trabajo,
colaboración activa, mentalidad de equipo sobre conocimiento individual.

---

## A gerencia (reporte)

### Project Status (semanal)
**Propósito:** Transparencia y seguimiento preciso de la salud de cada proyecto.
**Cuándo:** Cadencia semanal (ej. inicio de semana), con corte a mediodía.
**Pasos:** Elegir el proyecto a reportar → registrar fechas del hito actual y fechas
especiales → diagnosticar salud (Estable / Alerta / Crítico) → estimar probabilidad de
cumplimiento (Alta/Media/Baja) → recoger insights por disciplina (Tech, QA, UX, PM) →
registrar valor agregado y riesgos → publicar antes del corte.
**Entregable:** Reporte de status publicado.

### Revisión holística de salud operativa ("360")
**Propósito:** Evaluación integral (técnica + financiera + cliente + equipo) para detectar
problemas y reforzar aciertos.
**Cuándo:** Semanal, requiere que el Project Status ya esté hecho.
**Pasos:** Agendar con todos los stakeholders → consolidar el estado (finanzas, tiempos,
clima de equipo) antes de la sesión → compartir el reporte con anticipación → sesión
enfocada en levantar alertas (no esconder problemas) → registrar cada alerta en un sistema
compartido → co-diseñar una estrategia de mitigación por alerta.
**Entregable:** Alertas y estrategias de mitigación registradas.

### NPS (satisfacción de cliente)
**Propósito:** Medir y actuar sobre la satisfacción del cliente con feedback directo.
**Cuándo:** Semestral, al cierre de un sprint/ciclo.
**Pasos:** Preparar al cliente (explicar el propósito, que la honestidad es valiosa) →
enviar la encuesta justo al cierre del ciclo → registrar puntaje y comentarios → extraer
insights más allá del número → compartir resultados con el equipo → si el puntaje está bajo
un umbral, activar un plan de mejora.
**Entregable:** Score registrado + plan de mejora si aplica.

### Levantamiento de Alertas (escalamiento)
**Propósito:** Escalar riesgos temprano antes de que se vuelvan críticos.
**Cuándo:** Al detectar cualquier cosa que bloquee el flujo del proyecto.
**Pasos:** Identificar la situación que bloquea → clasificar severidad (Baja/Media/Alta/
Crítica) → elegir el canal de escalamiento proporcional a la severidad → comunicar con
título claro + descripción + soluciones propuestas + qué se necesita exactamente →
seguimiento hasta resolución → cerrar el ciclo confirmando que quedó resuelto.
**Entregable:** Alerta cerrada con evidencia de gestión.

---

## Qué se removió por ser específico de Imagine Apps (no portable)

Basecamp, Ops Hub, el agente Gabriela como herramienta puntual, nombres de canales de Slack/
Google Chat específicos (Centro de Operaciones, Triage/UCI, "1:1// [Nombre]"), personas
nombradas (Angie Rincón, Daniela Meza, David), terminología "Imaginer"/"Ecosistema Imagine",
mecánica de bot a las 8:00 AM, convención específica de emojis, LearningHub, plantilla de
Google Sites, links a documentos/carpetas de Drive específicos.

## Pendiente de definir (el doc fuente los nombra pero sin contenido)

Seguimiento al plan de Mejora (20), Seguimiento al plan de crecimiento (21) — probablemente
son solo el check-in periódico DENTRO de los procesos ya descritos arriba, no procesos nuevos
separados — a confirmar.
