export default function AssistantMeta({ meta }) {
  const cached = meta.resolution_source === "LLM_CACHE";
  return (
    <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 border-t border-white/10 pt-2 text-xs text-slate-400">
      <span>
        source:{" "}
        <b data-testid="meta-source" className={cached ? "text-emerald-400" : "text-sky-400"}>
          {meta.resolution_source}
        </b>
      </span>
      <span>model: <b data-testid="meta-model" className="text-slate-300">{meta.model}</b></span>
      <span>latency: <b data-testid="meta-latency" className="text-slate-300">{meta.latency_ms}</b> ms</span>
      <span>in tokens: <b data-testid="meta-input-tokens" className="text-slate-300">{meta.input_tokens}</b></span>
      <span>out tokens: <b data-testid="meta-output-tokens" className="text-slate-300">{meta.output_tokens}</b></span>
      <span>key: <b className="text-slate-300">{meta.key_id ?? "none"}</b></span>
      <span>fallbacks: <b className="text-slate-300">{meta.fallback_attempts}</b></span>
    </div>
  );
}
