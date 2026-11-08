# DATA-001 narrow UI contract for Sawaab

Before functional edits: expose backend/durability metadata separately from fixture/
simulation provenance in workspace/history/capabilities. Applications and Review retain
current layout/styles/controls; replace process-local store wording only when durable
metadata actually says postgres. A fixture reviewer remains a fixture reviewer even in
TigerData. API restarts preserve C state, but old B plans still need preparation again.
Sawaab's presentation is preserved; final field/component changes and validation follow.

Implemented additive `AnswerHistory.store: AnswerStoreMetadata | null` (backend:
postgres/memory/unconfigured, durable:boolean). Legacy `store_is_fixture` remains for
compatibility and describes the adapter; approval provenance comes from reviewer plus
saved workspace/version, not persistence. Review Page.tsx consumes this optional object:
postgres shows durable C state + continuing simulation/reviewer labels + new-plan restart
instruction; memory keeps its loss-on-restart notice. No CSS, layout, auth or flow redesign.
Backend capability `applications.storage` describes selection; readiness verifies the DB.
Workspace capability stays fixture-only/unavailable until real evidence integration.

Contracts regenerated together, preserving all baseline registrations. Review unit test
checks durable and simulation labels coexist, and restarted normal API + real Chromium
verifies the label at the same time as durable approval/new-plan read-back. B local files,
pending plan epochs and single-use grants are unchanged. Sawaab can restyle these existing
paragraphs while preserving their functional meaning and capability boundaries.

Publication reconciliation: main advanced to41a80efc477044203cf94cc44a289c56a50003f3 with
Sawaab's shared UI/landing/journey. Merged current main into this task branch, preserving
all his styles, layout and revised wording. Functional durable paragraph/metadata condition
remains. Complete required checks are rerun on that combined tree; no redesign authored here.

The combined browser suite caught external requests from UI-001's Google Fonts import.
To preserve both typography and existing no-external-request assertions, the exact Red Hat
Display600/Mono400/500/Text400/500/600 binaries are now served at /fonts with their original
SIL OFL notices and source hashes. Only font transport/import changed; no layout/tokens or
other design changes. Browser assertions/allowlists remain unchanged. This functional
reconciliation exception is documented in decision0006 and final handoff.
