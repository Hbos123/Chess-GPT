"use client";

import { supabase } from "@/lib/supabase";

import { getBackendBase } from "@/lib/backendBase";

const BACKEND_URL = getBackendBase();

let _appSessionId: string | null = null;
let _cachedUserId: string | null = null;
let _cachedUserIdAt: number = 0;

let _lastCompletedInteraction: { interactionId: string; completedAtMs: number } | null = null;

function uuidv4(): string {
  // Modern browsers
  const g = (globalThis as any).crypto;
  if (g?.randomUUID) return g.randomUUID();
  // Fallback (non-crypto, but acceptable for client correlation IDs)
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

export function getOrCreateAppSessionId(): string {
  if (_appSessionId) return _appSessionId;
  try {
    const existing = window.localStorage.getItem("chessgpt_app_session_id");
    if (existing) {
      _appSessionId = existing;
      return existing;
    }
    const fresh = uuidv4();
    window.localStorage.setItem("chessgpt_app_session_id", fresh);
    _appSessionId = fresh;
    return fresh;
  } catch {
    _appSessionId = uuidv4();
    return _appSessionId;
  }
}

async function getUserIdCached(): Promise<string | null> {
  const now = Date.now();
  // Cache for 30s to avoid spamming auth calls
  if (_cachedUserId && now - _cachedUserIdAt < 30000) return _cachedUserId;
  const {
    data: { user },
  } = await supabase.auth.getUser();
  _cachedUserId = user?.id ?? null;
  _cachedUserIdAt = now;
  return _cachedUserId;
}

export async function buildLearningHeaders(): Promise<{ interactionId: string; headers: Record<string, string> }> {
  const appSessionId = getOrCreateAppSessionId();
  const userId = await getUserIdCached();
  const interactionId = uuidv4();

  const headers: Record<string, string> = {
    "X-App-Session-Id": appSessionId,
    "X-Interaction-Id": interactionId,
    "X-Frontend-Version": process.env.NEXT_PUBLIC_APP_VERSION || "dev",
  };
  if (userId) headers["X-User-Id"] = userId;

  return { interactionId, headers };
}

export function noteInteractionCompleted(interactionId: string) {
  _lastCompletedInteraction = { interactionId, completedAtMs: Date.now() };
}

export async function flushNextActionForLastInteraction(nextActionType: string) {
  const last = _lastCompletedInteraction;
  if (!last) return;
  const dt = Date.now() - last.completedAtMs;
  _lastCompletedInteraction = null;

  try {
    const { headers } = await buildLearningHeaders();
    await fetch(`${BACKEND_URL}/learning/log_behavior`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...headers },
      body: JSON.stringify({
        interaction_id: last.interactionId,
        time_to_next_action_ms: dt,
        next_action_type: nextActionType,
      }),
      keepalive: true,
    });
  } catch {
    // swallow (behavior signals are best-effort)
  }
}

export async function logUserReprompt(type: "clarify" | "disagree" | "new_topic", interactionId?: string) {
  const targetId = interactionId || _lastCompletedInteraction?.interactionId;
  if (!targetId) return;

  try {
    const { headers } = await buildLearningHeaders();
    await fetch(`${BACKEND_URL}/learning/log_behavior`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...headers },
      body: JSON.stringify({
        interaction_id: targetId,
        event_type: "user_reprompt",
        payload: { reprompt_type: type },
      }),
      keepalive: true,
    });
  } catch {
    // swallow (behavior signals are best-effort)
  }
}

export async function logAnalysisAbandoned(
  reason: "timeout" | "exit" | "error" | "user_navigation",
  interactionId?: string
) {
  const targetId = interactionId || _lastCompletedInteraction?.interactionId;
  if (!targetId) return;

  try {
    const { headers } = await buildLearningHeaders();
    await fetch(`${BACKEND_URL}/learning/log_behavior`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...headers },
      body: JSON.stringify({
        interaction_id: targetId,
        event_type: "analysis_abandoned",
        payload: { reason },
      }),
      keepalive: true,
    });
  } catch {
    // swallow (behavior signals are best-effort)
  }
}


