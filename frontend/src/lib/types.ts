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
