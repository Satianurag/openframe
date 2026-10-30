# App orchestration

Popcorn, Ads, Content Factory and Billboard share the durable application document/job system and serial render queue. They do not create independent inference workers.

- Popcorn atomically queues ordered scenes with immutable document snapshots. Retry reuses the recorded scene request. Completed outputs can be handed to a new Cinema document without changing the original board.
- Ads supports image/video creation and an existing-video assembly path. Narration, timing, silence padding, background audio, ducking, captions and exports are explicit. Corrections preserve completed video/speech where still valid.
- Content Factory can use the configured Local Qwen visual planner to inspect attached references and propose editable shots. References, proposal status and user approval are durable. No render starts merely because a proposal succeeded.
- Billboard uses an explicit image preparation stage followed by a video that consumes that completed image. Preparation-only media is omitted from final video assembly. Reload, cancellation and resume use the same persisted sequence.

Targeted isolated queue/HTTP/media/bundle checks passed. Scoped desktop acceptance covers ordered Popcorn results/handoff; Ads narration, manual caption correction, burn-in, subtitle downloads and final playback; Content Factory reference analysis/reopen/manual save; and Billboard dependency/playback/reuse.

These results do not certify every prompt, music/prosody quality or maximum-duration combination. Local speech/planning requires its configured Linux CUDA runtime. No hosted Cloud speech/planner support is claimed. See [APPS-API.md](APPS-API.md), [desktop scope](DESKTOP-VALIDATION.md), [narration runtime](../custom_nodes/openframe/NARRATION-RUNTIME.md) and [planner runtime](../custom_nodes/openframe/PLANNER-RUNTIME.md).
