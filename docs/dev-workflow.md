# Dev Workflow

Local setup notes for CLI + dashboard development.

## Install
```bash
pip install -e .
debatebench init
```

## Run the CLI (example)
```bash
debatebench run --sample-topics 3 --debates-per-pair 1 --run-tag demo
```

## Dashboard local dev
```bash
cd dashboard
pnpm install
pnpm dev
# open http://localhost:3000
```

## Useful paths
- Configs: `configs/`
- Results: `results/`
- Dashboard app: `dashboard/`

## Notes
- Keep `.env` in repo root for CLI secrets.
- Keep `dashboard/.env` for dashboard secrets and S3 config.
