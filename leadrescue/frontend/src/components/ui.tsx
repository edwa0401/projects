import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from "react";
import type { Category, Priority, Status } from "../api/types";
import { CATEGORY_LABEL, PRIORITY_LABEL, STATUS_LABEL } from "../lib/labels";

const PRIORITY_ICON: Record<Priority, string> = { urgent: "!!", high: "!", normal: "•", low: "–" };

export function PriorityBadge({ priority }: { priority: Priority | null }) {
  if (!priority) return <span className="badge badge-muted">Not set</span>;
  return (
    <span className={`badge badge-priority-${priority}`}>
      <span aria-hidden="true" className="badge-icon">
        {PRIORITY_ICON[priority]}
      </span>
      {PRIORITY_LABEL[priority]}
    </span>
  );
}

export function CategoryBadge({ category }: { category: Category | null }) {
  if (!category) return <span className="badge badge-muted">Uncategorized</span>;
  return <span className={`badge badge-cat-${category}`}>{CATEGORY_LABEL[category]}</span>;
}

export function StatusBadge({ status }: { status: Status }) {
  return <span className={`badge badge-status badge-status-${status}`}>{STATUS_LABEL[status]}</span>;
}

export function Loading({ label = "Loading" }: { label?: string }) {
  return (
    <div className="state state-loading" role="status" aria-live="polite">
      <span className="spinner" aria-hidden="true" />
      <span>{label}…</span>
    </div>
  );
}

export function SkeletonRows({ rows = 5 }: { rows?: number }) {
  return (
    <div role="status" aria-label="Loading inquiries" className="skeleton-list">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="skeleton-row" />
      ))}
    </div>
  );
}

export function EmptyState({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="state state-empty">
      <h3>{title}</h3>
      {children && <div className="muted">{children}</div>}
      {action && <div className="state-action">{action}</div>}
    </div>
  );
}

export function ErrorState({ title = "Something went wrong", message, onRetry }: { title?: string; message: string; onRetry?: () => void }) {
  return (
    <div className="state state-error" role="alert">
      <h3>{title}</h3>
      <p>{message}</p>
      {onRetry && (
        <button type="button" className="btn btn-secondary" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  );
}

export function Alert({ tone, title, children, role }: { tone: "info" | "warning" | "danger" | "success"; title?: string; children: ReactNode; role?: string }) {
  return (
    <div className={`alert alert-${tone}`} role={role ?? (tone === "danger" ? "alert" : undefined)}>
      {title && <strong className="alert-title">{title}</strong>}
      <div>{children}</div>
    </div>
  );
}

// ---- Toasts ---------------------------------------------------------------
interface Toast {
  id: number;
  tone: "success" | "info" | "xp" | "danger";
  text: string;
}
const ToastContext = createContext<(tone: Toast["tone"], text: string) => void>(() => {});

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const nextId = useRef(1);
  const push = useCallback((tone: Toast["tone"], text: string) => {
    const id = nextId.current++;
    setToasts((t) => [...t, { id, tone, text }]);
    window.setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 6000);
  }, []);
  return (
    <ToastContext.Provider value={push}>
      {children}
      <div className="toast-region" aria-live="polite" aria-atomic="false">
        {toasts.map((t) => (
          <div key={t.id} className={`toast toast-${t.tone}`}>
            {t.text}
            <button type="button" className="toast-close" aria-label="Dismiss notification" onClick={() => setToasts((all) => all.filter((x) => x.id !== t.id))}>
              ×
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export const useToast = () => useContext(ToastContext);

export function ProgressBar({ value, max, label }: { value: number; max: number; label: string }) {
  const pct = max > 0 ? Math.min(100, Math.round((value / max) * 100)) : 0;
  return (
    <div className="progress" role="progressbar" aria-label={label} aria-valuemin={0} aria-valuemax={max} aria-valuenow={value}>
      <div className="progress-fill" style={{ width: `${pct}%` }} />
    </div>
  );
}
