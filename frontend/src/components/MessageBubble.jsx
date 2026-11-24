import AssistantMeta from "./AssistantMeta.jsx";

export default function MessageBubble({ message }) {
  const time = message.time.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-2xl rounded-br-sm bg-indigo-600 px-4 py-2 text-white">
          <p className="whitespace-pre-wrap break-words">{message.content}</p>
          <p className="mt-1 text-right text-[10px] text-indigo-200">{time}</p>
        </div>
      </div>
    );
  }

  if (message.role === "error") {
    return (
      <div className="flex justify-start">
        <div role="alert" className="max-w-[85%] rounded-2xl border border-red-500/40 bg-red-500/10 px-4 py-2 text-red-300">
          {message.content}
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start">
      <div data-testid="assistant-message" className="max-w-[90%] rounded-2xl rounded-bl-sm bg-slate-800 px-4 py-2 text-slate-100">
        <p className="whitespace-pre-wrap break-words">{message.content}</p>
        <p className="mt-1 text-[10px] text-slate-500">{time}</p>
        <AssistantMeta meta={message.metadata} />
      </div>
    </div>
  );
}
