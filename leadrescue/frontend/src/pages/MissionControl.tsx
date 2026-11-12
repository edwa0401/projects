import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { apiRequest, ApiError, newIdempotencyKey } from "../api/client";
import type { Progress, QueueResponse } from "../api/types";
import { useAppConfig } from "../components/AppShell";
import { Inboxic } from "../components/Creatures";
import { CategoryBadge, EmptyState, ErrorState, PriorityBadge, SkeletonRows, StatusBadge, useToast } from "../components/ui";
import { relativeTime } from "../lib/format";
import { CATEGORIES, CATEGORY_LABEL, CHANNEL_LABEL, PRIORITIES, PRIORITY_LABEL, STATUSES, STATUS_LABEL } from "../lib/labels";

const FILTER_KEYS = ["q", "category", "priority", "status", "assignee"] as const;

export function MissionControlPage() {
  const config = useAppConfig();
  const [params, setParams] = useSearchParams();
  const workspace = params.get("workspace") === "practice" ? "practice" : "business";
  const [data, setData] = useState<QueueResponse | null>(null);
  const [progress, setProgress] = useState<Progress | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState(params.get("q") ?? "");
  const [starting, setStarting] = useState(false);
  const toast = useToast();
  const navigate = useNavigate();

  const filters = Object.fromEntries(FILTER_KEYS.map((k) => [k, params.get(k) ?? ""])) as Record<(typeof FILTER_KEYS)[number], string>;
  const filterKey = FILTER_KEYS.map((k) => filters[k]).join("|");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [queue, prog] = await Promise.all([
        apiRequest<QueueResponse>("GET", "/api/inquiries", { query: { workspace, ...filters } }),
        apiRequest<Progress>("GET", "/api/progress"),
      ]);
      setData(queue);
      setProgress(prog);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) return;
      setError(e instanceof Error ? e.message : "Could not load the queue.");
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspace, filterKey]);

  useEffect(() => {
    load();
  }, [load]);

  // Debounced search kept in the URL so filters survive refresh.
  useEffect(() => {
    const t = window.setTimeout(() => {
      if ((params.get("q") ?? "") !== search) updateParam("q", search);
    }, 300);
    return () => window.clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search]);

  function updateParam(key: string, value: string) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: true });
  }

  function setWorkspace(ws: "business" | "practice") {
    const next = new URLSearchParams();
    if (ws === "practice") next.set("workspace", "practice");
    setSearch("");
    setParams(next);
  }

  async function startRush() {
    setStarting(true);
    try {
      const prog = await apiRequest<Progress>("POST", "/api/practice/start", { idempotencyKey: newIdempotencyKey() });
      setProgress(prog);
      toast("info", "Monday Morning Rush is ready: five practice cases are in your queue.");
      if (workspace !== "practice") setWorkspace("practice");
      else load();
    } catch (e) {
      toast("danger", e instanceof Error ? e.message : "Could not start the challenge.");
    } finally {
      setStarting(false);
    }
  }

  const hasFilters = FILTER_KEYS.some((k) => filters[k]);
  const staffName = (id: string | null) => (id ? config?.staff.find((s) => s.id === id)?.name ?? id : "Unassigned");

  return (
    <div className="mission">
      <section className="mission-hero" aria-labelledby="mc-title">
        <div>
          <p className="eyebrow">Mission control</p>
          <h1 id="mc-title">
            Catch the lead. <span className="accent-italic">Rescue</span> the opportunity.
          </h1>
          <p className="muted-light">Review AI suggestions, correct them, and approve replies. Nothing is sent automatically.</p>
        </div>
        <div className="mission-hero-art" aria-hidden="true">
          <Inboxic size={110} withMail={false} title="" />
          <span className="plate-move">Priority Mind</span>
        </div>
      </section>

      <div className="workspace-tabs" role="tablist" aria-label="Queue">
        <button role="tab" type="button" aria-selected={workspace === "business"} className={workspace === "business" ? "active" : ""} onClick={() => setWorkspace("business")}>
          Business queue
        </button>
        <button role="tab" type="button" aria-selected={workspace === "practice"} className={workspace === "practice" ? "active" : ""} onClick={() => setWorkspace("practice")}>
          Practice: Monday Morning Rush
        </button>
      </div>
      {workspace === "practice" && (
        <p className="practice-note" role="note">
          Practice cases are synthetic, kept separate from business records, and excluded from Business results. Five scenarios demonstrate the
          workflow; they do not establish production accuracy.
        </p>
      )}

      <section className="stat-grid" aria-label="Queue summary">
        <StatCard label="Awaiting review" value={data?.counts.awaitingReview} />
        <StatCard label="Urgent open" value={data?.counts.urgentOpen} tone={data && data.counts.urgentOpen > 0 ? "urgent" : undefined} />
        <StatCard label="Approved drafts" value={data?.counts.approvedDrafts} hint="Ready to copy and send" />
        <StatCard label="Challenge cases completed" value={progress ? `${progress.casesCompleted}/5` : undefined} hint={progress ? `${progress.xp} XP earned` : undefined} />
      </section>

      <section className="queue" aria-labelledby="queue-title">
        <div className="queue-head">
          <h2 id="queue-title">{workspace === "practice" ? "Practice queue" : "Inquiry queue"}</h2>
          <div className="queue-actions">
            {workspace === "practice" ? (
              <button type="button" className="btn btn-secondary" onClick={startRush} disabled={starting}>
                {starting ? "Preparing…" : "Load challenge cases"}
              </button>
            ) : (
              <Link to="/inquiries/new" className="btn btn-primary">
                + New inquiry
              </Link>
            )}
          </div>
        </div>

        <form className="filters" role="search" aria-label="Filter inquiries" onSubmit={(e) => e.preventDefault()}>
          <label className="field field-grow">
            <span>Search</span>
            <input type="search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Name, message, or ID" maxLength={200} />
          </label>
          <FilterSelect label="Category" value={filters.category} onChange={(v) => updateParam("category", v)} options={CATEGORIES.map((c) => [c, CATEGORY_LABEL[c]])} />
          <FilterSelect label="Priority" value={filters.priority} onChange={(v) => updateParam("priority", v)} options={PRIORITIES.map((p) => [p, PRIORITY_LABEL[p]])} />
          <FilterSelect
            label="Status"
            value={filters.status}
            onChange={(v) => updateParam("status", v)}
            options={[["open", "All open"], ...STATUSES.map((s) => [s, STATUS_LABEL[s]] as [string, string])]}
          />
          <FilterSelect
            label="Assigned to"
            value={filters.assignee}
            onChange={(v) => updateParam("assignee", v)}
            options={[["unassigned", "Unassigned"], ...(config?.staff ?? []).map((s) => [s.id, s.name] as [string, string])]}
          />
          {hasFilters && (
            <button
              type="button"
              className="btn btn-ghost btn-sm filters-clear"
              onClick={() => {
                setSearch("");
                setParams(workspace === "practice" ? new URLSearchParams({ workspace: "practice" }) : new URLSearchParams());
              }}
            >
              Clear filters
            </button>
          )}
        </form>

        <div aria-live="polite" className="sr-only">
          {data && !loading ? `${data.items.length} inquiries shown` : ""}
        </div>

        {loading && !data ? (
          <SkeletonRows />
        ) : error ? (
          <ErrorState message={error} onRetry={load} />
        ) : data && data.items.length === 0 ? (
          workspace === "practice" && !hasFilters ? (
            <EmptyState
              title="Start the Monday Morning Rush"
              action={
                <button type="button" className="btn btn-primary" onClick={startRush} disabled={starting}>
                  {starting ? "Preparing…" : "Start challenge"}
                </button>
              }
            >
              Five synthetic inquiries arrive at once. Earn XP by meeting review criteria, not by clicking buttons.
            </EmptyState>
          ) : hasFilters ? (
            <EmptyState title="No inquiries match these filters">Try a different search or clear the filters.</EmptyState>
          ) : (
            <EmptyState title="The queue is clear" action={<Link className="btn btn-primary" to="/inquiries/new">Add an inquiry</Link>}>
              New customer inquiries will appear here.
            </EmptyState>
          )
        ) : (
          data && (
            <table className="queue-table" aria-describedby="queue-title">
              <thead>
                <tr>
                  <th scope="col">Priority</th>
                  <th scope="col">Customer and summary</th>
                  <th scope="col">Category</th>
                  <th scope="col">Status</th>
                  <th scope="col">Assigned</th>
                  <th scope="col">Received</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((i) => (
                  <tr key={i.id} className={i.priority === "urgent" && i.status !== "resolved" ? "row-urgent" : undefined} onClick={() => navigate(`/inquiries/${i.id}`)}>
                    <td data-label="Priority">
                      <PriorityBadge priority={i.priority} />
                    </td>
                    <td data-label="Customer">
                      <Link to={`/inquiries/${i.id}`} className="row-link" onClick={(e) => e.stopPropagation()}>
                        {i.customerName ?? "Unknown customer"}
                      </Link>
                      {i.suspicious && <span className="badge badge-flag">Security flag</span>}
                      {i.analysisStatus === "failed" && <span className="badge badge-warn">AI failed</span>}
                      <span className="row-summary">{i.summary ?? i.preview}</span>
                    </td>
                    <td data-label="Category">
                      <CategoryBadge category={i.category} />
                    </td>
                    <td data-label="Status">
                      <StatusBadge status={i.status} />
                    </td>
                    <td data-label="Assigned">{staffName(i.assignee)}</td>
                    <td data-label="Received">
                      <time dateTime={i.createdAt} title={new Date(i.createdAt).toLocaleString()}>
                        {relativeTime(i.createdAt)}
                      </time>
                      <span className="row-channel">{CHANNEL_LABEL[i.channel] ?? i.channel}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )
        )}
      </section>
    </div>
  );
}

function StatCard({ label, value, hint, tone }: { label: string; value: number | string | undefined; hint?: string; tone?: "urgent" }) {
  return (
    <div className={`stat-card${tone ? ` stat-${tone}` : ""}`}>
      <span className="stat-label">{label}</span>
      <span className="stat-value">{value ?? "–"}</span>
      {hint && <span className="stat-hint">{hint}</span>}
    </div>
  );
}

function FilterSelect({ label, value, onChange, options }: { label: string; value: string; onChange: (v: string) => void; options: [string, string][] }) {
  return (
    <label className="field">
      <span>{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">All</option>
        {options.map(([v, l]) => (
          <option key={v} value={v}>
            {l}
          </option>
        ))}
      </select>
    </label>
  );
}
