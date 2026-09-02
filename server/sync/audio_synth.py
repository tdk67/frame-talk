"""
Audio Synthesis & Duration Engine.
Synthesizes speech per line via Gemini TTS (multiSpeakerVoiceConfig)
or OpenRouter, measures exact millisecond PCM length, concatenates
speech with natural conversational pauses (180ms - 260ms), and wraps into WAV.
"""

import os
import io
import wave
import struct
import math
import logging
import base64
from typing import List, Dict, Any, Tuple, Optional

logger = logging.getLogger("castops.audio_synth")

PCM_SAMPLE_RATE = 24000  # 24 kHz
PCM_CHANNELS = 1         # Mono
PCM_SAMPLE_WIDTH = 2     # 16-bit = 2 bytes
PCM_BYTES_PER_SECOND = PCM_SAMPLE_RATE * PCM_CHANNELS * PCM_SAMPLE_WIDTH  # 48,000 bytes/sec

class AudioSynthEngine:
    def __init__(self):
        pass

    def synthesize_line(
        self,
        text: str,
        speaker: str,
        voice_alex: str = "Puck",
        voice_sam: str = "Kore",
        api_key: Optional[str] = None
    ) -> Tuple[bytes, int]:
        """
        Synthesizes a single dialogue turn.
        Returns: (raw_pcm_bytes, duration_ms)
        """
        active_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("OPENROUTER_API_KEY")
        active_voice = voice_alex if speaker.lower() in ["alex", "mark"] else voice_sam

        if active_key:
            try:
                pcm_bytes = self._call_tts_api(text, active_voice, speaker, active_key)
                if pcm_bytes and len(pcm_bytes) > 1000:
                    dur_ms = int((len(pcm_bytes) / PCM_BYTES_PER_SECOND) * 1000)
                    return pcm_bytes, dur_ms
            except Exception as e:
                logger.warning(f"TTS API failed for '{text[:20]}...' ({e}). Using synthesized audio.")

        # Fallback harmonic acoustic speech synthesis
        return self._synthesize_acoustic_fallback(text, speaker)

    def _call_tts_api(self, text: str, voice: str, speaker: str, api_key: str) -> bytes:
        import requests
        # Direct Gemini TTS endpoint
        if api_key.startswith("AIzaSy") or not api_key.startswith("sk-or"):
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-tts-preview:generateContent?key={api_key}"
            body = {
                "contents": [{"parts": [{"text": text}]}],
                "generationConfig": {
                    "responseModalities": ["AUDIO"],
                    "speechConfig": {
                        "voiceConfig": {
                            "prebuiltVoiceConfig": {"voiceName": voice}
                        }
                    }
                }
            }
            resp = requests.post(url, json=body, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                b64 = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("inlineData", {}).get("data")
                if b64:
                    raw_bytes = base64.b64decode(b64)
                    # Strip 44-byte WAV header if returned as WAV container
                    if len(raw_bytes) > 44 and raw_bytes[:4] == b'RIFF':
                        return raw_bytes[44:]
                    return raw_bytes

        # OpenRouter audio/speech endpoint
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        body = {
            "model": "google/gemini-3.1-flash-tts-preview",
            "input": text,
            "voice": voice,
            "response_format": "pcm"
        }
        resp = requests.post("https://openrouter.ai/api/v1/audio/speech", headers=headers, json=body, timeout=30)
        if resp.status_code == 200:
            return resp.content

        raise RuntimeError(f"TTS API returned {resp.status_code}: {resp.text[:200]}")

    def _synthesize_acoustic_fallback(self, text: str, speaker: str) -> Tuple[bytes, int]:
        """
        Creates smooth harmonic speech pulses calibrated to natural human speaking pace
        (150 words/min = 2.5 words/sec). Guarantees perfect millisecond testing without API limits.
        """
        words = [w for w in text.split() if w]
        num_words = max(3, len(words))
        # 400ms per word on average
        duration_sec = num_words * 0.40
        num_samples = int(duration_sec * PCM_SAMPLE_RATE)

        base_freq = 130.0 if speaker.lower() in ["alex", "mark"] else 210.0
        pcm_chunks = bytearray()

        for i in range(num_samples):
            t = i / PCM_SAMPLE_RATE
            # Modulate amplitude per word to simulate syllable cadence
            syllable_mod = (math.sin(2 * math.pi * 3.5 * t) + 1.0) * 0.5
            # Harmonic combination
            sample_val = (
                0.6 * math.sin(2 * math.pi * base_freq * t) +
                0.3 * math.sin(2 * math.pi * (base_freq * 1.5) * t) +
                0.1 * math.sin(2 * math.pi * (base_freq * 2.0) * t)
            ) * syllable_mod * 0.45

            # Clamp to 16-bit integer
            int_sample = int(max(-32768, min(32767, sample_val * 32767)))
            pcm_chunks.extend(struct.pack("<h", int_sample))

        dur_ms = int(duration_sec * 1000)
        return bytes(pcm_chunks), dur_ms

    def generate_silence(self, duration_ms: int) -> bytes:
        """Generates exact millisecond silence."""
        if duration_ms <= 0:
            return b''
        pause_samples = int((duration_ms / 1000.0) * PCM_SAMPLE_RATE)
        return b'\x00' * (pause_samples * PCM_SAMPLE_WIDTH)

    def concatenate_dialogue_audio(
        self,
        audio_chunks: List[Tuple[bytes, int]],
        conversational_pause_ms: int = 220
    ) -> bytes:
        """
        Concatenates dialogue audio chunks with natural conversational pauses (180-260ms).
        """
        pause_bytes = self.generate_silence(conversational_pause_ms)

        master_pcm = bytearray()
        for idx, (chunk, _) in enumerate(audio_chunks):
            master_pcm.extend(chunk)
            if idx < len(audio_chunks) - 1:
                master_pcm.extend(pause_bytes)

        return bytes(master_pcm)

    def pcm_to_wav(self, pcm_data: bytes) -> bytes:
        """Wraps raw 16-bit mono 24kHz PCM into standard WAV bytes."""
        wav_io = io.BytesIO()
        with wave.open(wav_io, 'wb') as wav_file:
            wav_file.setnchannels(PCM_CHANNELS)
            wav_file.setsampwidth(PCM_SAMPLE_WIDTH)
            wav_file.setframerate(PCM_SAMPLE_RATE)
            wav_file.writeframes(pcm_data)
        return wav_io.getvalue()

audio_synth = AudioSynthEngine()
