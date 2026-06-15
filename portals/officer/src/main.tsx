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

type ImageEvidence = {
  filename: string;
  url: string;
  extracted_text: string;
  confidence: number;
  width: number | null;
  height: number | null;
  blur_score: number | null;
  glare_ratio: number | null;
  quality_flags: string[];
  engine: string;
};

type Review = {
  submission_id: string;
  application_id: string;
  source_label: string;
  processing_duration_ms: number;
  images: ImageEvidence[];
  findings: Finding[];
  suggested_rejection_reason: string | null;
  processing_error: string | null;
};

type IntakeStatus = {
  state: "idle" | "running" | "completed" | "failed";
  message: string;
  started: boolean;
  started_at: string | null;
  finished_at: string | null;
  packages_found: number;
  packages_imported: number;
  packages_skipped: number;
  applications_preprocessed: number;
  applications_needing_manual_review: number;
};

async function responseMessage(response: Response) {
  const body = await response.json().catch(() => null);
  return body?.detail ?? body?.message ?? response.statusText;
}

function normalizeReview(review: Partial<Review>): Review {
  return {
    submission_id: review.submission_id ?? "",
    application_id: review.application_id ?? "",
    source_label: review.source_label ?? "",
    processing_duration_ms: review.processing_duration_ms ?? 0,
    images: (review.images ?? []).map((image) => ({
      filename: image.filename ?? "",
      url: image.url ?? "",
      extracted_text: image.extracted_text ?? "",
      confidence: image.confidence ?? 0,
      width: image.width ?? null,
      height: image.height ?? null,
      blur_score: image.blur_score ?? null,
      glare_ratio: image.glare_ratio ?? null,
      quality_flags: image.quality_flags ?? [],
      engine: image.engine ?? "unknown"
    })),
    findings: review.findings ?? [],
    suggested_rejection_reason: review.suggested_rejection_reason ?? null,
    processing_error: review.processing_error ?? null
  };
}

