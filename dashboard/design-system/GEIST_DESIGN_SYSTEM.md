# Design System — Geist (Vercel), extraído para Orquestrador 360

> **Fuente**: https://vercel.com/geist (colors, typography, materials, grid)
> **Método**: valores reales leídos en vivo del CSS computado de esa página (CSSOM +
> `getComputedStyle`), no copiados de documentación de marketing — la página de docs de Vercel no
> expone los valores exactos en el HTML/markdown, solo los nombres de los tokens.
> **Extraído**: 2026-08-12
> **Archivo de datos**: [`geist-tokens.json`](geist-tokens.json) — mismo contenido en JSON puro
> para consumir desde código (Tailwind config, CSS-in-JS, etc.)

---

## 0. Por qué Geist y no un sistema propio desde cero

Pendiente reconocido de la auditoría de Jarvis Mode: el bug de overlap CSS y el rediseño general
del dashboard React. En vez de diseñar un sistema de cero, se adopta **Geist** (el design system
que usa Vercel — mismo proveedor donde ya está desplegado Orquestrador 360) como base, y se ajusta
el color de acento si hace falta. Es intercambiable: los nombres de los tokens no cambian, solo
sus valores.

---

## 1. Color

10 escalas (`gray`, `blue`, `red`, `amber`, `green`, `teal`, `purple`, `pink`, más `background` y
`grayAlpha`), cada una en HSL de 100 a 1000, **con valores distintos para modo claro y oscuro** —
no es solo invertir el mismo color, cada paso está ajustado a mano por Vercel para mantener
contraste correcto en ambos modos.

### 1.1 Estructura por paso (aplica a cualquier escala, ej. `gray`)

| Paso | Uso previsto |
|---|---|
| 100–300 | Fondos de componentes (default, hover, active) |
| 400–600 | Bordes (default, hover, active) |
| 700–800 | Fondos de alto contraste |
| 900–1000 | Texto/iconos (900 = secundario, 1000 = primario) |

### 1.2 Cómo ajustar el color de marca/acento

Todo vive como `"H, S%, L%"` (sin la función `hsl()`) bajo cada escala en `geist-tokens.json`. Para
cambiar el acento (ej. reemplazar el azul de Vercel por otro color de marca):

1. Elige o genera una escala nueva de 10 pasos con la misma progresión de luminosidad que `blue`
   (100 = casi blanco/negro según el tema, 1000 = el opuesto) — mantiene el contraste correcto.
2. Reemplaza los valores de `color.light.blue` y `color.dark.blue` en `geist-tokens.json` (o crea
   una escala nueva, ej. `brand`, y usa esa en vez de `blue` en los componentes).
3. No cambies los **nombres** de los tokens si el CSS/Tailwind ya los consume — solo los valores.

### 1.3 Colores estáticos (no cambian con el tema)

`black: #000`, `white: #fff`. `grayAlpha` son grises semitransparentes (para overlays/hovers sobre
cualquier fondo) — en modo claro son negro con alpha, en modo oscuro blanco con alpha.

---

## 2. Tipografía

Dos familias: **GeistSans** (UI) y **Geist Mono** (código). Cuatro categorías de tamaño, cada una
con su propia combinación fija de `font-size` + `line-height` + `font-weight` + `letter-spacing`
— no se mezclan independientemente, cada "talla" es un paquete completo:

| Categoría | Tallas | Uso |
|---|---|---|
| `heading` | 14 a 72 | Encabezados de página/sección — siempre `font-weight: 600`, `letter-spacing` negativo (más negativo cuanto más grande) |
| `button` | 12, 14, 16 | Texto de botones — `font-weight: 500`, sin letter-spacing |
| `label` | 12 a 20 | Texto de una sola línea (labels, badges) — `font-weight: 400` |
| `copy` | 13 a 24 | Texto de párrafo/multi-línea, line-height generoso — `font-weight: 400` |

Ejemplo real verificado: `heading-40` (usado en el `<h1>` de la propia página de Geist) = 40px /
48px / 600 / -2.4px letter-spacing.

---

## 3. Spacing

Escala base de 4px (`--geist-space` = 4px), con múltiplos nombrados (`2x`=8px, `3x`=12px... hasta
`64x`=256px) más 3 tamaños semánticos (`small`=32px, `medium`=36px, `large`=40px, usados en
controles de formulario) y un `gap` estándar de 24px para separación entre secciones.

## 4. Layout

`pageWidth`: 1200px (ancho de contenido clásico de Geist) — Orquestrador 360 puede usar 1400px
(`pageWidthDS`, la variante más ancha que Vercel usa en su propio dashboard de producto, no en
marketing) ya que el Command Center necesita más espacio horizontal (chat + panel de estado lado
a lado, §2 de `SPEC_JARVIS.md`).

## 5. Radios (border-radius)

Base 6px para casi todo; 12px para elementos "elevados" (menús, modales, cards medianas/grandes);
16px solo para fullscreen. Consistente con el principio de Geist de "más radio = más elevado".

## 6. Sombras

8 niveles (`2xs` a `2xl` + `modalElevated`), cada uno **distinto en claro y oscuro** — en modo
oscuro las sombras usan un borde blanco translúcido (`#ffffff25`) en vez de solo sombra oscura,
porque una sombra negra sobre fondo negro no se ve. Progresión: `tooltip` (más liviana) →
`menu` → `modal` → `fullscreen` (más elevada).

## 7. Z-index

`drawer: 200`, `modal: 300`, `menu: 2001`, `toast: 5000`, `tooltip: 99999` — jerarquía fija, útil
tal cual para el Command Center (el Panel de Chat no necesita z-index alto, pero un modal de
"Crear Nuevo Proyecto" sobre el Command Center sí debe respetar esta jerarquía).

## 8. Motion

Un solo timing function (`cubic-bezier(.175, .885, .32, 1.1)`, "swift") para overlays (0.3s) y
popovers (0.2s) — consistencia de sensación de movimiento en toda la UI.

---

## 9. Cómo se aplica esto al rediseño de Orquestrador 360

- **Resuelve el bug de overlap CSS** (hallazgo de la auditoría anterior): al adoptar el sistema de
  `spacing`/`layout` de Geist en vez del CSS ad-hoc actual (`styles.css` con `flex:1` sin control
  de overflow), el patrón de grid de Geist ya maneja estos casos correctamente por diseño.
- El **Panel de Chat + Panel de Estado** del Command Center (`SPEC_JARVIS.md` §2) puede usar
  `pageWidthDS` (1400px) con un grid de 2 columnas usando la escala de `spacing.gap` (24px) como
  separación.
- Los **semáforos de proyecto** (on-track / atención / bloqueado) mapean directo a
  `color.*.green.700`, `color.*.amber.700`, `color.*.red.700` — mismo verde/ámbar/rojo que Vercel
  ya usa para sus propios estados de deployment (success/building/error), consistente con el
  contexto de que esto se despliega ahí mismo.
