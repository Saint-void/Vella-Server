import audioop
from dataclasses import dataclass
from typing import Any

import numpy as np

from volco.state_machine import log_voice_event


@dataclass
class ASRConfig:
    sample_rate: int = 16000
    language: str = "en"
    beam_size: int = 2
    min_audio_ms: int = 350
    min_rms: int = 120
    vad_min_silence_ms: int = 500


class WhisperASREngine:
    """
    Single-shot Faster-Whisper ASR wrapper.

    The router calls this only after endpointing has produced a complete speech
    segment. There is intentionally no streaming transcription loop here.
    """

    def __init__(self, whisper_model: Any, config: ASRConfig = ASRConfig()):
        self.whisper_model = whisper_model
        self.config = config

    def transcribe_pcm(self, pcm16: bytes) -> str:
        duration_ms = int(len(pcm16) / 2 / self.config.sample_rate * 1000)
        rms = audioop.rms(pcm16, 2) if pcm16 else 0
        log_voice_event("asr_started", duration_ms=duration_ms, rms=rms)

        if duration_ms < self.config.min_audio_ms:
            log_voice_event(
                "noise_filtered",
                reason="asr_segment_too_short",
                duration_ms=duration_ms,
            )
            log_voice_event("asr_result", text="")
            return ""

        if rms < self.config.min_rms:
            log_voice_event(
                "noise_filtered",
                reason="asr_segment_low_energy",
                rms=rms,
                threshold=self.config.min_rms,
            )
            log_voice_event("asr_result", text="")
            return ""

        audio_np = np.frombuffer(pcm16, dtype=np.int16).astype(np.float32) / 32768.0
        segments, _ = self.whisper_model.transcribe(
            audio_np,
            beam_size=self.config.beam_size,
            language=self.config.language,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=self.config.vad_min_silence_ms),
        )
        text = " ".join(segment.text for segment in segments).strip()
        log_voice_event("asr_result", text=text)
        return text
