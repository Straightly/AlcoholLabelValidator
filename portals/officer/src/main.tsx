import { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

type Finding = {
  rule_id: string;
  field_name: string;
  result: string;
  expected: string;
  observed: string | null;
  confidence: number;
  explanation: string;
  source: string;
};

type Review = {
  submission_id: string;
  application_id: string;
  source_label: string;
  processing_duration_ms: number;
  findings: Finding[];
  suggested_rejection_reason: string | null;
};

function App() {
  const [loggedIn, setLoggedIn] = useState(false);
  const [queue, setQueue] = useState<Review[]>([]);
  const [selected, setSelected] = useState<Review | null>(null);
  const [reason, setReason] = useState("");
  const [message, setMessage] = useState("");

  async function refresh() {
    const response = await fetch("/api/review-queue");
    const items = response.ok ? await response.json() : [];
    setQueue(items);
    setSelected((current) => current ?? items[0] ?? null);
  }

  async function processSampleIntake() {
    const response = await fetch("/api/demo/process-sample-intake", { method: "POST" });
    if (!response.ok) {
      setMessage(`Sample intake failed: ${await response.text()}`);
      return;
    }
    const result = await response.json();
    setMessage(
      result.packages_imported > 0
        ? `Imported ${result.packages_imported} package and preprocessed ${result.applications_preprocessed} applications.`
        : "Sample intake was already processed; no artifacts were overwritten."
    );
    setSelected(null);
    await refresh();
  }

  useEffect(() => {
    if (loggedIn) void refresh();
  }, [loggedIn]);

  useEffect(() => {
    if (selected) setReason(selected.suggested_rejection_reason ?? "All implemented checks match.");
  }, [selected]);

  async function decide(decision: "Approved" | "Rejected") {
    if (!selected) return;
    const response = await fetch(
      `/api/reviews/${selected.submission_id}/${selected.application_id}/decision`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          decision,
          public_reason: reason,
          officer_name: "Demo Compliance Officer"
        })
      }
    );
    setMessage(response.ok ? `${decision} decision recorded.` : await response.text());
    setSelected(null);
    await refresh();
  }

  if (!loggedIn) {
    return (
      <main className="login-shell">
        <section className="login-card">
          <p className="kicker">Compliance Officer Portal</p>
          <h1>Evidence first.<br />Judgment stays human.</h1>
          <p>Demo identity: Compliance Officer 014</p>
          <button onClick={() => setLoggedIn(true)}>Open review queue</button>
        </section>
      </main>
    );
  }

  return (
    <main>
      <aside>
        <p className="kicker">Review Queue</p>
        <h1>{queue.length.toString().padStart(2, "0")}</h1>
        <p>applications ready</p>
        <button className="process" onClick={() => void processSampleIntake()}>
          Process Sample Intake
        </button>
        <button className="refresh" onClick={() => void refresh()}>Refresh queue</button>
        <nav>
          {queue.map((item) => (
            <button
              className={selected?.application_id === item.application_id ? "active" : ""}
              key={`${item.submission_id}-${item.application_id}`}
              onClick={() => setSelected(item)}
            >
              <span>{item.application_id}</span>
              <small>{item.source_label}</small>
            </button>
          ))}
        </nav>
      </aside>
      <section className="workspace">
        <header>
          <div>
            <p className="kicker">Application Review</p>
            <h2>{selected?.application_id ?? "Queue clear"}</h2>
          </div>
          <p>Officer: <strong>Compliance Officer 014</strong></p>
        </header>
        <p className="boundary">
          Standalone procurement POC. Synthetic label-review fields only; no COLA connection
          and no PII enters this application.
        </p>
        {!selected && <div className="empty">No unreviewed applications are waiting.</div>}
        {selected && (
          <>
            <div className="context">
              <span>Source: <strong>{selected.source_label}</strong></span>
              <span>Analysis: <strong>{selected.processing_duration_ms} ms</strong></span>
            </div>
            <div className="findings">
              {selected.findings.map((finding) => (
                <article key={finding.rule_id}>
                  <div className="finding-title">
                    <h3>{finding.field_name.replaceAll("_", " ")}</h3>
                    <span className={`result ${finding.result.toLowerCase().replaceAll(" ", "-")}`}>
                      {finding.result}
                    </span>
                  </div>
                  <dl>
                    <dt>Expected</dt><dd>{finding.expected}</dd>
                    <dt>Evidence</dt><dd>{finding.observed ?? "Not found"}</dd>
                    <dt>Basis</dt><dd>{finding.source}</dd>
                  </dl>
                  <p>{finding.explanation}</p>
                </article>
              ))}
            </div>
            <section className="decision">
              <label>
                Public decision reason
                <textarea value={reason} onChange={(event) => setReason(event.target.value)} />
              </label>
              <div>
                <button className="reject" onClick={() => void decide("Rejected")}>Reject</button>
                <button className="approve" onClick={() => void decide("Approved")}>Approve</button>
              </div>
            </section>
          </>
        )}
        {message && <p className="message">{message}</p>}
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
