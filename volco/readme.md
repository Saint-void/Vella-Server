🔴 Fix before anything else ships (security/stability)

 
 Authenticate the WebRTC session — right now anyone can POST /volco_webrtc/offer with any user_id and hijack a session. Issue a signed token (JWT) at login, require it on the offer, and bind the data channel to the verified user, not a client-supplied string.
 Stop swallowing exceptions with bare print() — replace with real logging (you already have a logger pattern in state_machine.py; use it everywhere) and add alerting for repeated failures (ASR crash, TTS crash, LLM unreachable).
 Rate-limit / auth the REST endpoints (/api/volco/login, /intent/process) — no throttling currently, so it's brute-forceable.
 Add reconnect/session-timeout handling for stale RTCPeerConnections beyond just failed/closed.

🟠 Consolidate the architecture (pay down debt before adding features)

 Merge the two LLM paths — agent.py (shared.models.llm, streaming) and actions/chat.py (OllamaClient, non-streaming) do the same job differently. Pick one client abstraction and one model, or explicitly document why two tiers exist (e.g., "fast intent model" vs "quality chat model") and wire both call sites through it consistently.
 Rename one of the two router.py files — confusing to navigate/import (volco/router.py vs volco/intent/router.py).
 Fix the mutable-default-arg pattern in ASRConfig = ASRConfig().
 Give the ASR/TTS pipeline real failure feedback — right now if Kokoro throws, the user gets silence with zero signal. Send an explicit "TTS_FAILED" message like you already do for "NO_SPEECH".
 Share classifier/router instances instead of re-instantiating IntentClassifier()/IntentRouter() (and spinning up a fresh OllamaClient) on every single call.

🟡 Core "personal assistant" capabilities you're missing
To feel like Alexa/Siri/Jarvis rather than a voice-controlled chatbot, you need an actual skills/capabilities layer, not just Spotify:

 Real device/smart-home control — lights, thermostat, locks (Matter/HomeKit/Google Home bridge). This is the single biggest "wow" factor gap.
 Calendar & reminders — "remind me to call mom at 5", "what's on my calendar today". Needs actual scheduling + push notification back to device.
 Timers & alarms — table stakes, currently absent.
 Real Spotify integration — spotify.py is fully mocked. Wire up the actual Spotify Web API (OAuth per user, device transfer, search-then-play instead of blind query strings).
 Weather, news, general knowledge lookups — currently everything non-Spotify routes to the small local LLM, which will hallucinate on anything needing live data. Add tool-use/function-calling so the LLM can call out to real APIs (weather, search, etc.) instead of guessing.
 Notifications/proactivity — Jarvis-like assistants push info ("your meeting starts in 5 min") rather than only responding to pull. You'd need a background scheduler + the app-broadcast channel you already have wired up.
 Multi-turn context / follow-ups — "play some jazz" → "skip this one" should retain context. Right now each COMMIT is classified independently with no conversation memory feeding the intent classifier (only the chat LLM gets add_memory/vector recall).
 Interruption / barge-in — real assistants let you interrupt TTS mid-sentence by speaking. Your state machine currently blocks incoming audio while is_processing — worth designing barge-in explicitly rather than just dropping audio.

🟢 Quality-of-life / "feels premium" polish

 Wake word detection on-device — I don't see an actual wake-word model in this code (state machine has WAKE_WORD_DETECTED but it's triggered just by "first audio bytes arriving"), so there's no real "Hey Vella" gating happening server-side. Confirm this lives correctly on the headset firmware, or add it here.
 Streaming ASR / partial transcripts — you're explicitly single-shot ("no streaming transcription loop" per the docstring). Alexa/Siri show/act on partial results for lower perceived latency. Worth revisiting once budget allows.
 Personality/consistency guardrails — VOLCO_SYSTEM_INSTRUCTION is generic boilerplate; a distinct voice/personality (like Jarvis's dry wit) is part of what makes these assistants memorable. Worth investing real writing time here.
 Error recovery language — "I could not reach the chat model right now" is fine functionally but flat; consider consistent, branded failure phrasing.
 Multi-device/multi-room support — track which headset/output should respond when a user has more than one.
 Analytics/observability dashboard — you're already emitting structured log_voice_events; pipe them into something queryable (even just structured JSON logs into a log store) so you can see latency per stage (ASR time, LLM time, TTS time) and catch regressions.

🔵 Longer-term differentiation (the "better than Alexa/Siri" part)

 On-device/local-first privacy story — you're already running Whisper + Ollama locally, which is a genuine differentiator over cloud-only assistants. Lean into that in product messaging once security is fixed.
 Agentic multi-step tasks — "book me a table and text Sarah when it's confirmed" requires actual planning/tool orchestration, not single-intent classification. This is where you'd go beyond Alexa's capability ceiling.
 Cross-session personal memory — you have add_memory/vector store already; make sure retrieval is actually used to personalize responses (recall preferences, past requests) rather than just logging.