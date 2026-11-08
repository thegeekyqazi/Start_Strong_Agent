# Strong Start Agent

A modular grant workspace for CommuniHacks. It covers discovering funding, capturing official requirements, retrieving organizational evidence, drafting and reviewing answers, and transferring approved content into forms. This repository currently holds the **INIT-001 foundation only**. No product feature is implemented yet.

- Working agreement: [AGENTS.md](AGENTS.md) (also imported by `CLAUDE.md`)
- Engineering baseline: [docs/engineering/StrongStart_Engineering_Plan.md](docs/engineering/StrongStart_Engineering_Plan.md) v1.1 and the [86-check catalog](docs/engineering/StrongStart_Check_Catalog.json). All checks are `planned`
- Setup and commands: [docs/setup/README.md](docs/setup/README.md)
- Ownership: [docs/coordination/ownership.md](docs/coordination/ownership.md)
- Setup report: [docs/handoffs/setup/INIT-001-setup-report.md](docs/handoffs/setup/INIT-001-setup-report.md)

```text
apps/web                 React + TypeScript + Vite shell (feature entry points per lane)
services/api             FastAPI host, health/readiness/capabilities, feature routers
packages/contracts       Pydantic contracts -> JSON Schema -> generated TypeScript
migrations               Alembic history (0001_bootstrap)
infra                    Local PostgreSQL (Docker Compose)
tests                    contracts, unit, smoke (db), browser; shared synthetic fixtures
docs                     engineering baseline, decisions, specs, coordination, handoffs
```

Quick start: `make bootstrap && make db-up && make smoke && make check`.
