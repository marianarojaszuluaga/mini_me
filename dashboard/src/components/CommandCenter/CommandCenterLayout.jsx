import React from "react";
import ChatPanel from "./ChatPanel.jsx";
import StatusPanel from "./StatusPanel.jsx";
import "./command-center.css";

/**
 * CommandCenterLayout — Command Center shell (SPEC_JARVIS.md §2).
 *
 * CSS Grid with explicit rows/columns, NOT flexbox — this is the fix for the
 * known overlap bug (.top-section had no overflow control in the old layout).
 * Each panel owns its own `overflow-y: auto` and the grid row has a fixed
 * height (`height: calc(100vh - header)`), so a panel's content can never
 * grow into its sibling.
 *
 * Props:
 *  - chatPanel?: ReactNode — defaults to <ChatPanel /> placeholder
 *  - statusPanel?: ReactNode — defaults to <StatusPanel /> placeholder
 *  - header?: ReactNode — optional header row rendered above the grid
 *  - api?, agents?, phases? — forwarded to the default <StatusPanel /> (which
 *    forwards `api` further into its drill-downs) when the caller doesn't
 *    supply its own `statusPanel`/`chatPanel` node.
 *
 * Other agents building the real ChatPanel/StatusPanel should keep editing
 * ChatPanel.jsx / StatusPanel.jsx directly (imported here by name), OR pass
 * their own component via the `chatPanel`/`statusPanel` props — either works.
 */
export default function CommandCenterLayout({ chatPanel, statusPanel, header, api, agents, phases }) {
  return (
    <div className="command-center">
      {header && <div className="command-center-header">{header}</div>}
      <div className="command-center-grid">
        <section className="command-center-panel command-center-chat" aria-label="Chat">
          {chatPanel || <ChatPanel api={api} />}
        </section>
        <section className="command-center-panel command-center-status" aria-label="Estado">
          {statusPanel || <StatusPanel api={api} agents={agents} phases={phases} />}
        </section>
      </div>
    </div>
  );
}
