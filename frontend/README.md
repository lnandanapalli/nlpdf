# NLPDF Frontend

React client for NLPDF — the AI-powered PDF processing tool.

## Tech Stack

| Library              | Purpose                       |
| -------------------- | ----------------------------- |
| React 19             | UI framework                  |
| TypeScript           | Type safety                   |
| Vite                 | Build tooling and dev server  |
| MUI (Material UI) 7  | Component library and theming |
| Lucide React         | Icons                         |
| Axios                | HTTP client                   |
| React Dropzone       | Drag-and-drop file uploads    |
| Cloudflare Turnstile | Bot protection (CAPTCHA)      |

## Structure

```
frontend/src/
├── components/
│   ├── AuthScreen.tsx      # Login, signup, and OTP verification
│   ├── CommandInput.tsx     # Natural language input with suggestion chips
│   ├── DragDropZone.tsx     # PDF drag-and-drop upload area
│   ├── ProcessingState.tsx  # Loading spinner during AI processing
│   └── ResultCard.tsx       # Download result and reset
├── services/
│   └── api.ts               # Axios client, API URL, and PDF processing
├── App.tsx                   # Root layout, auth gating, and state machine
├── index.css                 # Global reset and custom scrollbar
├── main.tsx                  # React entry point with ThemeProvider
└── theme.ts                  # MUI dark theme (Google Material palette)
```

## Getting Started

### Prerequisites

- Node.js 18+
- The backend API running at `http://127.0.0.1:8000` (see [root README](../README.md))

### Setup

1. **Install dependencies:**

   ```bash
   npm install
   ```

2. **Start the dev server:**

   ```bash
   npm run dev
   ```

3. **Open:** [http://localhost:5173](http://localhost:5173)

### Environment Variables

| Variable            | Default                 | Description     |
| ------------------- | ----------------------- | --------------- |
| `VITE_API_BASE_URL` | `http://127.0.0.1:8000` | Backend API URL |

Override via a `.env` file or inline:

```bash
VITE_API_BASE_URL=https://api.example.com npm run dev
```

## Design

- **Dark mode** using Google's Material Dark palette (`#202124` background, `#8ab4f8` primary).
- **All colours are theme-derived** — components use `useTheme()` and MUI `sx` palette tokens; no hardcoded hex values outside `theme.ts`.
- **Responsive layout** using flexbox with `minHeight: 100dvh`. No fixed heights or viewport-width hacks.
- **Inter** as the primary typeface with Roboto as fallback.

## Scripts

```bash
npm run dev       # Start Vite dev server with HMR
npm run build     # Type-check and build for production
npm run lint      # Run ESLint
npm run preview   # Preview the production build locally
```
