# NEXUS AI

An AI-first operating system for marketing agencies: one custom interface in
front of several open-source systems. Built step by step across a nine-lesson
course.

| Lesson | Adds | Status |
|---|---|---|
| 01 | Foundation, NEXUS interface, Chatwoot integration | Built |
| 02 onward | Twenty CRM, Plane, Activepieces, AI agents, approvals | Upcoming |

## Quick start

You need Docker Desktop and Node.js 20.9 or newer.

```bash
git clone <this repository> nexus-ai
cd nexus-ai
node scripts/init-env.mjs        # creates .env with random secrets
docker compose up -d --build     # first run downloads about 3 GB
```

| Open | URL |
|---|---|
| NEXUS interface | http://localhost:3100 |
| NEXUS API docs | http://localhost:8100/docs |
| Chatwoot | http://localhost:3110 |

NEXUS starts without Chatwoot credentials and tells you so. To connect it,
follow **[docs/lessons/lesson-01.md](docs/lessons/lesson-01.md)**.

## Layout

```
nexus-ai/
├── docker-compose.yml        all services for local development
├── .env.example              every setting, with no secret values
├── scripts/init-env.mjs      creates .env and generates secrets
├── frontend/                 Next.js 16, Tailwind CSS 4, shadcn/ui
│   └── src/
│       ├── app/(app)/        pages: dashboard, inbox, upcoming features
│       ├── app/api/nexus/    server-side proxy to the backend
│       ├── components/       shell, dashboard, inbox, ui
│       ├── hooks/            data hooks (polling)
│       └── lib/              API client, NEXUS types, formatting
├── backend/                  FastAPI, SQLAlchemy, Alembic
│   ├── app/
│   │   ├── api/              HTTP routes
│   │   ├── services/         inbox and webhook logic
│   │   ├── integrations/     adapter contract + chatwoot/
│   │   ├── models/           database tables
│   │   ├── schemas.py        normalized NEXUS shapes
│   │   └── cli.py            lesson helper commands
│   ├── migrations/           database schema history
│   └── tests/                pytest suite
└── docs/
    ├── architecture.md       layers, flows, decisions
    ├── api-contracts.md      every endpoint and shape
    ├── deployment.md         Vercel + Railway, protection, gotchas
    └── lessons/lesson-01.md  the lesson: setup, demos, troubleshooting
```

## Everyday commands

```bash
docker compose ps                                  # what is running
docker compose logs -f backend                     # follow backend logs
docker compose exec backend pytest                 # run backend tests
docker compose up -d --build frontend              # rebuild after frontend changes
docker compose down                                # stop everything, keep data
```

`docker compose down -v` also deletes the databases. Use it only when you want
to start from nothing.
