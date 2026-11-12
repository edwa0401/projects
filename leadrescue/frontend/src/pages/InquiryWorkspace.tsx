import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { apiRequest, ApiError, newIdempotencyKey } from "../api/client";
import type { AuditEvent, Award, Category, ExtractedField, Inquiry, InquiryDetail, Priority } from "../api/types";
import { useAppConfig } from "../components/AppShell";
import { Alert, CategoryBadge, ErrorState, Loading, PriorityBadge, StatusBadge, useToast } from "../components/ui";
import { formatDateTime, relativeTime } from "../lib/format";
import {
  CATEGORIES,
  CATEGORY_LABEL,
  CHANNEL_LABEL,
  draftPolicyWarnings,
  FIELD_LABEL,
  MISSING_LABEL,
  PRIORITIES,
  PRIORITY_LABEL,
  STATUS_LABEL,
  VERIFICATION_ITEMS,
} from "../lib/labels";

const FIELDS: ExtractedField[] = ["movingDate", "pickupLocation", "destination", "propertySize", "contactName", "contactPhone", "contactEmail"];

interface Draft {
  category: Category | "";
  priority: Priority | "";
  assignee: string;
  draftReply: string;
}

function draftFrom(i: Inquiry): Draft {
  return { category: i.category ?? "", priority: i.priority ?? "", assignee: i.assignee ?? "", draftReply: i.draftReply ?? "" };
}

const draftStorageKey = (id: string) => `leadrescue.unsaved.${id}`;

