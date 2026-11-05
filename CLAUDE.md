# CLAUDE.md - AIONEXT Package Factory Instructions

## Project Overview

This is the AIONEXT Package Factory - an autonomous system for building, maintaining, and deploying high-quality open-source packages.

**Tagline:** Build ~What You Want

## Repository Structure

```
Git-Packages/
├── .github/                    # Org-wide workflows, policies, templates
├── packages/
│   ├── django-cron-next/       # Python - Django async cron scheduler
│   ├── kafkajs-next/           # TypeScript - Type-safe Kafka client
│   ├── influxdb-rust-next/     # Rust - InfluxDB 3.x FlightSQL client
│   ├── markdown-pdf-next/      # TypeScript - PDF/A converter
│   └── universal-completion/   # Go - CLI completion generator
├── tools/
│   ├── build-orchestrator/     # Pipeline orchestrator
│   ├── deploy-validator/       # Deployment gate
│   ├── health-monitor/         # Background monitoring
│   └── package-factory/        # Package scaffolding tool
└── scripts/                    # Automation scripts
```

## Current Package Scaffolds

All 9 packages have been scaffolded with:
- ✅ Source code structure
- ✅ Package configuration (package.json, Cargo.toml, pyproject.toml, go.mod)
- ✅ TypeScript configs / build configs
- ✅ Core implementation files
- ✅ Tests structure
- ✅ README.md
- ✅ GitHub workflows (CI, deploy-gate, nightly-audit)

## Pipeline Stages

```
BUILD → REVIEW → TEST → FIX → TEST → REBUILD → VALIDATE → TEST → DEPLOY
```

## Key Commands

### Per Package
```bash
# TypeScript packages
cd packages/kafkajs-next
npm install
npm run build
npm run test
npm run lint

# Python packages
cd packages/django-cron-next
pip install -e ".[dev]"
pytest
ruff check .

# Rust packages
cd packages/influxdb-rust-next
cargo build
cargo test
cargo clippy

# Go packages
cd packages/universal-completion
go build ./...
go test ./...
```

### Tools
```bash
# Build orchestrator
cd tools/build-orchestrator
npm run build
node dist/index.js run --config pipeline.yaml

# Deploy validator
cd tools/deploy-validator
npm run build
node dist/index.js validate --config deploy.yaml

# Health monitor
cd tools/health-monitor
npm run build
node dist/index.js start --config monitor.yaml

# Package factory
cd tools/package-factory
npm run build
node dist/index.js create --template typescript --name my-package
```

## GitHub Integration

- **Org**: AIONEXT (user account, not organization)
- **Token**: Configured with full repo permissions
- **Workflows**: CI, deploy-gate, nightly-audit in .github/workflows/
- **Branch Protection**: Enabled on all repos (main branch)
- **Dependabot**: Daily dependency updates configured
- **CodeQL**: Security scanning enabled

## Automation Rules

1. **Never push broken code** - All CI checks must pass
2. **Auto-fix on lint** - Pre-commit hooks run formatters
3. **Security first** - CodeQL + dependency scanning on every PR
4. **Nightly audits** - Full security/dependency review at 2 AM UTC
5. **Deploy gate** - Validation required before any deployment
6. **Health monitoring** - Continuous package health checks

## Package Standards

| Aspect | Standard |
|--------|----------|
| TypeScript | ES2022, strict mode, NodeNext modules |
| Python | 3.11+, ruff, pytest, hatchling |
| Rust | 2021 edition, clippy, cargo-audit |
| Go | 1.22+, standard library first |
| Tests | Unit + integration, >80% coverage |
| Docs | README + API docs, CHANGELOG |
| Release | Semantic versioning, conventional commits |

## Adding New Packages

Use the package-factory:
```bash
cd tools/package-factory
npm run build
node dist/index.js create \
  --template typescript \
  --name my-new-package \
  --description "What it does" \
  --features "feature1,feature2"
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| CI failing | Check workflow logs, run locally first |
| Dependencies outdated | Dependabot PRs auto-created daily |
| Security alert | CodeQL findings in Security tab |
| Deploy blocked | Run deploy-validator locally |
| Health check failing | Check health-monitor logs |

## Resources

- **GitHub**: https://github.com/AIONEXT
- **Packages**: 9 repos under AIONEXT user
- **Workflows**: .github/workflows/ in each repo
- **Monitoring**: health-monitor metrics on :9090/metrics