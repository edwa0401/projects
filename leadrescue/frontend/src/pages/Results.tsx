import { useCallback, useEffect, useState } from "react";
import { apiRequest, ApiError } from "../api/client";
import type { Metrics } from "../api/types";
import { ErrorState, Loading } from "../components/ui";
import { formatPercent } from "../lib/format";
import { CATEGORY_LABEL, STATUS_LABEL } from "../lib/labels";

export function ResultsPage() {
  const [m, setM] = useState<Metrics | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setM(await apiRequest<Metrics>("GET", "/api/metrics"));
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) return;
      setError(e instanceof Error ? e.message : "Could not load results.");
    }
  }, []);
  useEffect(() => {
    load();
  }, [load]);

  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!m) return <Loading label="Loading results" />;

  const t = m.targets;
  const reviewMet = m.minutesToFirstReview.median !== null ? m.minutesToFirstReview.median <= t.medianMinutesToFirstReview.value : null;
  const resolveMet = m.hoursToResolution.median !== null ? m.hoursToResolution.median <= t.medianHoursToResolution.value : null;
  const categories = Object.entries(m.byCategory).map(([k, v]) => [CATEGORY_LABEL[k as keyof typeof CATEGORY_LABEL] ?? "Uncategorized", v] as [string, number]);
  const statuses = Object.entries(m.byStatus).map(([k, v]) => [STATUS_LABEL[k as keyof typeof STATUS_LABEL] ?? k, v] as [string, number]);

  return (
    <div className="results">
      <h1>Business results</h1>
      <div className="legend-row" aria-label="How to read this page">
        <span className="badge badge-measured">Measured</span> calculated from records in this environment
        <span className="badge badge-target">Target</span> a goal, not a result
        {m.syntheticRecordCount > 0 && (
          <>
            <span className="badge badge-sample">Sample data</span> synthetic seed records
          </>
        )}
      </div>
      <p className={m.syntheticRecordCount > 0 ? "data-note sample" : "data-note"} role="note">
        {m.dataNote} Practice challenge records are excluded.
      </p>

      {m.recordCount === 0 ? (
        <p className="muted">No business records yet. Add an inquiry to start measuring.</p>
      ) : (
        <>
          <section className="kpi-grid" aria-label="Key measures">
            <Kpi
              label="Median time to first review"
              value={m.minutesToFirstReview.median !== null ? `${m.minutesToFirstReview.median} min` : "No data"}
              sub={`${m.minutesToFirstReview.count} reviewed · mean ${m.minutesToFirstReview.mean ?? "–"} min`}
              target={`at most ${t.medianMinutesToFirstReview.value} min`}
              met={reviewMet}
              sample={m.syntheticRecordCount > 0}
            />
            <Kpi
              label="Median time to resolution"
              value={m.hoursToResolution.median !== null ? `${m.hoursToResolution.median} hr` : "No data"}
              sub={`${m.hoursToResolution.count} resolved · mean ${m.hoursToResolution.mean ?? "–"} hr`}
              target={`at most ${t.medianHoursToResolution.value} hr`}
              met={resolveMet}
              sample={m.syntheticRecordCount > 0}
            />
            <Kpi
              label="AI category correction rate"
              value={formatPercent(m.aiCorrection.categoryCorrectionRate)}
              sub={`${m.aiCorrection.categoryCorrections} of ${m.aiCorrection.reviewedCount} approved or resolved records changed by staff`}
              sample={m.syntheticRecordCount > 0}
            />
            <Kpi
              label="AI priority correction rate"
              value={formatPercent(m.aiCorrection.priorityCorrectionRate)}
              sub={`${m.aiCorrection.priorityCorrections} of ${m.aiCorrection.reviewedCount} records`}
              sample={m.syntheticRecordCount > 0}
            />
          </section>

          <div className="grid-2">
            <BarChart title="Requests by category" rows={categories} />
            <BarChart title="Requests by status" rows={statuses} />
          </div>
        </>
      )}

      <section className="card" aria-labelledby="eval-title">
        <h2 id="eval-title">AI evaluation targets</h2>
        <p>
          Classification quality is measured offline against a separate labeled set of 52 synthetic inquiries (not the practice cases). Run{" "}
          <code>npm run eval</code> for the demo analyzer or <code>npm run eval:bedrock</code> for a live model.
        </p>
        <table className="data-table">
          <caption className="sr-only">Evaluation targets</caption>
          <thead>
            <tr>
              <th scope="col">Measure</th>
              <th scope="col">Target</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Classification accuracy</td>
              <td>
                <span className="badge badge-target">Target</span> at least 90%
              </td>
            </tr>
            <tr>
              <td>Predefined urgent cases flagged</td>
              <td>
                <span className="badge badge-target">Target</span> all of them
              </td>
            </tr>
            <tr>
              <td>Invented facts in evaluated extractions</td>
              <td>
                <span className="badge badge-target">Target</span> none
              </td>
            </tr>
          </tbody>
        </table>
        <p className="small muted">
          Targets are goals, not guarantees. Results apply to the synthetic evaluation set only. See <code>eval/results/</code> for the latest recorded
          runs, including misses.
        </p>
      </section>
    </div>
  );
}

function Kpi({ label, value, sub, target, met, sample }: { label: string; value: string; sub: string; target?: string; met?: boolean | null; sample: boolean }) {
  return (
    <div className="kpi card">
      <span className="stat-label">{label}</span>
      <span className="kpi-value">{value}</span>
      <span className="small muted">{sub}</span>
      <div className="kpi-tags">
        <span className="badge badge-measured">Measured</span>
        {sample && <span className="badge badge-sample">Sample data</span>}
      </div>
      {target && (
        <p className="small kpi-target">
          <span className="badge badge-target">Target</span> {target}
          {met !== null && met !== undefined && (
            <span className={met ? "met" : "unmet"}>
              {met ? " ✓ Meets target" : " ✗ Above target"}
            </span>
          )}
        </p>
      )}
    </div>
  );
}

function BarChart({ title, rows }: { title: string; rows: [string, number][] }) {
  const max = Math.max(1, ...rows.map(([, v]) => v));
  const total = rows.reduce((s, [, v]) => s + v, 0);
  return (
    <section className="card chart" aria-label={title}>
      <h2>{title}</h2>
      <div className="bars" aria-hidden="true">
        {rows.map(([label, v]) => (
          <div className="bar-row" key={label} title={`${label}: ${v} of ${total}`}>
            <span className="bar-label">{label}</span>
            <span className="bar-track">
              <span className="bar-fill" style={{ width: `${(v / max) * 100}%` }} />
            </span>
            <span className="bar-value">{v}</span>
          </div>
        ))}
      </div>
      <details>
        <summary>View as table</summary>
        <table className="data-table">
          <caption className="sr-only">{title}</caption>
          <thead>
            <tr>
              <th scope="col">Group</th>
              <th scope="col">Count</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(([l, v]) => (
              <tr key={l}>
                <td>{l}</td>
                <td>{v}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
      <p className="sr-only">{rows.map(([l, v]) => `${l}: ${v}`).join(", ")}</p>
    </section>
  );
}
