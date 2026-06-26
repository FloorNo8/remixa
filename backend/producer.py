"""
Sound Producer Module - Programmatic DSP mastering pipeline.
Implements dynamic EQ, stereo widening, and peak limiting/loudness maximization.
"""

import os
import torch
import torchaudio
import structlog
from typing import Optional

logger = structlog.get_logger()

class AudioProducer:
    """
    DSP mastering pipeline for AI-generated music tracks.
    Aims to elevate raw generation to commercial loudness, clarity, and impact.
    """
    
    def __init__(self, sample_rate: int = 32000):
        self.sample_rate = sample_rate
        
    def apply_stereo_widening(self, wav: torch.Tensor, amount: float = 1.25) -> torch.Tensor:
        """
        Apply Mid/Side stereo widening.
        Keeps low frequencies centered (mono) and widens the mid-to-high frequencies.
        
        Args:
            wav: Input audio tensor shape [channels, samples] (must be stereo, channels=2)
            amount: Widening gain multiplier (typically 1.1 to 1.5)
        """
        if wav.ndim < 2 or wav.shape[0] != 2:
            # Fallback for mono or invalid shapes: return original
            return wav
            
        # Convert to Mid/Side
        mid = (wav[0] + wav[1]) / 2.0
        side = (wav[0] - wav[1]) / 2.0
        
        # Widen side channel
        side = side * amount
        
        # Reconstruct Left/Right
        left = mid + side
        right = mid - side
        
        return torch.stack([left, right])

    def apply_low_cut(self, wav: torch.Tensor) -> torch.Tensor:
        """
        Apply low-cut (high-pass) filter at 30Hz to remove sub-audible room rumble
        and clean up headroom.
        """
        try:
            # High-pass filter via torchaudio functional API
            return torchaudio.functional.highpass_biquad(
                waveform=wav,
                sample_rate=self.sample_rate,
                cutoff_freq=30.0
            )
        except Exception as e:
            logger.warning("low_cut_failed_falling_back", error=str(e))
            return wav

    def apply_high_shelf(self, wav: torch.Tensor, gain_db: float = 2.0) -> torch.Tensor:
        """
        Apply high-shelf filter at 10kHz to add brightness ("air") to the track.
        """
        try:
            # High-shelf filter via torchaudio functional API (treble_biquad)
            return torchaudio.functional.treble_biquad(
                waveform=wav,
                sample_rate=self.sample_rate,
                gain=gain_db,
                central_freq=10000.0
            )
        except Exception as e:
            logger.warning("high_shelf_failed_falling_back", error=str(e))
            return wav

    def apply_limiting_and_maximize(self, wav: torch.Tensor, target_db: float = -0.5, drive_db: float = 3.0) -> torch.Tensor:
        """
        Maximize perceived loudness using drive gain and soft clipping (tanh),
        then peak limit to target_db.
        """
        # Convert dB to linear amplitude
        target_amp = 10.0 ** (target_db / 20.0)
        drive_amp = 10.0 ** (drive_db / 20.0)
        
        # Apply drive gain to saturate audio
        driven = wav * drive_amp
        
        # Apply soft clipping to saturate peaks
        saturated = torch.tanh(driven)
        
        # Normalize to target peak amplitude
        max_val = torch.max(torch.abs(saturated))
        if max_val > 0:
            mastered = (saturated / max_val) * target_amp
        else:
            mastered = saturated
            
        return mastered

    def master_track(
        self, 
        wav_path: str, 
        output_path: str, 
        style: str,
        drive_db: Optional[float] = None,
        high_shelf_db: Optional[float] = None,
        stereo_width: Optional[float] = None
    ) -> None:
        """
        Load audio, execute the full mastering pipeline, and save.
        """
        # Load audio
        wav, sr = torchaudio.load(wav_path)
        self.sample_rate = sr
        
        # 1. Clean headroom with low-cut filter
        wav = self.apply_low_cut(wav)
        
        # 2. Add high-end clarity depending on genre
        shelf_gain = high_shelf_db
        if shelf_gain is None:
            if style in ("lofi", "ambient"):
                shelf_gain = 1.0
            else:
                shelf_gain = 2.5
        wav = self.apply_high_shelf(wav, gain_db=shelf_gain)
            
        # 3. Apply stereo widening
        if wav.shape[0] == 2:
            width = stereo_width if stereo_width is not None else 1.25
            wav = self.apply_stereo_widening(wav, amount=width)
            
        # 4. Saturation & Peak Limiting
        drive = drive_db
        if drive is None:
            drive = 4.0 if style in ("trap", "house", "techno", "dnb") else 2.0
        wav = self.apply_limiting_and_maximize(wav, target_db=-0.5, drive_db=drive)
        
        # Save output
        torchaudio.save(output_path, wav, sr)
