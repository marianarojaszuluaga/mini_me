import React from "react";

/**
 * Shared linear (stroke) icons — Mariana, 2026-08-19: "los íconos como
 * emojis no deberían estar presentes. Solo los iconos lineares que hay en
 * el artefacto." Replaces every emoji glyph (🎯 📁 🧠 ⚠️ ✅ ✓) across the app
 * with the same stroke-icon style as the mockup (viewBox 24x24, stroke
 * currentColor, strokeWidth 2).
 */

export const BrandIcon = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="3" />
    <path d="M12 2v4M12 18v4M4.9 4.9l2.8 2.8M16.3 16.3l2.8 2.8M2 12h4M18 12h4M4.9 19.1l2.8-2.8M16.3 7.7l2.8-2.8" />
  </svg>
);

export const FolderIcon = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V7z" />
  </svg>
);

export const BrainIcon = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M9.5 14.5L3 21M14 10a4 4 0 10-4-4M15.5 8.5L21 3M13.5 13.5L21 21" />
    <circle cx="8" cy="16" r="4" />
  </svg>
);

export const AlertIcon = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 9v4M12 17h.01" />
    <circle cx="12" cy="12" r="9" />
  </svg>
);

export const CheckIcon = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M20 6L9 17l-5-5" />
  </svg>
);
