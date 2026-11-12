import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { apiRequest, ApiError, newIdempotencyKey } from "../api/client";
import type { Progress } from "../api/types";
import { Inboxic, LockedSilhouette } from "../components/Creatures";
import { ErrorState, Loading, ProgressBar, StatusBadge, useToast } from "../components/ui";
import { formatDateTime } from "../lib/format";

export function CompanionsPage() {
  const [progress, setProgress] = useState<Progress | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const toast = useToast();

  const load = useCallback(async () => {
    setError(null);
    try {
      setProgress(await apiRequest<Progress>("GET", "/api/progress"));
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) return;
      setError(e instanceof Error ? e.message : "Could not load progress.");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function start(reset: boolean) {
    if (reset && !window.confirm("Reset the five practice cases? Earned XP and achievements are kept and cannot be earned twice.")) return;
    setBusy(true);
    try {
      const p = await apiRequest<Progress>("POST", reset ? "/api/practice/reset" : "/api/practice/start", { idempotencyKey: newIdempotencyKey() });
      setProgress(p);
      toast("info", reset ? "Practice cases reset. XP already earned is kept." : "Practice cases are ready.");
    } catch (e) {
      toast("danger", e instanceof Error ? e.message : "Could not update the challenge.");
    } finally {
      setBusy(false);
    }
  }

  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!progress) return <Loading label="Loading companions" />;

  const c = progress.companions.active;
  const started = progress.cases.some((x) => x.inquiryId);
  const nextXp = progress.nextLevelXp;

  return (
    <div className="companions">
      <h1>Companion collection</h1>
      <p className="muted">Companions grow when you complete measurable review work. They are a training aid; the business workflow always comes first.</p>

      <section className="companion-hero card" aria-labelledby="inboxic-title">
        <div className="companion-art">
          <Inboxic size={200} />
        </div>
        <div className="companion-info">
          <p className="eyebrow">Active companion</p>
          <h2 id="inboxic-title">{c.name}</h2>
          <p>
            {c.focus} · <span className="badge badge-cat-manual_review">{c.affinity} affinity</span>
          </p>
          <p>
            Signature ability: <strong>{c.signature}</strong>. Sorts leads and flags urgent requests so the right person sees them first.
          </p>
          <p className="level-line">
            Level {c.level} · {c.stage}
          </p>
          <ProgressBar value={progress.xp - progress.levelFloorXp} max={(nextXp ?? progress.maxXp) - progress.levelFloorXp || 1} label="Progress to next level" />
          <p className="small muted">
            {progress.xp} XP total{nextXp ? ` · ${nextXp - progress.xp} XP to level ${c.level + 1}` : " · maximum level reached"} · {progress.maxXp} XP available
          </p>
        </div>
      </section>

      <section className="card" aria-labelledby="rush-title">
        <div className="card-head">
          <h2 id="rush-title">Monday Morning Rush</h2>
          <div className="btn-row">
            {!started && (
              <button type="button" className="btn btn-primary" onClick={() => start(false)} disabled={busy}>
                Start challenge
              </button>
            )}
            {started && (
              <>
                <Link className="btn btn-primary" to="/?workspace=practice">
                  Open practice queue
                </Link>
                <button type="button" className="btn btn-ghost" onClick={() => start(true)} disabled={busy}>
                  Reset cases
                </button>
              </>
            )}
          </div>
        </div>
        <p className="practice-note" role="note">
          {progress.disclaimer} XP is awarded once per criterion when a case is approved or resolved, so retries and resets never double-count.
        </p>
        <ol className="case-list">
          {progress.cases.map((k, i) => (
            <li key={k.caseId} className={k.complete ? "case complete" : "case"}>
              <div className="case-head">
                <h3>
                  {i + 1}. {k.title}
                </h3>
                {k.status && <StatusBadge status={k.status} />}
                {k.complete && <span className="badge badge-success">✓ Correctly reviewed</span>}
              </div>
              <p className="small muted">{k.goal}</p>
              <ul className="criteria">
                {k.criteria.map((cr) => (
                  <li key={cr.id} className={cr.earned ? "earned" : ""}>
                    <span aria-hidden="true">{cr.earned ? "✓" : "○"}</span>
                    <span>
                      {cr.label} <span className="xp">+{cr.xp} XP</span>
                      <span className="sr-only">{cr.earned ? " (earned)" : " (not yet earned)"}</span>
                    </span>
                  </li>
                ))}
              </ul>
              {k.inquiryId && (
                <Link to={`/inquiries/${k.inquiryId}`} className="small">
                  Open case {i + 1}
                </Link>
              )}
            </li>
          ))}
        </ol>
      </section>

      <section aria-labelledby="ach-title">
        <h2 id="ach-title">Achievements</h2>
        <div className="card-grid">
          {progress.achievements.map((a) => (
            <article key={a.id} className={`achievement card ${a.unlocked ? "unlocked" : "locked"}`}>
              <div className="ach-medal" aria-hidden="true">
                {a.unlocked ? "★" : "☆"}
              </div>
              <h3>{a.name}</h3>
              <p>{a.description}</p>
              <p className="small">
                <strong>Unlocks when:</strong> {a.unlockRule}
              </p>
              <p className="small">
                {a.unlocked ? (
                  <span className="badge badge-success">Unlocked {formatDateTime(a.unlockedAt)}</span>
                ) : (
                  <span className="badge badge-muted">Locked</span>
                )}{" "}
                <span className="xp">+{a.xp} XP</span>
              </p>
            </article>
          ))}
        </div>
      </section>

      <section aria-labelledby="planned-title">
        <h2 id="planned-title">Planned companions</h2>
        <p className="muted">Future CloudQuest modules. They are locked because their modules have not been built yet, not because of missing XP.</p>
        <div className="card-grid four">
          {progress.companions.planned.map((p) => (
            <article key={p.id} className="card planned">
              <LockedSilhouette id={p.id} name={p.name} size={110} />
              <h3>{p.name}</h3>
              <p className="small">{p.focus}</p>
              <p className="small muted">Signature ability: {p.signature}</p>
              <span className="badge badge-muted">Locked · Planned</span>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
