# `frontend/` — the React app

What users see in the browser. Built with **React** (a JavaScript library for building
pages out of reusable pieces called *components*) and **Vite** (the tool that runs it
during development).

| File / folder | What it does |
|---|---|
| `index.html` | The single HTML page. React fills in `<div id="root">`. |
| `vite.config.js` | Dev server settings. Forwards `/api/...` requests to the FastAPI backend on port 8000. |
| `package.json` | List of JavaScript packages (like `requirements.txt` for Python). |
| `src/main.jsx` | Starts React. |
| `src/App.jsx` | The root component. It becomes the page router in Step 3. |
| `src/api.js` | The only file that calls the backend. |
| `src/components/` | Reusable pieces of UI. |
| `src/styles.css` | All styling, with colours as CSS variables. |

Run it (from this folder):

```powershell
npm install     # first time only
npm run dev     # then open http://localhost:5173
```

The backend must also be running (`uvicorn pantrypilot.web.main:app --reload` from the project root).
