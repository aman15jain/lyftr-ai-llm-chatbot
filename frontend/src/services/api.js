// The API URL is injected at BUILD time by Vite (VITE_API_BASE_URL).
const API_BASE = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");

function describeError(status, body) {
  if (status === 503) return "All providers are unavailable right now. Please try again later.";
  if (status === 422) {
    const d = body?.detail;
    const first = Array.isArray(d) ? d[0]?.msg : d;
    return `Invalid request: ${first || "please check your message."}`;
  }
  if (status === 502) return "The AI provider rejected the request (check the configured model).";
  return (typeof body?.detail === "string" && body.detail) || `Request failed (HTTP ${status}).`;
}

export async function sendChat({ sessionId, message, systemPrompt, simulateFailure }) {
  const headers = { "Content-Type": "application/json" };
  if (simulateFailure) headers["X-Simulate-Failure"] = simulateFailure;
  const payload = { session_id: sessionId, message };
  if (systemPrompt) payload.system_prompt = systemPrompt;

  let res;
  try {
    res = await fetch(`${API_BASE}/chat`, { method: "POST", headers, body: JSON.stringify(payload) });
  } catch {
    throw new Error("Cannot reach the backend. Is it running and is VITE_API_BASE_URL correct?");
  }
  const body = await res.json().catch(() => null);
  if (!res.ok) throw new Error(describeError(res.status, body));
  return body;
}
