<!--
Completa las dos secciones. Bullets cortos, sin relleno. Si una sección no
aplica, escribe "N/A" y por qué en una línea — no la borres.
-->

## Resumen funcional

<!-- Lenguaje de producto: qué cambia para la usuaria/el equipo, no cómo. -->

- ¿Qué cambia?
- ¿Por qué? (bug, pedido de negocio, deuda técnica...)
- ¿Quién lo nota? (usuaria final, PM, otro servicio...)

## Detalle técnico

<!-- Lenguaje técnico: para quien revisa código o depura esto en 6 meses. -->

- Archivos/módulos clave tocados:
- Decisiones de arquitectura (y alternativas descartadas, si las hubo):
- Breaking changes / migraciones necesarias:
- Cómo se probó (tests nuevos, manual, ninguno y por qué):

## Checklist

- [ ] `pytest` pasa localmente
- [ ] `npm run build` (dashboard) pasa, si tocaste `dashboard/`
- [ ] No rompe multi-usuario / i18n / Basecamp Publisher existentes
