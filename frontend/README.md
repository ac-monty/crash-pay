# Crash-Pay Frontend

> Overview of the SPA code that runs in the browser.

## Tech Stack

* **React 18** with functional components and hooks.
* **Vite** for lightning-fast dev server and production bundling.
* **Tailwind CSS** – utility-first styling, extended with the project’s **glass UI** custom theme.
* **SVG / PNG Icon Set** under `src/assets` – imported directly by React.
* **APM** instrumentation via Elastic APM RUM agent (injected at runtime).

## Directory Layout

```
frontend/
  Dockerfile              # Nginx lightweight image for prod
  index.html              # Single entry HTML
  vite.config.js          # Build / proxy configuration
  package.json            # Dependencies + scripts
  public/                 # Service-worker, static assets
  src/
    App.jsx               # Top-level router / layout
    index.jsx             # ReactDOM mount + global providers
    index.css             # Tailwind base + custom CSS variables
    components/           # Feature and shared components
      finance/            # Finance dashboard widgets
      FloatingChatAssistant.jsx  # LLM banking assistant widget
      ...
    utils/                # Fetch wrappers, auth helpers, logger, …
    assets/               # 1x / 2x / 3x PNG + SVG icon packs
```

## State Management

* Local component state via `useState` / `useReducer` – no global store.
* Critical user context (JWT, chat session) persisted to `localStorage` for reload survival.
* React Context is currently **not** used; easy to introduce if the app grows.

## Networking

* All API traffic goes through the **API-Gateway** container via an origin-relative base URL (`/api/...`).
* `FloatingChatAssistant` attaches the JWT as `Authorization: Bearer <token>`.
* `fetch` is wrapped in small helpers under `src/utils` (auth, financeApi).
* Project rule: every `curl` / fetch must use a 5-second timeout – enforced in backend, optional here.

## Build & Deployment

1. `docker compose build frontend` (no version field per project policy).
2. Image is a multistage build – Vite build → copy into Nginx-alpine.
3. Served on port **5173** (host) → **80** inside container.

## Security Footnotes

The frontend intentionally contains demonstrable OWASP-LLM findings (e.g. dangerous `innerHTML` rendering in `Chat.js`). These are **deliberate** for the security lab – do not replicate in production code.
