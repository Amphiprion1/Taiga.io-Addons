# Taiga.io-addons

Overlay kit for **official self-hosted Taiga 6 Docker**. This repo does not fork `taiga-docker`, `taiga-back`, or `taiga-front`.

Planning pack (implementation not started):

| Artifact | Path |
| --- | --- |
| Light PRD | [docs/planning/prd.md](docs/planning/prd.md) |
| Architecture (human) | [docs/planning/architecture.md](docs/planning/architecture.md) |
| Architecture spine | [docs/planning/ARCHITECTURE-SPINE.md](docs/planning/ARCHITECTURE-SPINE.md) |
| Epics + stories | [docs/planning/epics.md](docs/planning/epics.md) |
| Sprint status | [docs/implementation/sprint-status.yaml](docs/implementation/sprint-status.yaml) |
| First story (ready-for-dev) | [docs/implementation/1-1-overlay-scaffolding.md](docs/implementation/1-1-overlay-scaffolding.md) |

Next implementation step: `bmad-dev-story` on **1.1 Overlay scaffolding**.

## Tests

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```
