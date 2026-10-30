export type PlannerInfo = {
  model_id: string;
  name: string;
  budget_policy?: string;
  max_budget_seconds?: number;
  legacy_text_available?: boolean;
  legacy_text_detail?: string;
  providers: { id: string; name?: string; model_id?: string; available: boolean; detail: string }[];
};
type Plan = {
  status: string;
  error?: string;
  request?: { budget_seconds?: number; provider?: string; model_id?: string };
  proposal?: { metadata: Record<string, unknown> };
};
function duration(seconds: number) {
  const rounded = Math.round(seconds);
  const minutes = Math.floor(rounded / 60),
    remainder = rounded % 60;
  return minutes ? `${minutes}m${remainder ? ` ${remainder}s` : ''}` : `${remainder}s`;
}

/** Display recorded limits/provenance; never turn an execution budget into an ETA. */
export function plannerRunNote(plan: Plan): string {
  if (plan.status === 'queued' || plan.status === 'running') {
    const budget = plan.request?.budget_seconds;
    return (
      (plan.request?.provider === 'local' && plan.request?.model_id === 'qwen3.8-planner'
        ? 'The configured ComfyUI host is preparing the proposal. You can return to this saved draft later.'
        : 'Progress updates between shot batches. You can return to this saved draft later.') +
      (typeof budget === 'number' && budget > 0
        ? ` Execution limit: ${duration(budget)}; this is not an estimated wait.`
        : '')
    );
  }
  if (plan.status === 'succeeded') {
    const metadata = plan.proposal?.metadata;
    const model = metadata?.repository || metadata?.model_id;
    const seconds = metadata?.seconds;
    return [
      typeof model === 'string' ? `Planned with ${model}.` : '',
      typeof seconds === 'number' && Number.isFinite(seconds)
        ? `Recorded planning time: ${duration(seconds)}.`
        : '',
    ]
      .filter(Boolean)
      .join(' ');
  }
  if (
    plan.status === 'failed' &&
    /budget|deadline|timed?\s*out|time.*limit/i.test(plan.error || '')
  ) {
    return 'Planning reached its execution limit. Shorten the brief or split the request, then submit a new proposal explicitly.';
  }
  return '';
}

export function plannerAvailable(info: PlannerInfo | null, provider: string, model: string) {
  return provider === 'local' && model === 'qwen-planner-7b'
    ? info?.legacy_text_available === true
    : !!info?.providers.some((item) => item.id === provider && item.available);
}
