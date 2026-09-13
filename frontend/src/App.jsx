import BackendStatus from "./components/BackendStatus.jsx";

/**
 * App — the root component, i.e. the whole page.
 *
 * In Step 1 it is just a welcome screen plus a check that the backend is reachable.
 * In Step 3 this becomes the place where we choose which page to show
 * (login, restaurant, pantry, driver or admin).
 */
export default function App() {
  return (
    <main className="page">
      <section className="card">
        <h1>
          PantryPilot <span aria-hidden="true">🥫</span>
        </h1>
        <p className="muted">
          An AI agent team that routes surplus food from restaurants to food pantries — and only asks a
          human when there is a real decision to make.
        </p>
        <BackendStatus />
      </section>
    </main>
  );
}
