import { useRef, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { apiRequest, ApiError, newIdempotencyKey } from "../api/client";
import type { InquiryDetail } from "../api/types";
import { Alert, useToast } from "../components/ui";
import { CHANNEL_LABEL } from "../lib/labels";

export function NewInquiryPage() {
  const navigate = useNavigate();
  const toast = useToast();
  const [form, setForm] = useState({ message: "", channel: "web_form", customerName: "", customerEmail: "", customerPhone: "" });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // One key per submission intent: retries after a network failure reuse it, so no duplicate record is created.
  const keyRef = useRef(newIdempotencyKey());

  function set<K extends keyof typeof form>(k: K, v: string) {
    setForm((f) => ({ ...f, [k]: v }));
    keyRef.current = newIdempotencyKey(); // content changed: this is a new request
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const local: Record<string, string> = {};
    if (form.message.trim().length < 10) local.message = "Enter the customer's message (at least 10 characters).";
    setErrors(local);
    if (Object.keys(local).length) {
      document.getElementById("message")?.focus();
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const body = Object.fromEntries(Object.entries(form).filter(([, v]) => v.trim() !== ""));
      const res = await apiRequest<InquiryDetail>("POST", "/api/inquiries", { body, idempotencyKey: keyRef.current });
      if (res.analysisError) toast("danger", `Inquiry saved, but AI analysis failed: ${res.analysisError.message}`);
      else toast("success", "Inquiry saved and analyzed. Review the suggestion before approving.");
      navigate(`/inquiries/${res.inquiry.id}`);
    } catch (err) {
      if (err instanceof ApiError && err.details && typeof err.details === "object" && "fields" in (err.details as object)) {
        const fields = (err.details as { fields: Record<string, string> | string[] }).fields;
        if (!Array.isArray(fields)) setErrors(fields);
      }
      setError(err instanceof Error ? err.message : "Could not save the inquiry.");
    } finally {
      setBusy(false);
    }
  }

  const fieldError = (k: string) =>
    errors[k] ? (
      <span className="field-error" id={`${k}-error`}>
        {errors[k]}
      </span>
    ) : null;

  return (
    <div className="narrow">
      <p>
        <Link to="/">← Back to mission control</Link>
      </p>
      <h1>New inquiry</h1>
      <p className="muted">
        Paste a customer message from email, text, chat, or a phone note. LeadRescue saves it first, then runs analysis. If analysis fails, the
        inquiry stays saved for manual handling.
      </p>
      {error && (
        <Alert tone="danger" title="Not saved">
          {error}
        </Alert>
      )}
      <form onSubmit={onSubmit} noValidate className="card form-stack">
        <label className="field">
          <span>
            Customer message <span className="req">(required)</span>
          </span>
          <textarea
            id="message"
            rows={7}
            value={form.message}
            maxLength={5000}
            onChange={(e) => set("message", e.target.value)}
            aria-invalid={Boolean(errors.message)}
            aria-describedby={errors.message ? "message-error" : "message-hint"}
          />
          <span className="hint" id="message-hint">
            {form.message.length}/5,000 characters. Treated as untrusted input.
          </span>
          {fieldError("message")}
        </label>
        <label className="field">
          <span>Channel</span>
          <select value={form.channel} onChange={(e) => set("channel", e.target.value)}>
            {Object.entries(CHANNEL_LABEL).map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
        </label>
        <div className="grid-3">
          <label className="field">
            <span>Customer name</span>
            <input value={form.customerName} maxLength={100} onChange={(e) => set("customerName", e.target.value)} autoComplete="off" aria-invalid={Boolean(errors.customerName)} />
            {fieldError("customerName")}
          </label>
          <label className="field">
            <span>Email</span>
            <input type="email" value={form.customerEmail} maxLength={254} onChange={(e) => set("customerEmail", e.target.value)} autoComplete="off" aria-invalid={Boolean(errors.customerEmail)} />
            {fieldError("customerEmail")}
          </label>
          <label className="field">
            <span>Phone</span>
            <input type="tel" value={form.customerPhone} maxLength={32} onChange={(e) => set("customerPhone", e.target.value)} autoComplete="off" aria-invalid={Boolean(errors.customerPhone)} />
            {fieldError("customerPhone")}
          </label>
        </div>
        <div className="form-actions">
          <button className="btn btn-primary" type="submit" disabled={busy}>
            {busy ? "Saving and analyzing…" : "Save and analyze"}
          </button>
          <Link to="/" className="btn btn-ghost">
            Cancel
          </Link>
        </div>
      </form>
    </div>
  );
}
