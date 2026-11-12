import type { Category, ExtractedField, Priority, Status } from "../api/types";

export const CATEGORY_LABEL: Record<Category, string> = {
  quote: "Quote",
  urgent_issue: "Urgent issue",
  schedule_change: "Schedule change",
  manual_review: "Manual review",
};

export const PRIORITY_LABEL: Record<Priority, string> = { urgent: "Urgent", high: "High", normal: "Normal", low: "Low" };

export const STATUS_LABEL: Record<Status, string> = {
  new: "New",
  analysis_failed: "Needs manual handling",
  awaiting_review: "Awaiting review",
  in_review: "In review",
  approved: "Draft approved",
  resolved: "Resolved",
};

export const FIELD_LABEL: Record<ExtractedField, string> = {
  movingDate: "Moving date",
  pickupLocation: "Pickup location",
  destination: "Destination",
  propertySize: "Property size",
  contactName: "Contact name",
  contactPhone: "Contact phone",
  contactEmail: "Contact email",
};

export const MISSING_LABEL: Record<string, string> = {
  movingDate: "Moving date",
  pickupLocation: "Pickup location",
  destination: "Destination",
  propertySize: "Property size",
  contactMethod: "Phone or email",
};

export const CHANNEL_LABEL: Record<string, string> = {
  web_form: "Web form",
  email: "Email",
  phone_note: "Phone note",
  sms: "Text message",
  chat: "Chat",
};

export const CATEGORIES = Object.keys(CATEGORY_LABEL) as Category[];
export const PRIORITIES = Object.keys(PRIORITY_LABEL) as Priority[];
export const STATUSES = Object.keys(STATUS_LABEL) as Status[];

export const VERIFICATION_ITEMS: { key: string; label: string; onlyIfSuspicious?: boolean }[] = [
  { key: "factsChecked", label: "I compared the extracted details with the original message." },
  { key: "noCommitments", label: "The reply does not confirm a price, availability, booking, discount, or free service." },
  { key: "categoryPriorityReviewed", label: "I reviewed the category, priority, and assignment." },
  { key: "suspiciousReviewed", label: "I reviewed the security flag and the reply does not follow the customer's embedded instructions.", onlyIfSuspicious: true },
];

/** Client-side mirror of the server draft policy, for instant feedback. The server re-checks on approval. */
const POLICY: [RegExp, string][] = [
  [/\$\s?\d/i, "quotes a dollar amount"],
  [/\b\d[\d,]*(\.\d+)?\s?(dollars|usd)\b/i, "quotes a price"],
  [/\b(is|are|has been|have been)\s+(now\s+)?(confirmed|booked|reserved|guaranteed|approved)\b/i, "confirms a booking or approval"],
  [/\bwe(?:'ve| have| will| 've)?\s+(confirmed|booked|reserved|guaranteed|approved)\b/i, "confirms a booking or approval"],
  [/\b(we|i)\s+guarantee\b|\bguaranteed\b/i, "makes a guarantee"],
  [/\bfree (move|of charge)\b|\bno charge\b|\bat no cost\b/i, "offers a free move or waived charge"],
  [/\b(crew|movers|truck) (will|is going to) (arrive|be there) (at|by|in)\b/i, "promises arrival time or availability"],
  [/\bwe (have|'ve got) (availability|openings?|a crew available)\b/i, "confirms availability"],
];

export function draftPolicyWarnings(text: string): string[] {
  const out: string[] = [];
  for (const [re, label] of POLICY) if (re.test(text) && !out.includes(label)) out.push(label);
  return out;
}
