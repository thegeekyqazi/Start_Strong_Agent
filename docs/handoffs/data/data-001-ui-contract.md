# DATA-001 narrow UI contract for Sawaab

Before functional edits: expose backend/durability metadata separately from fixture/
simulation provenance in workspace/history/capabilities. Applications and Review retain
current layout/styles/controls; replace process-local store wording only when durable
metadata actually says postgres. A fixture reviewer remains a fixture reviewer even in
TigerData. API restarts preserve C state, but old B plans still need preparation again.
No Sawaab redesign branch is integrated by this task. Final field/component changes and
validation will be recorded here after implementation.
