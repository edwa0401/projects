import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Inquiry, InquiryDetail } from "../../src/api/types";
import { AuthProvider } from "../../src/auth/AuthContext";
import { saveSession, clearSession } from "../../src/auth/session";
import { ToastProvider } from "../../src/components/ui";
import { InquiryWorkspacePage } from "../../src/pages/InquiryWorkspace";

function inquiry(over: Partial<Inquiry> = {}): Inquiry {
  return {
    id: "inq_1",
    workspace: "business",
    source: "staff_entry",
    createdAt: "2026-11-12T10:00:00Z",
    updatedAt: "2026-11-12T10:00:00Z",
    createdBy: "u",
    version: 3,
    channel: "web_form",
    customer: { name: "Dana", email: null, phone: null },
    message: "Quote for a two-bedroom apartment from Sherman to Denison next Saturday",
    status: "awaiting_review",
    category: "quote",
    priority: "normal",
    assignee: null,
    draftReply: "Hello Dana, a team member will follow up with an estimate soon.",
    staffEditedFields: [],
    analysisStatus: "succeeded",
    analysisError: null,
    verification: null,
    approvedResponse: null,
    resolvedAt: null,
    resolvedBy: null,
    resolutionNote: null,
    firstReviewedAt: null,
    aiSuggestion: {
      category: "quote",
      priority: "normal",
      priorityReason: "New lead",
      summary: "Quote request",
      extracted: { movingDate: "next Saturday", pickupLocation: "Sherman", destination: "Denison", propertySize: null, contactName: "Dana", contactPhone: null, contactEmail: null },
      missingInformation: ["propertySize", "contactMethod"],
      draftReply: "Hello",
      suspiciousInstructions: false,
      suspiciousReason: null,
      guardrails: { removedUngroundedFields: [], injectionSignals: [], overrides: [], draftPolicyWarnings: [] },
      meta: { provider: "demo", modelId: "demo-rules-v1", promptVersion: "x", latencyMs: 1, inputTokens: null, outputTokens: null, analyzedAt: "2026-11-12T10:00:00Z", confidenceCalibrated: false },
    },
    ...over,
  };
}

function setup(detail: InquiryDetail, extraResponses: Record<string, unknown> = {}) {
  const calls: { url: string; init: RequestInit }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init: RequestInit) => {
      calls.push({ url, init });
      const key = `${init.method} ${url}`;
      const body = key in extraResponses ? extraResponses[key] : detail;
      return new Response(JSON.stringify(body), { status: 200 });
    }),
  );
  render(
    <MemoryRouter initialEntries={["/inquiries/inq_1"]}>
      <AuthProvider>
        <ToastProvider>
          <Routes>
            <Route path="/inquiries/:id" element={<InquiryWorkspacePage />} />
          </Routes>
        </ToastProvider>
      </AuthProvider>
    </MemoryRouter>,
  );
  return calls;
}

beforeEach(() => {
  saveSession({ token: "tok", expiresAt: Math.floor(Date.now() / 1000) + 3600, user: { id: "u", name: "Maya" }, mode: "demo" });
  vi.stubGlobal("scrollTo", () => {});
});
afterEach(() => {
  vi.unstubAllGlobals();
  clearSession();
  sessionStorage.clear();
});

describe("Inquiry workspace", () => {
  it("marks missing extracted details as Not provided", async () => {
    setup({ inquiry: inquiry(), audit: [] });
    expect(await screen.findByText("Original customer message")).toBeInTheDocument();
    expect(screen.getAllByText("Not provided")).toHaveLength(3);
    expect(screen.getByText("Sherman")).toBeInTheDocument();
    expect(screen.getByText(/No confidence score is shown/)).toBeInTheDocument();
  });

  it("requires every verification check before approval", async () => {
    const user = userEvent.setup();
    const approved = { inquiry: inquiry({ status: "approved", version: 4, approvedResponse: { text: "Hello Dana, a team member will follow up with an estimate soon.", approvedBy: "u", approvedByName: "Maya", approvedAt: "2026-11-12T10:05:00Z" } }), audit: [], awards: [] };
    const calls = setup({ inquiry: inquiry(), audit: [] }, { "POST /api/inquiries/inq_1/approve": approved });
    const approve = await screen.findByRole("button", { name: "Approve response" });
    expect(approve).toBeDisabled();
    const boxes = screen.getAllByRole("checkbox");
    expect(boxes).toHaveLength(3);
    await user.click(boxes[0]);
    await user.click(boxes[1]);
    expect(approve).toBeDisabled();
    await user.click(boxes[2]);
    expect(approve).toBeEnabled();
    await user.click(approve);
    await waitFor(() => expect(screen.getByRole("button", { name: /Copy approved response/ })).toBeInTheDocument());
    const req = calls.find((c) => c.url.endsWith("/approve"))!;
    expect((req.init.headers as Record<string, string>)["Idempotency-Key"]).toBeTruthy();
    expect(JSON.parse(String(req.init.body)).verification).toEqual({ factsChecked: true, noCommitments: true, categoryPriorityReviewed: true });
  });

  it("adds a security check and warning for suspicious inquiries", async () => {
    const base = inquiry();
    setup({ inquiry: { ...base, category: "manual_review", aiSuggestion: { ...base.aiSuggestion!, suspiciousInstructions: true, suspiciousReason: "asks to ignore instructions" } }, audit: [] });
    expect(await screen.findByText(/Security flag/)).toBeInTheDocument();
    expect(screen.getAllByRole("checkbox")).toHaveLength(4);
  });

  it("blocks approval when the draft makes a commitment", async () => {
    const user = userEvent.setup();
    setup({ inquiry: inquiry(), audit: [] });
    const textarea = await screen.findByLabelText(/^Response draft/);
    await user.clear(textarea);
    await user.type(textarea, "Your move is confirmed and the total is $500.");
    expect(screen.getByText(/Approval blocked/)).toBeInTheDocument();
    for (const box of screen.getAllByRole("checkbox")) await user.click(box);
    expect(screen.getByRole("button", { name: /approve response/i })).toBeDisabled();
  });

  it("shows a useful error and manual path when analysis failed", async () => {
    setup({ inquiry: inquiry({ status: "analysis_failed", aiSuggestion: null, analysisStatus: "failed", category: null, priority: null, draftReply: "", analysisError: { code: "model_throttled", message: "The AI service is busy.", retryable: true } }), audit: [] });
    expect(await screen.findByText(/AI analysis failed. The inquiry is saved./)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry analysis" })).toBeInTheDocument();
    expect(screen.getByText(/handle it manually/)).toBeInTheDocument();
  });
});
