# Strong Start Agent

A modular grant workspace for CommuniHacks. It covers discovering funding, capturing official requirements, retrieving organizational evidence, drafting and reviewing answers, and transferring approved content into forms. The current integration connects exact C-approved answers to selected-field Chromium prefill on a registered representative portal. Real PostgreSQL/A4 pack replacement guards managed pending work. C state now supports durable PostgreSQL persistence and explicit memory fixtures. Synthetic data and fixture approvals remain labelled; production prefill is disabled. TigerData verification is pending an isolated owner-selected target.

- Working agreement: [AGENTS.md](AGENTS.md) (also imported by `CLAUDE.md`)
- Engineering baseline: [docs/engineering/StrongStart_Engineering_Plan.md](docs/engineering/StrongStart_Engineering_Plan.md) v1.1 and the [86-check catalog](docs/engineering/StrongStart_Check_Catalog.json). Implementation status is recorded per rule; this increment does not claim all checks or project-wide gates complete
- Setup and commands: [docs/setup/README.md](docs/setup/README.md)
- Ownership: [docs/coordination/ownership.md](docs/coordination/ownership.md)
- Setup report: [docs/handoffs/setup/INIT-001-setup-report.md](docs/handoffs/setup/INIT-001-setup-report.md)

```text
apps/web                 React + TypeScript + Vite shell (feature entry points per lane)
services/api             FastAPI host, health/readiness/capabilities, feature routers
packages/contracts       Pydantic contracts -> JSON Schema -> generated TypeScript
migrations               Alembic history through 0009_durable_applications
infra                    Local PostgreSQL (Docker Compose)
tests                    contracts, unit, smoke (db), browser; shared synthetic fixtures
docs                     engineering baseline, decisions, specs, coordination, handoffs
```

Quick start: `make bootstrap && make db-up && make smoke && make check`.


Current integration: [INT-001 handoff](docs/handoffs/integration/int-001-approved-content-currentness-r1.md),
[manual guide](docs/handoffs/integration/int-001-manual-test-guide.md), and
[functional UI contract for Sawaab](docs/handoffs/integration/int-001-ui-contract.md).
DATA-001 implements durable C state with local PostgreSQL/restart/Chromium evidence. See [the current handoff](docs/handoffs/data/data-001-durable-applications-r1.md) and [TigerData setup](docs/setup/tigerdata.md). Hosted TigerData verification (migration, roles, verify, real API restart, backup/restore into a separate service) was performed 2026-11-08; owner acceptance of the pinned provider TLS root is the remaining gate; DATA-002 B/artifact durability and complete A-evidence/workspace/policy integration follow.
The repository is now `thegeekyqazi/strong-start-agent`; historical GitHub links redirect.
