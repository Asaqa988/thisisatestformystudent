// The shapes the NEXUS backend returns. They are NEXUS shapes, not Chatwoot
// shapes: the backend's adapter translates before anything reaches this file.
// Keep this in step with docs/api-contracts.md.

export type ConversationStatus = "open" | "pending" | "snoozed" | "resolved";
export type MessageDirection = "inbound" | "outbound" | "system";
export type AuthorType = "contact" | "agent" | "bot" | "system";

export interface Contact {
  name: string;
  email: string | null;
  avatar_url: string | null;
}

export interface LastMessage {
  preview: string;
  direction: MessageDirection;
  at: string;
}

export interface Conversation {
  id: string;
  source: string;
  external_id: string;
  channel: string;
  inbox_name: string | null;
  status: ConversationStatus;
  contact: Contact;
  last_message: LastMessage | null;
  unread_count: number;
  updated_at: string;
  ai_enabled: boolean;
  ai_paused_reason: string | null;
  customer_id: string | null;
}

export interface Message {
  id: string;
  direction: MessageDirection;
  author: { type: AuthorType; name: string };
  content: string;
  private: boolean;
  sent_at: string;
}

export interface IntegrationStatus {
  key: string;
  name: string;
  configured: boolean;
  ok: boolean;
  detail: string;
  webhook_verification?: "hmac" | "disabled";
}

export interface DashboardSummary {
  conversations: {
    total: number;
    open: number;
    awaiting_reply: number;
    resolved: number;
  };
  events: {
    received_24h: number;
    duplicates_ignored: number;
    last_received_at: string | null;
  };
  integrations: IntegrationStatus[];
}

export interface WebhookEvent {
  id: string;
  source: string;
  event_type: string;
  summary: string;
  external_conversation_id: string | null;
  duplicate_count: number;
  received_at: string;
}

export interface ItemList<T> {
  items: T[];
}

export interface KnowledgeArticle {
  id: string;
  title: string;
  content: string;
  updated_at: string;
}

export interface KnowledgeList {
  items: KnowledgeArticle[];
  total_chars: number;
}

export interface AISettings {
  enabled: boolean;
  business_name: string;
  instructions: string;
  configured: boolean;
  model: string;
}

export type AIReplyStatus = "pending" | "sending" | "sent" | "handoff" | "skipped" | "error";

export interface AIReply {
  id: string;
  conversation_id: string;
  contact_name: string;
  status: AIReplyStatus;
  reply_text: string | null;
  reason: string | null;
  input_tokens: number;
  output_tokens: number;
  created_at: string;
}

export interface CustomerSummary {
  id: string;
  source: string;
  external_id: string;
  name: string;
  email: string | null;
  phone: string | null;
  avatar_url: string | null;
  city: string | null;
  country: string | null;
  company: string | null;
  channels: string[];
  conversation_count: number;
  open_conversations: number;
  last_message_at: string | null;
  last_message_preview: string | null;
  first_seen_at: string | null;
}

export interface CustomerList {
  items: CustomerSummary[];
  total: number;
}

export interface CustomerDetail extends CustomerSummary {
  identifier: string | null;
  description: string | null;
  social_profiles: Record<string, string>;
  custom_attributes: Record<string, unknown>;
  blocked: boolean;
  updated_at: string;
  conversations: Conversation[];
}

export type AutomationStatus = "building" | "ready" | "unsupported" | "failed";
export type RunStatus = "running" | "awaiting_approval" | "succeeded" | "failed" | "rejected";

export interface AutomationStep {
  id: string;
  tool: string;
  kind: "read" | "action" | "unknown";
  description: string;
  params: Record<string, unknown>;
}

export interface RunOutput {
  step_id: string;
  tool: string;
  kind: "customers" | "conversations" | "file" | "summary" | "action" | "action_result";
  count: number;
  summary: string;
  file_id?: string;
  filename?: string;
  size?: number;
  table?: { group: string; count: number }[];
}

export interface PendingAction {
  step_id: string;
  tool: string;
  label: string;
  text?: string;
  status?: string;
  enabled?: boolean;
  target_count: number;
  targets: { conversation_id: string; name: string; channel: string; status: string }[];
}

export interface AutomationRun {
  id: string;
  automation_id: string;
  automation_title: string | null;
  status: RunStatus;
  outputs: RunOutput[];
  pending_actions: PendingAction[];
  error: string | null;
  files: { id: string; filename: string; size: number }[];
  started_at: string;
  finished_at: string | null;
  decided_at: string | null;
}

export interface AutomationSummary {
  id: string;
  title: string;
  request_text: string;
  language: string | null;
  summary: string | null;
  status: AutomationStatus;
  error: string | null;
  review_notes: string | null;
  needs_approval: boolean;
  input_tokens: number;
  output_tokens: number;
  run_count: number;
  last_run_at: string | null;
  last_run_status: RunStatus | null;
  created_at: string;
}

export interface AutomationDetail extends AutomationSummary {
  steps: AutomationStep[];
  runs: AutomationRun[];
}
