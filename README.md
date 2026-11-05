# AIONEXT Package Factory

> **Tagline:** Build ~What You Want

Autonomous package factory for building, maintaining, and deploying high-quality open-source packages.

## Repository Structure

```
Git-Packages/
├── .github/                    # Org-wide workflows, policies, templates
├── django-cron-next/           # Modern async cron scheduler for Django 4.x/5.x
├── kafkajs-next/               # TypeScript-first Kafka client with schema validation
├── influxdb-rust-next/         # Native Rust client for InfluxDB 3.x (IOx)
├── markdown-pdf-next/          # Modern Markdown to PDF converter
├── universal-completion/       # Universal CLI completion generator (Go)
├── build-orchestrator/         # Build-Review-Test-Fix-Rebuild-Validate-Test-Deploy pipeline
├── deploy-validator/           # Zero-fault deployment gate
├── health-monitor/             # Background health and security monitoring
└── package-factory/            # Meta-tool to spawn new package repos
```

## Pipeline Flow

```
BUILD → REVIEW → TEST → FIX → TEST → REBUILD → VALIDATE → TEST → DEPLOY
```

## Quick Start

```bash
# Clone all repos
gh repo list AIONEXT --limit 20 --json name -q '.[].name' | xargs -I {} gh repo clone AIONEXT/{}

# Or use the package-factory to create new packages
cd package-factory
npm run build
node dist/index.js create --template typescript --name my-package --description "My awesome package"
```

## Package Status

| Package | Language | Status | Description |
|---------|----------|--------|-------------|
| django-cron-next | Python | 🚧 Scaffold | Modern async cron scheduler for Django |
| kafkajs-next | TypeScript | 🚧 Scaffold | Type-safe Kafka client with Zod validation |
| influxdb-rust-next | Rust | 🚧 Scaffold | FlightSQL/Arrow client for InfluxDB 3.x |
| markdown-pdf-next | TypeScript | 🚧 Scaffold | PDF/A, accessibility, streaming converter |
| universal-completion | Go | 🚧 Scaffold | Universal CLI completion generator |
| build-orchestrator | TypeScript | 🚧 Scaffold | Full CI/CD pipeline orchestrator |
| deploy-validator | TypeScript | 🚧 Scaffold | Zero-fault deployment validation |
| health-monitor | TypeScript | 🚧 Scaffold | Background health monitoring |
| package-factory | TypeScript | 🚧 Scaffold | Meta-tool for spawning packages |

## Development

Each package follows the standard pipeline:

1. **Build** - Compile, type-check, bundle
2. **Review** - Lint, format, security scan
3. **Test** - Unit, integration, contract tests
4. **Fix** - Auto-fix linting, update dependencies
5. **Test** - Regression testing
6. **Rebuild** - Release artifacts
7. **Validate** - Security, performance, contract checks
8. **Test** - Smoke tests, canary deployment
9. **Deploy** - Publish to npm/crates.io/PyPI, tag release

## Automation

- **Dependabot**: Daily dependency updates
- **CodeQL**: Security scanning on every PR
- **Nightly Audit**: Full security and dependency audit
- **Health Monitor**: Continuous package health checks
- **Deploy Validator**: Gate before production deployment

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes following the pipeline
4. Submit PR with passing checks
5. Deploy after review

## License

MIT License - see individual packages for details.

---

**AIONEXT** - Build ~What You Want