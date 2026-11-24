import { useEffect, useRef, useState } from "react";
import MessageBubble from "./components/MessageBubble.jsx";
import { sendChat } from "./services/api.js";

// A brand new session on every page load.
const newSessionId = () => `s-${crypto.randomUUID().slice(0, 8)}`;

export default function App() {
  const [sessionId] = useState(newSessionId);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [simulate, setSimulate] = useState("");
  const [loading, setLoading] = useState(false);
  const endRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const add = (m) => setMessages((prev) => [...prev, { ...m, time: new Date() }]);

  async function send() {
    const text = input.trim();
    if (!text || loading) return;
    setInput("");
    add({ role: "user", content: text });
    setLoading(true);
    try {
      // Only the new message goes to the server; it keeps the history itself.
      const data = await sendChat({
        sessionId,
        message: text,
        systemPrompt: systemPrompt.trim(),
        simulateFailure: simulate.trim(),
      });
      add({ role: "assistant", content: data.reply, metadata: data.metadata });
    } catch (err) {
      add({ role: "error", content: err.message });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto flex h-full max-w-3xl flex-col text-slate-100">
      <header className="border-b border-white/10 px-4 py-3">
        <h1 className="text-lg font-semibold">LLM Chatbot</h1>
        <p className="text-xs text-slate-400">
          Key failover · LiteLLM cache · session <span className="font-mono">{sessionId}</span>
        </p>
      </header>

      <details className="border-b border-white/10 px-4 py-2 text-sm text-slate-300">
        <summary className="cursor-pointer text-slate-400">Options</summary>
        <div className="mt-2 grid gap-2 sm:grid-cols-2">
          <label className="text-xs text-slate-400">
            System prompt (optional)
            <input
              data-testid="system-prompt-input"
              value={systemPrompt}
              onChange={(e) => setSystemPrompt(e.target.value)}
              placeholder="You are a helpful assistant."
              className="mt-1 w-full rounded-md border border-white/10 bg-slate-900 px-2 py-1 text-slate-100"
            />
          </label>
          <label className="text-xs text-slate-400">
            X-Simulate-Failure (demo, e.g. key_1=429)
            <input
              value={simulate}
              onChange={(e) => setSimulate(e.target.value)}
              placeholder="key_1=429,key_2=500 or *=429"
              className="mt-1 w-full rounded-md border border-white/10 bg-slate-900 px-2 py-1 font-mono text-slate-100"
            />
          </label>
        </div>
      </details>

      <main className="flex-1 space-y-3 overflow-y-auto px-4 py-4">
        {messages.length === 0 && (
          <p className="mt-10 text-center text-slate-500">Send a message to start the conversation.</p>
        )}
        {messages.map((m, i) => (
          <MessageBubble key={i} message={m} />
        ))}
        {loading && (
          <div className="flex justify-start" aria-live="polite">
            <div className="rounded-2xl bg-slate-800 px-4 py-2 text-slate-400">
              <span className="animate-pulse">Assistant is thinking…</span>
            </div>
          </div>
        )}
        <div ref={endRef} />
      </main>

      <form
        className="flex gap-2 border-t border-white/10 p-3"
        onSubmit={(e) => {
          e.preventDefault();
          send();
        }}
      >
        <input
          data-testid="chat-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type a message…"
          maxLength={4000}
          className="flex-1 rounded-lg border border-white/10 bg-slate-900 px-3 py-2 text-slate-100 outline-none focus:border-indigo-500"
        />
        <button
          data-testid="send-button"
          type="submit"
          disabled={loading || !input.trim()}
          className="rounded-lg bg-indigo-600 px-4 py-2 font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
        >
          Send
        </button>
      </form>
    </div>
  );
}
