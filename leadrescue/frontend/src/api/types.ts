export type Category = "quote" | "urgent_issue" | "schedule_change" | "manual_review";
export type Priority = "urgent" | "high" | "normal" | "low";
export type Status = "new" | "analysis_failed" | "awaiting_review" | "in_review" | "approved" | "resolved";
export type ExtractedField =
  | "movingDate"
  | "pickupLocation"
  | "destination"
  | "propertySize"
  | "contactName"
  | "contactPhone"
  | "contactEmail";

export interface Analysis {
  category: Category;
  priority: Priority;
  priorityReason: string;
  summary: string;
  extracted: Record<ExtractedField, string | null>;
  missingInformation: string[];
  draftReply: string;
  suspiciousInstructions: boolean;
  suspiciousReason: string | null;
  guardrails: {
    removedUngroundedFields: string[];
    injectionSignals: string[];
    overrides: string[];
    draftPolicyWarnings: string[];
  };
  meta: {
    provider: "demo" | "bedrock" | string;
    modelId: string;
    promptVersion: string;
    latencyMs: number;
    inputTokens: number | null;
    outputTokens: number | null;
    analyzedAt: string;
    confidenceCalibrated: false;
  };
}

export interface AnalysisErrorInfo {
  code: string;
  message: string;
  retryable: boolean;
  at?: string;
}

export interface Inquiry {
  id: string;
  workspace: string;
  source: string;
  createdAt: string;
  updatedAt: string;
  createdBy: string;
  version: number;
  channel: string;
  customer: { name: string | null; email: string | null; phone: string | null };
  message: string;
  status: Status;
  category: Category | null;
  priority: Priority | null;
  assignee: string | null;
  draftReply: string;
  staffEditedFields: string[];
  aiSuggestion: Analysis | null;
  analysisStatus: "not_started" | "succeeded" | "failed";
  analysisError: AnalysisErrorInfo | null;
  verification: Record<string, unknown> | null;
  approvedResponse: { text: string; approvedBy: string; approvedByName: string; approvedAt: string } | null;
  resolvedAt: string | null;
  resolvedBy: string | null;
  resolvedByName?: string;
  resolutionNote: string | null;
  resolvedWithoutResponse?: boolean;
  firstReviewedAt: string | null;
  practiceCaseId?: string;
  practiceTitle?: string;
}

export interface AuditEvent {
  id: string;
  inquiryId: string;
  at: string;
  actor: string;
  type: string;
  details: Record<string, unknown>;
}

export interface Award {
  awardKey: string;
  kind: "criterion" | "achievement";
  label: string;
  xp: number;
}

export interface InquiryDetail {
  inquiry: Inquiry;
  audit: AuditEvent[];
  analysisError?: AnalysisErrorInfo | null;
  awards?: Award[];
}

export interface InquirySummary {
  id: string;
  createdAt: string;
  updatedAt: string;
  status: Status;
  category: Category | null;
  priority: Priority | null;
  assignee: string | null;
  customerName: string | null;
  channel: string;
  summary: string | null;
  preview: string;
  analysisStatus: string;
  suspicious: boolean;
  practiceCaseId?: string;
  source: string;
  version: number;
}

export interface QueueResponse {
  items: InquirySummary[];
  counts: { awaitingReview: number; urgentOpen: number; approvedDrafts: number; total: number };
  workspace: "business" | "practice";
}

export interface StaffMember {
  id: string;
  name: string;
  role?: string;
}

export interface AppConfig {
  mode: "demo" | "live";
  aiProvider: "demo" | "bedrock";
  modelId: string;
  store: string;
  staff: StaffMember[];
  user: { id: string; username: string; name: string };
}

export interface Progress {
  xp: number;
  maxXp: number;
  level: number;
  stage: string;
  nextLevelXp: number | null;
  levelFloorXp: number;
  casesCompleted: number;
  cases: {
    caseId: string;
    title: string;
    goal: string;
    inquiryId: string | null;
    status: Status | null;
    criteria: { id: string; label: string; xp: number; earned: boolean }[];
    complete: boolean;
  }[];
  achievements: { id: string; name: string; description: string; unlockRule: string; xp: number; unlocked: boolean; unlockedAt: string | null }[];
  companions: {
    active: { id: string; name: string; focus: string; affinity: string; signature: string; level: number; stage: string };
    planned: { id: string; name: string; focus: string; signature: string; locked: boolean; status: string }[];
  };
  disclaimer: string;
}

export interface Stats {
  count: number;
  median: number | null;
  mean: number | null;
}

export interface Metrics {
  recordCount: number;
  syntheticRecordCount: number;
  analysisProviders: string[];
  byCategory: Record<string, number>;
  byStatus: Record<string, number>;
  minutesToFirstReview: Stats;
  hoursToResolution: Stats;
  aiCorrection: {
    reviewedCount: number;
    categoryCorrections: number;
    categoryCorrectionRate: number | null;
    priorityCorrections: number;
    priorityCorrectionRate: number | null;
  };
  targets: Record<string, { value: number; label: string; unit: string; direction: string }>;
  dataNote: string;
}
