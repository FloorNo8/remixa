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

PERSONA_CONSTRAINTS = {
    # ── MAJOR TIER ──────────────────────────────────────────────────────
    "default_producer": {
        "min_drive_db": 1.0, "max_drive_db": 5.0,
        "min_stereo_width": 1.0, "max_stereo_width": 1.3,
        "enable_sub_bass": False
    },
    "rubin_raw": {  # Rick Rubin — Minimalist subtraction
        "min_drive_db": 0.5, "max_drive_db": 3.0,
        "min_stereo_width": 1.0, "max_stereo_width": 1.2,
        "enable_sub_bass": False
    },
    "quincy_hifi": {  # Quincy Jones — Genre fusion, meticulous layering
        "min_drive_db": 1.5, "max_drive_db": 6.0,
        "min_stereo_width": 1.1, "max_stereo_width": 1.5,
        "enable_sub_bass": False
    },
    "zimmer_epic": {  # Hans Zimmer — Cinematic sub-bass, orchestral limiting
        "min_drive_db": 1.0, "max_drive_db": 5.5,
        "min_stereo_width": 1.1, "max_stereo_width": 1.5,
        "enable_sub_bass": True
    },
    "martin_pop": {  # Max Martin — Melodic math, high-gloss pop
        "min_drive_db": 2.0, "max_drive_db": 5.0,
        "min_stereo_width": 1.15, "max_stereo_width": 1.4,
        "enable_sub_bass": False
    },
    "lange_wall": {  # Mutt Lange — Wall of Sound perfectionist
        "min_drive_db": 2.5, "max_drive_db": 6.5,
        "min_stereo_width": 1.2, "max_stereo_width": 1.5,
        "enable_sub_bass": False
    },
    "gmartin_studio": {  # George Martin — Studio innovation, classical-pop hybrid
        "min_drive_db": 1.0, "max_drive_db": 4.0,
        "min_stereo_width": 1.0, "max_stereo_width": 1.35,
        "enable_sub_bass": False
    },
    "spector_wall": {  # Phil Spector — Original Wall of Sound, dense mono
        "min_drive_db": 3.0, "max_drive_db": 7.0,
        "min_stereo_width": 1.0, "max_stereo_width": 1.15,
        "enable_sub_bass": False
    },
    "dre_gfunk": {  # Dr. Dre — G-Funk, crisp mono-centric, deep low-end
        "min_drive_db": 2.0, "max_drive_db": 5.5,
        "min_stereo_width": 1.0, "max_stereo_width": 1.2,
        "enable_sub_bass": True
    },
    "eno_ambient": {  # Brian Eno — Ambient generative, wide soundscapes
        "min_drive_db": 0.5, "max_drive_db": 2.5,
        "min_stereo_width": 1.2, "max_stereo_width": 1.6,
        "enable_sub_bass": False
    },
    # ── MIDDLE TIER ─────────────────────────────────────────────────────
    "rock_arena": {  # Bob Rock — Arena metal, massive drums
        "min_drive_db": 2.0, "max_drive_db": 5.5,
        "min_stereo_width": 1.1, "max_stereo_width": 1.4,
        "enable_sub_bass": True
    },
    "dilla_swing": {  # J Dilla — Human swing, sidechain ducking, lo-fi warmth
        "min_drive_db": 1.0, "max_drive_db": 3.5,
        "min_stereo_width": 1.0, "max_stereo_width": 1.25,
        "enable_sub_bass": True
    },
    "timbaland_bounce": {  # Timbaland — Futuristic bounce, heavy sidechain
        "min_drive_db": 2.5, "max_drive_db": 5.5,
        "min_stereo_width": 1.1, "max_stereo_width": 1.35,
        "enable_sub_bass": True
    },
    "pharrell_sparse": {  # Pharrell — Sparse crunch, precise arrangement
        "min_drive_db": 1.5, "max_drive_db": 4.0,
        "min_stereo_width": 1.05, "max_stereo_width": 1.3,
        "enable_sub_bass": True
    },
    "godrich_detail": {  # Nigel Godrich — Nuanced detail, deliberate effects
        "min_drive_db": 0.5, "max_drive_db": 3.0,
        "min_stereo_width": 1.1, "max_stereo_width": 1.4,
        "enable_sub_bass": False
    },
    "albini_raw": {  # Steve Albini — Anti-compression purist, tape saturation
        "min_drive_db": 0.0, "max_drive_db": 1.5,
        "min_stereo_width": 1.0, "max_stereo_width": 1.15,
        "enable_sub_bass": False
    },
    "vig_power": {  # Butch Vig — Power rock, dynamic integrity
        "min_drive_db": 1.5, "max_drive_db": 4.5,
        "min_stereo_width": 1.1, "max_stereo_width": 1.35,
        "enable_sub_bass": False
    },
    "wallace_metal": {  # Andy Wallace — Parallel compression, cohesive metal
        "min_drive_db": 2.5, "max_drive_db": 6.0,
        "min_stereo_width": 1.15, "max_stereo_width": 1.45,
        "enable_sub_bass": True
    },
    # ── MINOR/NICHE TIER ────────────────────────────────────────────────
    "tubby_dub": {  # King Tubby — Dub master, deep bass, creative filtering
        "min_drive_db": 1.0, "max_drive_db": 3.5,
        "min_stereo_width": 1.0, "max_stereo_width": 1.3,
        "enable_sub_bass": True
    },
    "perry_dub": {  # Lee Scratch Perry — Dub chaos, metallic punch
        "min_drive_db": 1.5, "max_drive_db": 4.5,
        "min_stereo_width": 1.0, "max_stereo_width": 1.25,
        "enable_sub_bass": True
    },
    "sophie_hyper": {  # SOPHIE — Hyperpop, OTT multiband, waveshaping
        "min_drive_db": 3.0, "max_drive_db": 7.0,
        "min_stereo_width": 1.2, "max_stereo_width": 1.6,
        "enable_sub_bass": True
    },
    "skrillex_loud": {  # Skrillex — Maximum loudness, transient shaping
        "min_drive_db": 4.0, "max_drive_db": 8.0,
        "min_stereo_width": 1.2, "max_stereo_width": 1.5,
        "enable_sub_bass": True
    },
    "tainy_vibes": {  # Tainy — Modern Reggaeton, synth-heavy, sub-bass
        "min_drive_db": 1.5, "max_drive_db": 5.0,
        "min_stereo_width": 1.15, "max_stereo_width": 1.45,
        "enable_sub_bass": True
    },
    "luny_tunes": {  # Luny Tunes — Classic golden-era dembow punch
        "min_drive_db": 2.0, "max_drive_db": 6.0,
        "min_stereo_width": 1.05, "max_stereo_width": 1.35,
        "enable_sub_bass": True
    },
    "eliel_reggae": {  # DJ Eliel — Classic dancehall-reggaeton hybrid
        "min_drive_db": 1.0, "max_drive_db": 4.5,
        "min_stereo_width": 1.0, "max_stereo_width": 1.3,
        "enable_sub_bass": True
    },
}

