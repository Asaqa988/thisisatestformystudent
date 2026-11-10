# NEXUS frontend

Next.js 16 (App Router), TypeScript, Tailwind CSS 4 and shadcn/ui.

```
src/
├── app/
│   ├── (app)/              pages inside the NEXUS shell
│   │   ├── page.tsx        Dashboard
│   │   ├── inbox/          Unified Inbox
│   │   └── customers/ ...  upcoming features, clearly marked
│   ├── api/health/         liveness check for the container
│   ├── api/nexus/[...path] server-side proxy to the NEXUS backend
│   └── globals.css         design tokens: warm paper, petrol ink, one amber signal
├── components/
│   ├── shell/              sidebar, drawer, page header
│   ├── dashboard/          stat cards, needs-a-reply, event stream
│   ├── inbox/              conversation list, thread, composer, details
│   └── ui/                 shadcn/ui components
├── hooks/use-nexus.ts      data hooks (polling)
└── lib/                    API client, NEXUS types, formatting
```

The browser only calls `/api/nexus/*`. The proxy route forwards to the backend
address in `NEXUS_API_URL` (default `http://localhost:8100`).

```bash
npm install
npm run dev -- --port 3100   # needs the backend running on port 8100
npm run lint
npm run build
```

Note: this Next.js version has conventions that differ from older tutorials.
`AGENTS.md` points to the documentation bundled in `node_modules/next/dist/docs/`.