export function InquiryWorkspacePage() {
  const { id = "" } = useParams();
  const config = useAppConfig();
  const toast = useToast();
  const [detail, setDetail] = useState<InquiryDetail | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [checks, setChecks] = useState<Record<string, boolean>>({});
  const [busy, setBusy] = useState<null | "save" | "approve" | "resolve" | "analyze">(null);
  const [actionError, setActionError] = useState<{ message: string; code: string; details?: unknown } | null>(null);
  const [note, setNote] = useState("");
  const [copied, setCopied] = useState(false);
  const keys = useRef<Record<string, string>>({});

  const keyFor = (action: string) => (keys.current[action] ??= newIdempotencyKey());
  const resetKey = (action: string) => delete keys.current[action];

  const load = useCallback(async () => {
    setLoadError(null);
    try {
      const res = await apiRequest<InquiryDetail>("GET", `/api/inquiries/${encodeURIComponent(id)}`);
      setDetail(res);
      // Restore unsaved edits kept across a session expiry, if they belong to this version.
      let restored: Draft | null = null;
      try {
        const raw = sessionStorage.getItem(draftStorageKey(id));
        if (raw) {
          const parsed = JSON.parse(raw) as { version: number; draft: Draft };
          if (parsed.version === res.inquiry.version) restored = parsed.draft;
        }
      } catch {
        /* storage unavailable */
      }
      setDraft(restored ?? draftFrom(res.inquiry));
      setChecks({});
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) return;
      setLoadError(e instanceof Error ? e.message : "Could not load this inquiry.");
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  const inquiry = detail?.inquiry;
  const ai = inquiry?.aiSuggestion ?? null;
  const dirty = useMemo(() => {
    if (!inquiry || !draft) return false;
    const base = draftFrom(inquiry);
    return (Object.keys(base) as (keyof Draft)[]).some((k) => base[k] !== draft[k]);
  }, [inquiry, draft]);

  // Keep unsaved edits in session storage so a session expiry does not lose work.
  useEffect(() => {
    if (!inquiry || !draft) return;
    try {
      if (dirty) sessionStorage.setItem(draftStorageKey(inquiry.id), JSON.stringify({ version: inquiry.version, draft }));
      else sessionStorage.removeItem(draftStorageKey(inquiry.id));
    } catch {
      /* ignore */
    }
  }, [dirty, draft, inquiry]);

  useEffect(() => {
    const handler = (e: BeforeUnloadEvent) => {
      if (dirty) e.preventDefault();
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [dirty]);

  if (loadError) {
    return (
      <div className="narrow">
        <p>
          <Link to="/">← Back to mission control</Link>
        </p>
        <ErrorState title="Inquiry unavailable" message={loadError} onRetry={load} />
      </div>
    );
  }
  if (!detail || !inquiry || !draft) return <Loading label="Loading inquiry" />;

  const closed = inquiry.status === "resolved";
  const suspicious = Boolean(ai?.suspiciousInstructions);
  const requiredChecks = VERIFICATION_ITEMS.filter((v) => !v.onlyIfSuspicious || suspicious);
  const allChecked = requiredChecks.every((v) => checks[v.key]);
  const warnings = draftPolicyWarnings(draft.draftReply);
  const staffName = (sid: string | null | undefined) => config?.staff.find((s) => s.id === sid)?.name ?? sid ?? "Unassigned";
  const canApprove =
    !closed && inquiry.status !== "approved" && allChecked && draft.draftReply.trim().length >= 20 && draft.category && draft.priority && warnings.length === 0;

  function applyResult(res: InquiryDetail, successText: string) {
    setDetail(res);
    setDraft(draftFrom(res.inquiry));
    setChecks({});
    setActionError(null);
    toast("success", successText);
    announceAwards(res.awards);
  }

  function announceAwards(awards?: Award[]) {
    awards?.forEach((a) => toast("xp", a.kind === "achievement" ? `Achievement unlocked: ${a.label} (+${a.xp} XP)` : `+${a.xp} XP: ${a.label}`));
  }

  function handleError(e: unknown, action: string) {
    if (e instanceof ApiError) {
      if (e.status === 401) return;
      if (e.status !== 0) resetKey(action); // server rejected: next attempt is a new request
      setActionError({ message: e.message, code: e.code, details: e.details });
    } else {
      setActionError({ message: "Unexpected error. Try again.", code: "unknown" });
    }
  }

  async function saveChanges(current: Inquiry): Promise<Inquiry> {
    const base = draftFrom(current);
    const changes: Record<string, unknown> = {};
    if (draft!.category !== base.category && draft!.category) changes.category = draft!.category;
    if (draft!.priority !== base.priority && draft!.priority) changes.priority = draft!.priority;
    if (draft!.assignee !== base.assignee) changes.assignee = draft!.assignee || null;
    if (draft!.draftReply !== base.draftReply) changes.draftReply = draft!.draftReply;
    if (!Object.keys(changes).length) return current;
    const res = await apiRequest<InquiryDetail>("PATCH", `/api/inquiries/${current.id}`, { body: { expectedVersion: current.version, ...changes } });
    setDetail(res);
    return res.inquiry;
  }

  async function onSave() {
    setBusy("save");
    try {
      const updated = await saveChanges(inquiry!);
      const res = await apiRequest<InquiryDetail>("GET", `/api/inquiries/${updated.id}`);
      applyResult(res, "Draft saved.");
    } catch (e) {
      handleError(e, "save");
    } finally {
      setBusy(null);
    }
  }

  async function onApprove() {
    setBusy("approve");
    try {
      const current = await saveChanges(inquiry!);
      const res = await apiRequest<InquiryDetail>("POST", `/api/inquiries/${current.id}/approve`, {
        body: { expectedVersion: current.version, verification: Object.fromEntries(requiredChecks.map((c) => [c.key, Boolean(checks[c.key])])) },
        idempotencyKey: keyFor("approve"),
      });
      resetKey("approve");
      applyResult(res, "Response approved. Copy it into your email or messaging tool to send.");
    } catch (e) {
      handleError(e, "approve");
      load();
    } finally {
      setBusy(null);
    }
  }

  async function onResolve() {
    setBusy("resolve");
    try {
      const res = await apiRequest<InquiryDetail>("POST", `/api/inquiries/${inquiry!.id}/resolve`, {
        body: { expectedVersion: inquiry!.version, resolutionNote: note.trim() || undefined },
        idempotencyKey: keyFor("resolve"),
      });
      resetKey("resolve");
      setNote("");
      applyResult(res, "Inquiry resolved.");
    } catch (e) {
      handleError(e, "resolve");
    } finally {
      setBusy(null);
    }
  }

  async function onAnalyze() {
    setBusy("analyze");
    try {
      const res = await apiRequest<InquiryDetail>("POST", `/api/inquiries/${inquiry!.id}/analyze`, {
        body: { expectedVersion: inquiry!.version },
        idempotencyKey: keyFor("analyze"),
      });
      resetKey("analyze");
      setDetail(res);
      setDraft(draftFrom(res.inquiry));
      if (res.analysisError) toast("danger", `Analysis failed again: ${res.analysisError.message}`);
      else toast("success", "Analysis complete. Review the suggestion.");
    } catch (e) {
      handleError(e, "analyze");
    } finally {
      setBusy(null);
    }
  }

  async function copyApproved() {
    const text = inquiry!.approvedResponse?.text ?? "";
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2500);
    } catch {
      const el = document.getElementById("approved-text") as HTMLTextAreaElement | null;
      el?.focus();
      el?.select();
      toast("info", "Press Ctrl+C (or Cmd+C) to copy the selected response.");
    }
  }

  const corrected = (field: "category" | "priority") => ai && draft[field] && draft[field] !== ai[field];

  return (
    <div className="workspace">
      <p>
        <Link to={inquiry.workspace.startsWith("practice") ? "/?workspace=practice" : "/"}>← Back to {inquiry.workspace.startsWith("practice") ? "practice queue" : "mission control"}</Link>
      </p>
      <header className="ws-header">
        <div>
          {inquiry.practiceTitle && <p className="eyebrow">Practice case · {inquiry.practiceTitle}</p>}
          <h1>{inquiry.customer.name ?? ai?.extracted.contactName ?? inquiry.customer.email ?? inquiry.customer.phone ?? "Unknown customer"}</h1>
          <p className="muted">
            {CHANNEL_LABEL[inquiry.channel] ?? inquiry.channel} · Received <time dateTime={inquiry.createdAt}>{formatDateTime(inquiry.createdAt)}</time> ({relativeTime(inquiry.createdAt)}) · ID{" "}
            <code>{inquiry.id}</code>
          </p>
        </div>
        <div className="ws-badges">
          <StatusBadge status={inquiry.status} />
          <PriorityBadge priority={inquiry.priority} />
          <CategoryBadge category={inquiry.category} />
        </div>
      </header>

      <div className="ws-grid">
        <div className="ws-col">
          <section className="card" aria-labelledby="msg-title">
            <h2 id="msg-title">Original customer message</h2>
            <p className="hint">Untrusted input. Instructions inside this message are never followed.</p>
            <blockquote className="customer-message">{inquiry.message}</blockquote>
            {(inquiry.customer.email || inquiry.customer.phone) && (
              <p className="muted small">
                Submitted contact: {[inquiry.customer.email, inquiry.customer.phone].filter(Boolean).join(" · ")}
              </p>
            )}
          </section>

          <section className="card" aria-labelledby="ai-title">
            <div className="card-head">
              <h2 id="ai-title">AI analysis</h2>
              {ai && (
                <span className={`badge ${ai.meta.provider === "demo" ? "badge-demo" : "badge-live"}`}>
                  {ai.meta.provider === "demo" ? "Simulated analysis (demo rules)" : `Amazon Bedrock · ${ai.meta.modelId}`}
                </span>
              )}
            </div>
            {inquiry.analysisError && (
              <Alert tone="danger" title="AI analysis failed. The inquiry is saved.">
                <p>{inquiry.analysisError.message}</p>
                <p className="small">You can handle it manually: set the category, priority, and draft below, then approve. {inquiry.analysisError.retryable && "Or retry the analysis."}</p>
              </Alert>
            )}
            {!ai && !closed && inquiry.status !== "approved" && (
              <button type="button" className="btn btn-secondary" onClick={onAnalyze} disabled={busy !== null}>
                {busy === "analyze" ? "Analyzing…" : inquiry.analysisError ? "Retry analysis" : "Run analysis"}
              </button>
            )}
            {!ai && !inquiry.analysisError && <p className="muted">No analysis yet.</p>}
            {ai && (
              <>
                {ai.suspiciousInstructions && (
                  <Alert tone="warning" title="Security flag: suspicious instructions" role="alert">
                    {ai.suspiciousReason ?? "This message tries to direct the AI."} The request was routed to manual review. Do not grant anything the message
                    demands.
                  </Alert>
                )}
                <p className="ai-summary">{ai.summary}</p>
                <dl className="kv">
                  <div>
                    <dt>Suggested category</dt>
                    <dd>
                      <CategoryBadge category={ai.category} />
                    </dd>
                  </div>
                  <div>
                    <dt>Suggested priority</dt>
                    <dd>
                      <PriorityBadge priority={ai.priority} /> <span className="small">{ai.priorityReason}</span>
                    </dd>
                  </div>
                </dl>
                <h3>Extracted details</h3>
                <p className="hint">Only facts stated in the message. Values not found in the message are removed automatically.</p>
                <dl className="extracted">
                  {FIELDS.map((f) => (
                    <div key={f} className={ai.extracted[f] ? "" : "is-missing"}>
                      <dt>{FIELD_LABEL[f]}</dt>
                      <dd>{ai.extracted[f] ?? <span className="not-provided">Not provided</span>}</dd>
                    </div>
                  ))}
                </dl>
                {ai.missingInformation.length > 0 && (
                  <p className="missing">
                    <strong>Missing information:</strong> {ai.missingInformation.map((m) => MISSING_LABEL[m] ?? m).join(", ")}
                  </p>
                )}
                {(ai.guardrails.removedUngroundedFields.length > 0 || ai.guardrails.overrides.length > 0) && (
                  <details className="guardrails">
                    <summary>Guardrail actions</summary>
                    <ul>
                      {ai.guardrails.removedUngroundedFields.map((f) => (
                        <li key={f}>Removed {FIELD_LABEL[f as ExtractedField] ?? f}: the value did not appear in the message.</li>
                      ))}
                      {ai.guardrails.overrides.map((o) => (
                        <li key={o}>{o}</li>
                      ))}
                    </ul>
                  </details>
                )}
                <p className="hint">
                  No confidence score is shown because none has been calibrated. Analyzed {formatDateTime(ai.meta.analyzedAt)} in {ai.meta.latencyMs} ms
                  {ai.meta.inputTokens != null && ` · ${ai.meta.inputTokens} input / ${ai.meta.outputTokens} output tokens`}.
                </p>
              </>
            )}
          </section>
        </div>

        <div className="ws-col">
          <section className="card review" aria-labelledby="review-title">
            <h2 id="review-title">Staff review</h2>
            {actionError && (
              <Alert tone="danger" title={actionError.code === "version_conflict" ? "Someone else updated this inquiry" : "Action not completed"}>
                <p>{actionError.message}</p>
                {Array.isArray((actionError.details as { violations?: string[] } | undefined)?.violations) && (
                  <ul>
                    {(actionError.details as { violations: string[] }).violations.map((v) => (
                      <li key={v}>The draft {v}.</li>
                    ))}
                  </ul>
                )}
                {actionError.code === "version_conflict" && (
                  <button type="button" className="btn btn-secondary btn-sm" onClick={() => { setActionError(null); load(); }}>
                    Reload latest version
                  </button>
                )}
              </Alert>
            )}
            <fieldset disabled={closed || busy !== null} className="form-stack">
              <legend className="sr-only">Classification and draft</legend>
              <div className="grid-2">
                <label className="field">
                  <span>Category</span>
                  <select value={draft.category} onChange={(e) => setDraft({ ...draft, category: e.target.value as Category })}>
                    <option value="" disabled>
                      Choose a category
                    </option>
                    {CATEGORIES.map((c) => (
                      <option key={c} value={c}>
                        {CATEGORY_LABEL[c]}
                      </option>
                    ))}
                  </select>
                  {corrected("category") && <span className="hint corrected">Corrected from AI suggestion ({CATEGORY_LABEL[ai!.category]})</span>}
                </label>
                <label className="field">
                  <span>Priority</span>
                  <select value={draft.priority} onChange={(e) => setDraft({ ...draft, priority: e.target.value as Priority })}>
                    <option value="" disabled>
                      Choose a priority
                    </option>
                    {PRIORITIES.map((p) => (
                      <option key={p} value={p}>
                        {PRIORITY_LABEL[p]}
                      </option>
                    ))}
                  </select>
                  {corrected("priority") && <span className="hint corrected">Corrected from AI suggestion ({PRIORITY_LABEL[ai!.priority]})</span>}
                </label>
              </div>
              <label className="field">
                <span>Assigned to</span>
                <select value={draft.assignee} onChange={(e) => setDraft({ ...draft, assignee: e.target.value })}>
                  <option value="">Unassigned</option>
                  {config?.staff.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                      {s.role ? ` (${s.role})` : ""}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span>Response draft</span>
                <textarea
                  rows={9}
                  value={draft.draftReply}
                  maxLength={4000}
                  onChange={(e) => setDraft({ ...draft, draftReply: e.target.value })}
                  aria-describedby="draft-hint draft-policy"
                />
                <span className="hint" id="draft-hint">
                  {draft.draftReply.length}/4,000 · Do not confirm prices, availability, bookings, or free services.
                </span>
                <span id="draft-policy" aria-live="polite">
                  {warnings.length > 0 && (
                    <span className="field-error">Approval blocked: the draft {warnings.join(", ")}.</span>
                  )}
                </span>
              </label>
              <div className="form-actions">
                <button type="button" className="btn btn-secondary" onClick={onSave} disabled={!dirty || busy !== null}>
                  {busy === "save" ? "Saving…" : "Save draft"}
                </button>
                {dirty && <span className="hint">Unsaved changes</span>}
              </div>
            </fieldset>

            {!closed && inquiry.status !== "approved" && (
              <fieldset className="verify" disabled={busy !== null}>
                <legend>Human verification (required before approval)</legend>
                {requiredChecks.map((c) => (
                  <label key={c.key} className="check-row">
                    <input type="checkbox" checked={Boolean(checks[c.key])} onChange={(e) => setChecks({ ...checks, [c.key]: e.target.checked })} />
                    <span>{c.label}</span>
                  </label>
                ))}
                <button type="button" className="btn btn-primary" onClick={onApprove} disabled={!canApprove || busy !== null}>
                  {busy === "approve" ? "Approving…" : dirty ? "Save and approve response" : "Approve response"}
                </button>
                {!canApprove && (
                  <p className="hint" id="approve-hint">
                    {!allChecked
                      ? "Complete every verification check to enable approval."
                      : !draft.category || !draft.priority
                        ? "Choose a category and priority."
                        : draft.draftReply.trim().length < 20
                          ? "Write a response draft of at least 20 characters."
                          : warnings.length
                            ? "Edit the draft to remove commitments."
                            : ""}
                  </p>
                )}
              </fieldset>
            )}

            {inquiry.approvedResponse && (
              <div className="approved">
                <h3>Approved response</h3>
                <p className="small muted">
                  Approved by {inquiry.approvedResponse.approvedByName} on {formatDateTime(inquiry.approvedResponse.approvedAt)}. LeadRescue does not send
                  messages; copy this into your email or messaging tool.
                </p>
                <textarea id="approved-text" readOnly rows={6} value={inquiry.approvedResponse.text} aria-label="Approved response text" />
                <button type="button" className="btn btn-secondary" onClick={copyApproved}>
                  {copied ? "Copied" : "Copy approved response"}
                </button>
                <span aria-live="polite" className="sr-only">
                  {copied ? "Approved response copied to clipboard" : ""}
                </span>
              </div>
            )}

            {!closed && (
              <div className="resolve">
                <h3>Resolve</h3>
                {inquiry.status === "approved" ? (
                  <p className="small muted">Mark resolved after you have sent the approved response or finished the follow-up.</p>
                ) : (
                  <label className="field">
                    <span>Resolution note (required when resolving without an approved response)</span>
                    <textarea rows={2} value={note} maxLength={1000} onChange={(e) => setNote(e.target.value)} />
                  </label>
                )}
                <button
                  type="button"
                  className="btn btn-ghost"
                  onClick={onResolve}
                  disabled={busy !== null || (inquiry.status !== "approved" && note.trim().length < 5)}
                >
                  {busy === "resolve" ? "Resolving…" : inquiry.status === "approved" ? "Mark resolved" : "Resolve without response"}
                </button>
              </div>
            )}
            {closed && (
              <Alert tone="success" title="Resolved">
                Resolved {formatDateTime(inquiry.resolvedAt)} by {inquiry.resolvedByName ?? "staff"}.
                {inquiry.resolutionNote && <> Note: {inquiry.resolutionNote}</>}
              </Alert>
            )}
          </section>

          <section className="card" aria-labelledby="audit-title">
            <h2 id="audit-title">Audit history</h2>
            <ol className="audit">
              {[...detail.audit].reverse().map((e) => (
                <li key={e.id}>
                  <time dateTime={e.at}>{formatDateTime(e.at)}</time>
                  <span className="audit-actor">{e.actor}</span>
                  <span>{describeEvent(e, staffName)}</span>
                </li>
              ))}
            </ol>
          </section>
        </div>
      </div>
    </div>
  );
}

function describeEvent(e: AuditEvent, staffName: (id: string | null) => string): string {
  const d = e.details as Record<string, unknown>;
  const val = (field: unknown, v: unknown) => {
    if (v === null || v === undefined) return field === "assignee" ? "Unassigned" : "none";
    if (field === "category") return CATEGORY_LABEL[v as Category] ?? String(v);
    if (field === "priority") return PRIORITY_LABEL[v as Priority] ?? String(v);
    if (field === "assignee") return staffName(String(v));
    return String(v);
  };
  switch (e.type) {
    case "created":
      return `Inquiry received (${CHANNEL_LABEL[String(d.channel)] ?? d.channel}).`;
    case "analysis_succeeded":
      return `Analysis completed by ${d.provider === "demo" ? "demo rules" : `Bedrock (${d.modelId})`}: suggested ${val("category", d.suggestedCategory)}, ${val("priority", d.suggestedPriority)} priority${d.suspicious ? ", security flag raised" : ""}.`;
    case "analysis_failed":
      return `Analysis failed (${d.code}). Inquiry kept for manual handling.`;
    case "field_changed":
      return `Changed ${String(d.field)} from ${val(d.field, d.fromValue)} to ${val(d.field, d.toValue)}.`;
    case "draft_saved":
      return `Saved response draft (${d.characters} characters).`;
    case "approved":
      return "Approved the response after completing human verification. Not sent automatically.";
    case "approval_revoked":
      return "Approval revoked because the inquiry was edited.";
    case "resolved":
      return d.withoutApprovedResponse ? "Resolved without an approved response (note recorded)." : "Marked resolved.";
    case "status_changed":
      return `Status: ${STATUS_LABEL[d.fromStatus as keyof typeof STATUS_LABEL] ?? d.fromStatus} → ${STATUS_LABEL[d.toStatus as keyof typeof STATUS_LABEL] ?? d.toStatus}.`;
    default:
      return e.type;
  }
}
