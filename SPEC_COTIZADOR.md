# SPEC — Cotizador (Gestión Comercial)
> **Status**: Diseño conceptual cerrado — sin código todavía
> **Bucket de Mariana**: Comercial / Growth (NO es Project Management)
> **Creado**: Agosto 2026

---

## Overview

**Qué es**: El proceso completo de cotización de un proyecto nuevo, desde que llega un
prospecto hasta que la propuesta se convierte en venta (o se cierra como perdida).

**Por qué**: No existía ningún spec para esto en `ia-hybrid-teams` (`docs/how_to_fill.md`
solo lo nombra como responsabilidad de "Área Comercial", sin proceso documentado). No debe
tratarse como un proceso manual ni como un simple generador de documento — el eje central
es la **conversión**, no solo producir una cotización bonita.

---

## El proceso (8 pasos)

| # | Paso | Reusa agente existente |
|---|---|---|
| 1 | Entender el dolor del cliente / revisar su idea. **Captura también las 5 señales de calificación (ver abajo).** | — (nuevo, con calificación integrada) |
| 2 | Construir versión inicial de HUs — verificar promesa de valor, consistencia, concreción | `gimena` |
| 3 | Consulta técnica — aproximación tecnológica, recursos, dependencias | `architect`, `data-engineer` |
| 4 | Generar hitos + estimación de tiempo + DoD | `milestone-writer`, `dod-definer`, `gabi`, `gina-scheduler` |
| 5 | Asignar valor/precio a la propuesta (valor-aportado, no solo horas×tarifa) | — **gap: agente de pricing, no existe** |
| 6 | Verificar cohesión entre alcance, precio, timeline y DoD | — **gap: reusar lógica tipo "Jenny" (qa-agents.skill) para auditoría de consistencia** |
| 7 | Corregir (loop de vuelta a los pasos anteriores según lo que falle en 6) | control de flujo, no agente |
| 8 | Generar propuesta comercial cara al cliente (Inversión, Equipo, Tiempo, Promesa de valor/DoD) | — **gap: nuevo agente "proposal-writer", misma disciplina "sin términos técnicos" que Daniel pero formato de propuesta, no release notes** |

**Los pasos 2-4 no requieren agentes nuevos** — son básicamente el mismo trabajo que ya
hace la Fase 1 de planeación interna (`esquema-planeacion.md`), aplicado en pre-venta en
vez de post-venta.

---

## Calificación de prospecto (integrada al Paso 1, no un paso aparte)

Los datos de calificación no existen antes de la conversación de descubrimiento — por eso
viven DENTRO del Paso 1, no como filtro previo.

| Señal | 🔥 Caliente | 🧊 Frío |
|---|---|---|
| Origen | Referido | Tráfico frío |
| Urgencia | Fecha límite real | "Algún día" |
| Decisor | Acceso directo a quien aprueba | No identificado |
| Presupuesto | Mencionado/claro | Ninguna señal |
| Claridad del problema | Concreto | Vago |

**Regla:** 2+ señales calientes → 🔥 Caliente. Si no → 🧊 Frío.

---

## Loop de conversión (después de enviar la propuesta)

El eje central del proceso. Cadencia real de Mariana hoy: seguimiento inmediato + día 8.

| Paso | Cuándo | Canal (según temperatura) |
|---|---|---|
| Envío | Día 0 | 🔥 WhatsApp / 🧊 Correo |
| Seguimiento 1 (ya existe) | Inmediato | 🔥 WhatsApp / 🧊 Correo |
| Seguimiento intermedio (nuevo) | Día 3-4 | 🔥 WhatsApp / 🧊 Correo |
| Seguimiento 2 (ya existe) | Día 8 | 🔥 WhatsApp / 🧊 Correo — **capturar motivo si hay objeción** |
| Cierre de ciclo (nuevo) | ~Día 15 | Decisión: seguir negociando / ajustar propuesta / marcar perdida |
| Registro de resultado (nuevo) | Al cerrar | Ganada / Perdida / Pausada + **motivo explícito** — alimenta mejora de cotizaciones futuras |

---

## Automatización por canal

- **Correo**: fácil — mismo patrón que ya funciona para Actas (Google Apps Script / Gmail).
- **WhatsApp**: requiere WhatsApp Business API (Meta directo o proveedor tipo Twilio) —
  implica alta de cuenta/número y costo por mensaje. **No decidido todavía si se automatiza
  ahora o se deja manual mientras tanto.**

---

## Gaps a construir (cuando se pase de spec a código)

1. Agente de **pricing** (Paso 5) — no existe ningún agente ni regla de negocio documentada
   sobre cómo se traduce esfuerzo/horas a precio de valor-aportado. Necesita definirse antes
   de escribir el agente (no inventar una fórmula de pricing sin validarla con Mariana).
2. Agente de **cohesión/QA de propuesta** (Paso 6) — candidato a reusar la lógica de Jenny
   (`qa-agents.skill`, auditor de cumplimiento de spec) adaptada a "¿alcance, precio, tiempo
   y DoD son consistentes entre sí?".
3. Agente **proposal-writer** (Paso 8) — mismo principio que Daniel (cara al cliente, sin
   términos técnicos) pero formato de propuesta comercial, no release notes.
4. Automatización de **seguimiento por WhatsApp** — bloqueada hasta decidir si se monta
   WhatsApp Business API ahora o después.
5. Automatización de **seguimiento por correo** — no bloqueada, mismo patrón que Actas.

---

## Open Questions

- [NEEDS CLARIFICATION] ¿Cuál es la fórmula/criterio real de pricing por valor-aportado hoy
  (aunque sea informal)? Sin esto no se puede escribir el agente del Paso 5.
- [NEEDS CLARIFICATION] ¿Automatizamos WhatsApp ahora (con el costo/setup de Business API)
  o empezamos solo con correo?
