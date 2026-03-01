# Dynaplan

Open-source enterprise planning platform. A full-featured replacement for Anaplan.

## Tech Stack

- **Frontend**: Next.js 15, TypeScript, Tailwind CSS, shadcn/ui
- **Backend**: Python, FastAPI, SQLAlchemy, NumPy/Pandas
- **Database**: PostgreSQL, Redis

## Features

- Multidimensional modeling with formula engine
- Modules, line items, and dimensions (Anaplan-compatible paradigm)
- High-performance grid UI with pivot/filter
- Dashboard builder with charts
- Scenario planning & what-if analysis
- Real-time collaboration
- CSV/Excel import/export
- Role-based access control
- REST API for integrations

## Getting Started

### Backend
```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend
```bash
cd frontend
bun install
bun dev
```

## Development

This project uses Claude Code autonomous workflow patterns. See `CLAUDE.md` for development conventions and `features.json` for the full feature roadmap.

## License

MIT