function App() {
  const [loggedIn, setLoggedIn] = useState(false);
  const [queue, setQueue] = useState<Review[]>([]);
  const [selected, setSelected] = useState<Review | null>(null);
  const [reason, setReason] = useState("");
  const [overrideNote, setOverrideNote] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [intakeStatus, setIntakeStatus] = useState<IntakeStatus | null>(null);
  const [showDetails, setShowDetails] = useState(false);
  const [overrides, setOverrides] = useState<Record<string, boolean>>({});
  const [showOnlyMissing, setShowOnlyMissing] = useState(true);


  async function refresh() {
    const response = await fetch("/api/review-queue");
    if (!response.ok) {
      setMessage(`Queue could not be loaded: ${await responseMessage(response)}`);
      return null;
    }
    const payload = await response.json();
    const items: Review[] = Array.isArray(payload) ? payload.map(normalizeReview) : [];
    setQueue(items);
    setSelected((current) =>
      current ? items.find((item) => item.application_id === current.application_id) ?? items[0] ?? null : items[0] ?? null
    );
    return items;
  }

  async function refreshIntakeStatus() {
    const response = await fetch("/api/demo/process-sample-intake");
    if (!response.ok) return null;
    const status: IntakeStatus = await response.json();
    setIntakeStatus((current) => ({ ...current, ...status, started: status.started ?? current?.started ?? false }));
    if (status.state === "completed") {
      await refresh();
    }
    return status;
  }

  async function refreshWorkspace() {
    setBusy(true);
    try {
      const response = await fetch("/api/demo/refresh-queue", { method: "POST" });
      if (!response.ok) throw new Error(await responseMessage(response));
      const body = await response.json();
      const status = await refreshIntakeStatus();
      const items = await refresh();
      if (status?.state === "running") {
        setMessage(`${body.message} Background preprocessing is still running.`);
      } else if ((items?.length ?? 0) > 0) {
        setMessage(`${body.message} ${items?.length ?? 0} application(s) ready for review.`);
      } else {
        setMessage("Queue restored. No unreviewed applications are ready yet.");
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "The operation failed.");
    } finally {
      setBusy(false);
    }
  }

  async function runAction(url: string, success: (body: any) => string) {
    setBusy(true);
    setMessage("");
    try {
      const response = await fetch(url, { method: "POST" });
      if (!response.ok) throw new Error(await responseMessage(response));
      setMessage(success(await response.json()));
      setSelected(null);
      await refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "The operation failed.");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (loggedIn) void refresh();
  }, [loggedIn]);

  useEffect(() => {
    if (!loggedIn) return;
    void refreshIntakeStatus();
  }, [loggedIn]);

  useEffect(() => {
    if (!loggedIn || intakeStatus?.state !== "running") return;
    const handle = window.setInterval(() => {
      void refreshIntakeStatus();
    }, 1500);
    return () => window.clearInterval(handle);
  }, [loggedIn, intakeStatus?.state]);

  useEffect(() => {
    if (selected) {
      setReason(selected.suggested_rejection_reason ?? "All implemented checks match.");
      setOverrideNote("");
      setOverrides({});
    }
  }, [selected]);

  async function decide(decision: "Approved" | "Rejected") {
    if (!selected || !reason.trim()) return;
    setBusy(true);
    const unresolved = selected.findings.some((finding) => finding.result !== "Match");
    const response = await fetch(
      `/api/reviews/${selected.submission_id}/${selected.application_id}/decision`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          decision,
          public_reason: reason,
          officer_name: "Compliance Officer 014",
          override_note: decision === "Approved" && unresolved ? overrideNote : null
        })
      }
    );
    setMessage(response.ok ? `${decision} decision recorded.` : await responseMessage(response));
    if (response.ok) setSelected(null);
    await refresh();
    setBusy(false);
  }

  if (!loggedIn) {
    return (
      <main className="login-shell">
        <section className="login-card">
          <p className="kicker">Compliance Officer Portal</p>
          <h1>Open The Review Queue</h1>
          <p>
            This prototype pre-processes sample applications in the background,
            then shows the completed results here for officer review.
          </p>
          <p>Demonstration only. The login is not an authorization boundary.</p>
          <button onClick={() => setLoggedIn(true)}>Login</button>
        </section>
      </main>
    );
  }

  const unresolved = selected?.findings.some((finding) => finding.result !== "Match") ?? false;
  const allUnresolvedOverridden = selected
    ? selected.findings.filter((f) => f.result !== "Match").every((f) => overrides[f.rule_id])
    : false;

  return (
    <main>
      <aside>
        <p className="kicker">Review Queue</p>
        <h1>{queue.length.toString().padStart(2, "0")}</h1>
        <p>applications ready</p>
        <nav aria-label="Applications ready for review">
          {queue.map((item) => (
            <button
              className={selected?.application_id === item.application_id ? "active" : ""}
              key={`${item.submission_id}-${item.application_id}`}
              onClick={() => setSelected(item)}
            >
              <span>{item.application_id}</span>
              <small>{item.processing_error ? "Needs attention" : item.source_label}</small>
            </button>
          ))}
        </nav>
        <button className="refresh" disabled={busy} onClick={() => void refreshWorkspace()}>Refresh queue</button>
        <button
          className="reset"
          disabled={busy}
          onClick={() => void runAction("/api/demo/reset", () => "Demo data reset. Select Process Sample Intake to begin again.")}
        >
          Reset Demo Data
        </button>
        <button
          className="process"
          disabled={busy || intakeStatus?.state === "running"}
          onClick={async () => {
            setBusy(true);
            setMessage("");
            try {
              const response = await fetch("/api/demo/process-sample-intake", { method: "POST" });
              if (!response.ok) throw new Error(await responseMessage(response));
              const status: IntakeStatus = await response.json();
              setIntakeStatus(status);
              setMessage(
                status.started
                  ? "Background preprocessing started. This can take a minute or two. The queue will refresh when it finishes."
                  : status.message
              );
            } catch (error) {
              setMessage(error instanceof Error ? error.message : "The operation failed.");
            } finally {
              setBusy(false);
            }
          }}
        >
          {intakeStatus?.state === "running" ? "Preprocessing…" : busy ? "Working…" : "Process Sample Intake"}
        </button>
        {intakeStatus && (
          <section className={`intake-status ${intakeStatus.state}`}>
            <strong>Preprocessing status</strong>
            <p>{intakeStatus.message}</p>
            <small>
              State: {intakeStatus.state}
              {intakeStatus.started_at ? ` · started ${new Date(intakeStatus.started_at).toLocaleTimeString()}` : ""}
              {intakeStatus.finished_at ? ` · finished ${new Date(intakeStatus.finished_at).toLocaleTimeString()}` : ""}
            </small>
            {intakeStatus.state !== "idle" && (
              <small>
                Packages: {intakeStatus.packages_imported}/{intakeStatus.packages_found} imported,
                {" "}Applications: {intakeStatus.applications_preprocessed},
                {" "}Needs officer review: {intakeStatus.applications_needing_manual_review}
              </small>
            )}
          </section>
        )}
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
          Standalone procurement POC. Publication-safe samples only; no COLAs Online connection and no applicant PII.
        </p>
        {!selected && (
          <div className="empty">
            <strong>No unreviewed applications are waiting.</strong>
            <p>
              Select <code>Process Sample Intake</code> to start background preprocessing,
              then wait for the status box to show completion.
            </p>
          </div>
        )}
        {selected && (
          <>
            <div className="context">
              <span>Source: <strong>{selected.source_label}</strong></span>
              <span>Analysis: <strong>{selected.processing_duration_ms} ms</strong></span>
              <div style={{ display: "flex", gap: "1.5rem", alignItems: "center" }}>
                <label style={{ display: "flex", gap: "0.5rem", alignItems: "center", cursor: "pointer", margin: 0, fontWeight: "600" }}>
                  <input
                    type="checkbox"
                    checked={showOnlyMissing}
                    onChange={(e) => setShowOnlyMissing(e.target.checked)}
                  />
                  Show Only Missing Fields
                </label>
                <label style={{ display: "flex", gap: "0.5rem", alignItems: "center", cursor: "pointer", margin: 0, fontWeight: "600" }}>
                  <input
                    type="checkbox"
                    checked={showDetails}
                    onChange={(e) => setShowDetails(e.target.checked)}
                  />
                  Show Technical Details
                </label>
              </div>
            </div>
            <section className="evidence-gallery" aria-label="Label images">
              {selected.images.map((image) => (
                <figure key={image.filename}>
                  <img src={image.url} alt={`Submitted label ${image.filename}`} />
                  <figcaption>
                    <strong>{image.filename}</strong>
                    {showDetails && (
                      <span>{image.engine} · {Math.round(image.confidence * 100)}% confidence</span>
                    )}
                    {image.quality_flags.map((flag) => <span className="quality" key={flag}>{flag}</span>)}
                    {showDetails && (
                      <details><summary>Extracted text</summary><pre>{image.extracted_text}</pre></details>
                    )}
                  </figcaption>
                </figure>
              ))}
            </section>
            <div className="findings">
              {selected.findings.filter((finding) => !showOnlyMissing || finding.result !== "Match").length === 0 ? (
                <div className="empty" style={{ gridColumn: "span 2", marginTop: 0 }}>
                  <strong>All checked fields match perfectly.</strong>
                  <p>There are no missing or unresolved findings to display.</p>
                </div>
              ) : (
                selected.findings
                  .filter((finding) => !showOnlyMissing || finding.result !== "Match")
                  .map((finding) => (
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
                        {showDetails && (
                          <>
                            <dt>Confidence</dt><dd>{Math.round(finding.confidence * 100)}%</dd>
                          </>
                        )}
                        <dt>Basis</dt><dd>{finding.source}</dd>
                      </dl>
                      <p>{finding.explanation}</p>
                      {finding.result !== "Match" && (
                        <label style={{ display: "flex", gap: "0.5rem", alignItems: "center", cursor: "pointer", marginTop: "1rem", fontWeight: "600" }}>
                          <input
                            type="checkbox"
                            checked={!!overrides[finding.rule_id]}
                            onChange={(e) => {
                              const val = e.target.checked;
                              const nextOverrides = { ...overrides, [finding.rule_id]: val };
                              setOverrides(nextOverrides);
                              
                              const unresolvedFindings = selected.findings.filter((f) => f.result !== "Match");
                              const allOverridden = unresolvedFindings.every((f) => nextOverrides[f.rule_id]);
                              if (allOverridden) {
                                setOverrideNote(`Manually verified and approved: ${unresolvedFindings.map((f) => f.field_name.replaceAll("_", " ")).join(", ")}.`);
                                setReason("All implemented checks match or have been manually verified by the compliance officer.");
                              } else {
                                setOverrideNote("");
                                setReason(selected.suggested_rejection_reason ?? "");
                              }
                            }}
                          />
                          Manually verify and override
                        </label>
                      )}
                    </article>
                  ))
              )}
            </div>
            <section className="decision">
              <label>
                Public decision reason
                <textarea required value={reason} onChange={(event) => setReason(event.target.value)} />
              </label>
              {unresolved && (
                <label>
                  Override note required only when approving unresolved findings
                  <textarea value={overrideNote} onChange={(event) => setOverrideNote(event.target.value)} />
                </label>
              )}
              <div>
                <button disabled={busy || !reason.trim()} className="reject" onClick={() => void decide("Rejected")}>Reject</button>
                <button disabled={busy || !reason.trim() || (unresolved && (!overrideNote.trim() || !allUnresolvedOverridden))} className="approve" onClick={() => void decide("Approved")}>Approve</button>
              </div>
            </section>
          </>
        )}
        {message && <p className="message" role="status">{message}</p>}
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
