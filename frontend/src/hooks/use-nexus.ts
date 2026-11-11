"use client";

// Data hooks. Lesson 01 keeps the Inbox fresh by polling every few seconds.
// A later lesson replaces polling with a live connection; only this file changes.

import useSWR from "swr";

import { ApiError, fetcher } from "@/lib/api";
import type {
  AIReply,
  AISettings,
  Conversation,
  DashboardSummary,
  IntegrationStatus,
  ItemList,
  KnowledgeList,
  Message,
  WebhookEvent,
} from "@/lib/types";

const LIST_REFRESH_MS = 4000;
const THREAD_REFRESH_MS = 3000;
const SLOW_REFRESH_MS = 10000;

// Do not hammer the backend while it reports a setup problem.
const retry = { shouldRetryOnError: false } as const;

export function useConversations() {
  return useSWR<ItemList<Conversation>, ApiError>("/api/v1/conversations", fetcher, {
    refreshInterval: LIST_REFRESH_MS,
    ...retry,
  });
}

export function useMessages(conversationId: string | null) {
  return useSWR<ItemList<Message>, ApiError>(
    conversationId ? `/api/v1/conversations/${conversationId}/messages` : null,
    fetcher,
    { refreshInterval: THREAD_REFRESH_MS, ...retry },
  );
}

export function useDashboardSummary() {
  return useSWR<DashboardSummary, ApiError>("/api/v1/dashboard/summary", fetcher, {
    refreshInterval: LIST_REFRESH_MS,
    ...retry,
  });
}

export function useEvents(limit = 12) {
  return useSWR<ItemList<WebhookEvent>, ApiError>(`/api/v1/events?limit=${limit}`, fetcher, {
    refreshInterval: LIST_REFRESH_MS,
    ...retry,
  });
}

export function useChatwootStatus() {
  return useSWR<IntegrationStatus, ApiError>("/api/v1/integrations/chatwoot/status", fetcher, {
    refreshInterval: SLOW_REFRESH_MS,
    ...retry,
  });
}

export function useKnowledge() {
  return useSWR<KnowledgeList, ApiError>("/api/v1/knowledge", fetcher, retry);
}

export function useAISettings() {
  return useSWR<AISettings, ApiError>("/api/v1/ai/settings", fetcher, retry);
}

export function useAIActivity(limit = 30) {
  return useSWR<ItemList<AIReply>, ApiError>(`/api/v1/ai/activity?limit=${limit}`, fetcher, {
    refreshInterval: LIST_REFRESH_MS,
    ...retry,
  });
}
