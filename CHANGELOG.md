# Changelog

All notable changes to `spekoai` (Python SDK) will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- OpenAI provider-direct realtime sessions now honor the negotiated WebRTC
  transport, including RTP audio, SDP exchange, data-channel events, and
  billing-sideband binding before media is enabled.

## [0.2.0] - 2026-07-24

Full feature parity with `@spekoai/sdk` 0.4.x (plus its unreleased surface).

### Added

- **Resource namespaces** on both `Speko` and `AsyncSpeko`:
  - `speko.agents` — agent CRUD, `attach_phone_number` / `detach_phone_number`,
    `list_calls`, and `speko.agents.tools` (tool CRUD with typed
    inline / webhook / builtin / integration sources, plus `list_chat_tools`
    which returns `ChatTool`s ready for `complete(tools=...)`).
  - `speko.knowledge_bases` — KB CRUD, document CRUD, `upload_document`
    (register + signed-URL PUT + finalize in one call) and
    `poll_document_ready`.
  - `speko.phone_numbers` — list/get/create/update/delete,
    `search_available`, `import_sip_trunk`, and business verification:
    `get_kyb`, `save_kyb_draft`, `submit_kyb`.
  - `speko.calls` — `get`, `events`, `report`, `finalize_report`,
    `recording`, `web_join`, `end`, and transfers (`blind_transfer`,
    `warm_transfer`, `complete_warm_transfer`, `cancel_warm_transfer`).
  - `speko.callbacks` — scheduled-callback `list` / `get` / `cancel` /
    `dispatch`.
  - `speko.sessions` — `transcript` snapshot and `stream`, a live SSE
    iterator that auto-reconnects through server stream rotations with an
    internal cursor and event dedupe.
  - `speko.voice.dial` — outbound phone calls with the full dial surface
    (agent binding, prompt template `variables`, `turn_handling`,
    `telephony` / AMD hints, `webhook_tags`, metadata).
  - `speko.voices` — read-only TTS voice catalog.
  - `speko.webhooks` — workspace webhook endpoint CRUD plus
    `speko.webhooks.deliveries` (`list` / `get` / `redeliver`).
- **Streaming primitives**: `transcribe_stream` (typed meta / transcript /
  done events), `complete_stream` (meta / delta / tool_call /
  server_tool_call / done), and `synthesize_stream` (audio chunks +
  provider metadata) on both clients.
- **`complete` tool calling**: `tools`, `tool_choice`,
  `parallel_tool_calls`, `max_tool_hops`, `reasoning_effort`; results carry
  `tool_calls`, and `ChatMessage` supports `role="tool"`, `tool_calls`,
  `tool_call_id`, and `is_error`.
- **New primitive options**: `session_id` (usage attribution via
  `x-session-id`) on transcribe/synthesize/complete; `keywords` +
  `stt_language` on transcribe; `model`, `instructions`, `spoken_form` on
  synthesize.
- **Realtime (S2S) parity**: `inworld`, `alibaba`, and `speko-lab`
  providers; `agent_id` and `webhook_tags` connect params; input/output
  sample rates surfaced on the session; new `ready`, `interruption`, and
  `server_tool_call` frames.
- Pydantic models for the whole REST surface, mirroring the TS types
  (camelCase wire aliases; the calls/callbacks family models the API's
  snake_case serialization directly).
- First-party pytest suite (respx-mocked httpx).

### Fixed

- HTTP errors on streaming endpoints (`/v1/transcribe`, `/v1/complete`)
  now raise `SpekoApiError` with the server's message/code instead of
  crashing with httpx's `ResponseNotRead`.

## [0.1.1] - 2026-04-26

### Added

- `RoutingIntent.region` — optional string forwarded to the gateway as
  `intent.region`. Set when latency to a specific geography matters
  (e.g. `"us-east4"`, `"eu-west1"`); STT/TTS rankings differ per
  region. Omitting it preserves the previous behaviour: the server
  defaults to `"global"`, which surfaces the region-agnostic (batch)
  benchmark rows. New keyword arg on `transcribe()` and
  `synthesize()` (sync + async); also accepted on the `intent`
  dict / `RoutingIntent` model passed to `complete()`.

## [0.1.0] - 2026-04-26

### Removed

- **BREAKING**: `vertical` field removed from `RoutingIntent` and from the
  `transcribe()` / `synthesize()` keyword arguments. The router now ranks
  on `(language, optimize_for)` only. `Vertical` literal is no longer
  exported from `spekoai`. Callers passing `vertical=...` will hit a
  `TypeError` at the call site.

## [0.0.1] - 2026-04-18

### Added

- Initial release. Surface mirrors `@spekoai/sdk`:
  `speko.transcribe(audio, ...)`, `speko.synthesize(text, ...)`,
  `speko.complete(messages=..., intent=...)`, `speko.usage.get(...)`.
- Sync `Speko` and async `AsyncSpeko` clients.
- Pydantic v2 models with camelCase wire aliases and snake_case Python
  fields: `RoutingIntent`, `PipelineConstraints`, `AllowedProviders`,
  `ChatMessage`, `TranscribeResult`, `SynthesizeResult`, `CompleteResult`,
  `UsageSummary`, `UsageByProvider`, plus `OptimizeFor` literals.
- Typed errors: `SpekoApiError`, `SpekoAuthError`, `SpekoRateLimitError`.