class AudioProducer:
    """
    DSP mastering pipeline for AI-generated music tracks.
    Aims to elevate raw generation to commercial loudness, clarity, and impact.
    """
    STYLE_TARGET_LUFS = {
        "lofi": -14.0,
        "ambient": -16.0,
        "house": -11.0,
        "techno": -10.0,
        "trap": -11.0,
        "reggaeton": -10.0,
    }
    DEFAULT_TARGET_LUFS = -14.0
    
    def __init__(self, sample_rate: int = 32000):
        self.sample_rate = sample_rate
        
    def calculate_lufs(self, wav: torch.Tensor) -> float:
        """
        Calculate K-weighted integrated loudness (LUFS) according to ITU-R BS.1770-4.
        """
        try:
            # Stage 1: Pre-filter (high-shelf filter representing head acoustics)
            # Treble biquad operates as high shelf: gain=1.5dB, frequency=1000Hz, Q=0.707
            pre = torchaudio.functional.treble_biquad(
                waveform=wav,
                sample_rate=self.sample_rate,
                gain=1.5,
                central_freq=1000.0
            )
            # Stage 2: RLB filter (high-pass filter modeling low frequency roll-off)
            k_weighted = torchaudio.functional.highpass_biquad(
                waveform=pre,
                sample_rate=self.sample_rate,
                cutoff_freq=38.0
            )
            # Calculate mean square energy per channel
            mean_squares = torch.mean(k_weighted ** 2, dim=-1)
            # Weighting factors: 1.0 for Left/Right (channels 0 and 1)
            sum_ms = torch.sum(mean_squares)
            
            if sum_ms <= 1e-12:
                return -100.0  # Silent limit threshold
                
            lufs = -0.691 + 10.0 * torch.log10(sum_ms)
            return float(lufs.item())
        except Exception as e:
            # Fallback to simple RMS-based estimation if filtering fails
            logger.warning("calculate_lufs_failed_falling_back_to_rms", error=str(e))
            rms = torch.sqrt(torch.mean(wav ** 2))
            if rms <= 1e-6:
                return -100.0
            return float(20.0 * torch.log10(rms).item())

    def calculate_phase_correlation(self, wav: torch.Tensor) -> float:
        """
        Compute the Pearson correlation coefficient between Left and Right channels.
        Used to monitor stereo widening and ensure mono compatibility.
        """
        if wav.ndim < 2 or wav.shape[0] != 2:
            return 1.0
        try:
            left = wav[0]
            right = wav[1]
            dot_product = torch.dot(left, right)
            norm_l = torch.linalg.vector_norm(left)
            norm_r = torch.linalg.vector_norm(right)
            if norm_l > 1e-8 and norm_r > 1e-8:
                corr = dot_product / (norm_l * norm_r)
                return float(torch.clamp(corr, -1.0, 1.0).item())
            return 1.0
        except Exception as e:
            logger.warning("phase_correlation_calculation_failed_defaulting", error=str(e))
            return 1.0

    def normalize_loudness(self, wav_path: str, output_path: str, target_lufs: float) -> None:
        """
        Normalize a raw audio file to target LUFS perceptual level with a safety True Peak ceiling of -0.5 dB.
        Used to eliminate loudness bias in the control group.
        """
        wav, sr = torchaudio.load(wav_path)
        self.sample_rate = sr
        
        # Calculate current LUFS
        current_lufs = self.calculate_lufs(wav)
        
        # Calculate gain adjustment
        gain_db = target_lufs - current_lufs
        gain_amp = 10.0 ** (gain_db / 20.0)
        
        # Scale audio
        scaled = wav * gain_amp
        
        # Apply True Peak limiting to catch transients exceeding -0.5 dBFS
        target_amp = 10.0 ** (-0.5 / 20.0)
        try:
            oversampling_factor = 4
            upsampled_rate = self.sample_rate * oversampling_factor
            tp_upsampled = torchaudio.functional.resample(scaled, self.sample_rate, upsampled_rate)
            true_peak = torch.max(torch.abs(tp_upsampled))
            
            if true_peak > target_amp:
                correction = target_amp / true_peak
                scaled = scaled * correction
        except Exception as e:
            logger.warning("normalize_loudness_true_peak_failed", error=str(e))
            # Safe sample clamp fallback
            max_val = torch.max(torch.abs(scaled))
            if max_val > target_amp:
                scaled = (scaled / max_val) * target_amp
                
        torchaudio.save(output_path, scaled, sr)

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
            
        try:
            n = wav.shape[-1]
            spec = torch.fft.rfft(wav, dim=-1)
            freqs = torch.fft.rfftfreq(n, d=1.0/self.sample_rate)
            
            low_indices = freqs < 150.0
            high_indices = ~low_indices
            
            # Mid/Side in frequency domain
            mid_spec = (spec[0] + spec[1]) / 2.0
            side_spec = (spec[0] - spec[1]) / 2.0
            
            # Adaptive phase correlation guardrail loop
            current_amount = amount
            widened = wav
            
            for attempt in range(4):
                spec_widened = spec.clone()
                # 1. Mono-sum the low frequency spectrum (bass below 150 Hz)
                spec_widened[0, low_indices] = mid_spec[low_indices]
                spec_widened[1, low_indices] = mid_spec[low_indices]
                
                # 2. Widen the high frequency spectrum
                side_high_widened = side_spec[high_indices] * current_amount
                spec_widened[0, high_indices] = mid_spec[high_indices] + side_high_widened
                spec_widened[1, high_indices] = mid_spec[high_indices] - side_high_widened
                
                # 3. Inverse FFT to get time domain signal
                candidate = torch.fft.irfft(spec_widened, n=n, dim=-1)
                
                # 4. Check phase correlation of the combined signal
                corr = self.calculate_phase_correlation(candidate)
                
                # If correlation is safe, or widening is scaled back to neutral, stop
                if corr >= 0.15 or current_amount <= 1.0:
                    widened = candidate
                    break
                    
                current_amount = 1.0 + (current_amount - 1.0) * 0.5
            else:
                # Fallback: force neutral widening (amount = 1.0) with mono-summed bass
                spec_widened = spec.clone()
                spec_widened[0, low_indices] = mid_spec[low_indices]
                spec_widened[1, low_indices] = mid_spec[low_indices]
                # High band remains unwidened (amount = 1.0)
                widened = torch.fft.irfft(spec_widened, n=n, dim=-1)
                
            return widened
            
        except Exception as e:
            logger.warning("fft_stereo_widening_failed_falling_back", error=str(e))
            # Naive time-domain widening fallback if FFT fails
            mid = (wav[0] + wav[1]) / 2.0
            side = (wav[0] - wav[1]) / 2.0
            side_widened = side * amount
            return torch.stack([mid + side_widened, mid - side_widened])

    def apply_low_cut(self, wav: torch.Tensor) -> torch.Tensor:
        """
        Apply low-cut (high-pass) filter at 30Hz to remove sub-audible room rumble
        and clean up headroom.
        """
        try:
            # High-pass filter via torchaudio functional API
            result = torchaudio.functional.highpass_biquad(
                waveform=wav,
                sample_rate=self.sample_rate,
                cutoff_freq=30.0
            )
            # Guard against NaN from edge-case sample rates
            if torch.isnan(result).any():
                logger.warning("low_cut_produced_nan_falling_back", sr=self.sample_rate)
                return wav
            return result
        except Exception as e:
            logger.warning("low_cut_failed_falling_back", error=str(e))
            return wav

    def apply_high_shelf(self, wav: torch.Tensor, gain_db: float = 2.0) -> torch.Tensor:
        """
        Apply high-shelf filter at 10kHz to add brightness ("air") to the track.
        """
        try:
            # High-shelf filter via torchaudio functional API (treble_biquad)
            result = torchaudio.functional.treble_biquad(
                waveform=wav,
                sample_rate=self.sample_rate,
                gain=gain_db,
                central_freq=10000.0
            )
            if torch.isnan(result).any():
                logger.warning("high_shelf_produced_nan_falling_back", sr=self.sample_rate, gain_db=gain_db)
                return wav
            return result
        except Exception as e:
            logger.warning("high_shelf_failed_falling_back", error=str(e))
            return wav

    def apply_sub_bass(self, wav: torch.Tensor, boost_db: float = 0.0) -> torch.Tensor:
        """
        Apply low-shelf bass boost at 60Hz to enhance sub-bass presence (Sound Designer role).
        """
        if boost_db <= 0.0:
            return wav
        try:
            result = torchaudio.functional.bass_biquad(
                waveform=wav,
                sample_rate=self.sample_rate,
                gain=boost_db,
                central_freq=60.0
            )
            if torch.isnan(result).any():
                logger.warning("sub_bass_produced_nan_falling_back", sr=self.sample_rate, boost_db=boost_db)
                return wav
            return result
        except Exception as e:
            logger.warning("sub_bass_failed_falling_back", error=str(e))
            return wav

    def apply_limiting_and_maximize(self, wav: torch.Tensor, target_db: float = -0.5, drive_db: float = 3.0, target_lufs: Optional[float] = None) -> torch.Tensor:
        """
        Maximize perceived loudness using drive gain and oversampled soft clipping (tanh),
        then apply True Peak limiting to target_db using 4x interpolation peak detection.
        Optionally scales to target_lufs closed-loop perceptual loudness before peak limiting.
        """
        # Convert dB to linear amplitude
        target_amp = 10.0 ** (target_db / 20.0)
        drive_amp = 10.0 ** (drive_db / 20.0)
        
        # 1. Soft Clipping Saturation with 4x Oversampling (Anti-Aliasing)
        oversampling_factor = 4
        try:
            # Upsample
            upsampled_rate = self.sample_rate * oversampling_factor
            upsampled = torchaudio.functional.resample(wav, self.sample_rate, upsampled_rate)
            # Apply drive
            driven = upsampled * drive_amp
            # Soft clip in high sample rate space (harmonics above Nyquist fold inaudibly)
            saturated_upsampled = torch.tanh(driven)
            # Downsample
            saturated = torchaudio.functional.resample(saturated_upsampled, upsampled_rate, self.sample_rate)
        except Exception as e:
            logger.warning("oversampled_clipping_failed_falling_back_to_naive", error=str(e))
            # Naive clipping fallback
            driven = wav * drive_amp
            saturated = torch.tanh(driven)
            
        # 2. Loudness Normalization & Peak Maximization
        if target_lufs is not None:
            # Measure K-weighted integrated LUFS of the saturated signal
            current_lufs = self.calculate_lufs(saturated)
            # Compute required gain to reach target LUFS
            gain_db = target_lufs - current_lufs
            gain_amp = 10.0 ** (gain_db / 20.0)
            mastered = saturated * gain_amp
        else:
            # Fallback to naive peak normalization
            max_val = torch.max(torch.abs(saturated))
            if max_val > 0:
                mastered = (saturated / max_val) * target_amp
            else:
                mastered = saturated
            
        # 3. True Peak Clamping (4x interpolation peak check)
        try:
            upsampled_rate = self.sample_rate * oversampling_factor
            tp_upsampled = torchaudio.functional.resample(mastered, self.sample_rate, upsampled_rate)
            true_peak = torch.max(torch.abs(tp_upsampled))
            
            if true_peak > target_amp:
                # Inter-sample peak clipping would occur on DAC reconstruction.
                # Apply scaling correction to pull True Peak exactly down to target_amp.
                correction = target_amp / true_peak
                mastered = mastered * correction
        except Exception as e:
            logger.warning("true_peak_clamping_failed", error=str(e))
            
        return mastered

    def master_track(
        self, 
        wav_path: str, 
        output_path: str, 
        style: str,
        drive_db: Optional[float] = None,
        high_shelf_db: Optional[float] = None,
        stereo_width: Optional[float] = None,
        limiter_ceiling_db: Optional[float] = None,
        sub_bass_boost_db: Optional[float] = None,
        persona_id: Optional[str] = None
    ) -> None:
        """
        Load audio, execute the multi-role virtual production team mastering pipeline, and save.
        """
        # Load audio
        wav, sr = torchaudio.load(wav_path)
        self.sample_rate = sr
        
        # Calculate input LUFS loudness
        input_lufs = self.calculate_lufs(wav)
        
        # Resolve persona and its constraints
        pid = persona_id or "default_producer"
        constraints = PERSONA_CONSTRAINTS.get(pid, PERSONA_CONSTRAINTS["default_producer"])
        
        # 1. Sound Designer / Assistant: low cut & optional sub-bass boost
        wav = self.apply_low_cut(wav)
        
        if constraints["enable_sub_bass"]:
            sub_boost = sub_bass_boost_db if sub_bass_boost_db is not None else 0.0
            wav = self.apply_sub_bass(wav, boost_db=sub_boost)
            
        # 2. Mixing Engineer: brightness EQ & saturation drive (respecting Lead constraints)
        shelf_gain = high_shelf_db
        if shelf_gain is None:
            if style in ("lofi", "ambient"):
                shelf_gain = 1.0
            else:
                shelf_gain = 2.5
        wav = self.apply_high_shelf(wav, gain_db=shelf_gain)
        
        drive = drive_db if drive_db is not None else (4.0 if style in ("trap", "house", "techno", "dnb", "reggaeton") else 2.0)
        clamped_drive = max(constraints["min_drive_db"], min(constraints["max_drive_db"], drive))
        
        # 3. Mastering Engineer: widening & limiter ceiling (respecting Lead constraints)
        width = stereo_width if stereo_width is not None else 1.25
        clamped_width = max(constraints["min_stereo_width"], min(constraints["max_stereo_width"], width))
        if wav.shape[0] == 2:
            wav = self.apply_stereo_widening(wav, amount=clamped_width)
        ceiling = limiter_ceiling_db if limiter_ceiling_db is not None else -0.5
        target_lufs = self.STYLE_TARGET_LUFS.get(style, self.DEFAULT_TARGET_LUFS)
        wav = self.apply_limiting_and_maximize(wav, target_db=ceiling, drive_db=clamped_drive, target_lufs=target_lufs)
        
        # Calculate output LUFS loudness
        output_lufs = self.calculate_lufs(wav)
        logger.info(
            "mastering_loudness_report",
            input_lufs=input_lufs,
            output_lufs=output_lufs,
            style=style,
            persona_id=pid
        )
        
        # Save output
        torchaudio.save(output_path, wav, sr)
