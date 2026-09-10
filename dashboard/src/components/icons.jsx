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

// Same paths as Sidebar's ICONS.integrations/chat (kept in sync manually —
// Sidebar's copy stays inline since it's part of a larger local ICONS map).
export const IntegrationsIcon = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M9 2v4M15 2v4M6 10h12a1 1 0 011 1v3a5 5 0 01-5 5h-4a5 5 0 01-5-5v-3a1 1 0 011-1zM8 19v1a2 2 0 002 2h4a2 2 0 002-2v-1" />
  </svg>
);

export const ChatIcon = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" />
  </svg>
);

export const AgentsIcon = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2" />
    <circle cx="9" cy="7" r="4" />
    <path d="M23 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75" />
  </svg>
);

export const QaIcon = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 2l8 4v6c0 5-3.5 8.5-8 10-4.5-1.5-8-5-8-10V6l8-4z" />
    <path d="M9 12l2 2 4-4" />
  </svg>
);
