import pytest
import os
import shutil
import torch
import torchaudio
from unittest.mock import MagicMock, patch
from producer import AudioProducer

# Override conftest autouse database fixture to run offline unit tests
@pytest.fixture(scope="session", autouse=True)
def _setup_test_schema():
    pass

def test_apply_stereo_widening():
    producer = AudioProducer(sample_rate=16000)
    
    # 1. Mono audio input should return unchanged
    mono = torch.ones(1, 1000)
    widened_mono = producer.apply_stereo_widening(mono)
    assert torch.equal(mono, widened_mono)
    
    # 2. Stereo audio input should be widened
    # Use a high-frequency sine wave (e.g. 1000 Hz) fully panned Left to ensure it falls above 150 Hz crossover
    t = torch.arange(1000) / 16000
    left = torch.sin(2 * 3.14159 * 1000 * t)
    right = torch.zeros_like(left)
    stereo = torch.stack([left, right])
    widened_stereo = producer.apply_stereo_widening(stereo, amount=1.5)
    
    assert widened_stereo.shape == (2, 1000)
    # The difference between channels in widened stereo should be larger than original
    orig_diff = torch.abs(stereo[0] - stereo[1]).mean()
    widened_diff = torch.abs(widened_stereo[0] - widened_stereo[1]).mean()
    assert widened_diff > orig_diff

def test_apply_low_cut():
    producer = AudioProducer(sample_rate=16000)
    wav = torch.randn(2, 16000) # 1 second of random noise
    
    processed = producer.apply_low_cut(wav)
    assert processed.shape == wav.shape
    # Not identical because filtering took place
    assert not torch.equal(processed, wav)

def test_apply_high_shelf():
    producer = AudioProducer(sample_rate=44100)
    wav = torch.randn(2, 44100)
    
    processed = producer.apply_high_shelf(wav, gain_db=3.0)
    assert processed.shape == wav.shape
    assert not torch.equal(processed, wav)

def test_apply_limiting_and_maximize():
    producer = AudioProducer(sample_rate=16000)
    
    # Signal exceeding normal bounds
    wav = torch.randn(2, 1000) * 10.0
    
    target_db = -0.5
    target_amp = 10.0 ** (target_db / 20.0)
    
    processed = producer.apply_limiting_and_maximize(wav, target_db=target_db, drive_db=2.0)
    
    assert processed.shape == wav.shape
    # Check that peaks are constrained within the limit ceiling
    assert torch.max(torch.abs(processed)) <= target_amp + 1e-4

@patch("torchaudio.load")
@patch("torchaudio.save")
def test_master_track(mock_save, mock_load):
    # Mock torchaudio to return dummy stereo tensor
    mock_load.return_value = (torch.randn(2, 32000), 32000)
    
    producer = AudioProducer()
    producer.master_track("input.mp3", "output.mp3", "trap")
    
    assert mock_load.called
    assert mock_save.called
    
    # Verify mock save args
    args, kwargs = mock_save.call_args
    assert args[0] == "output.mp3"
    assert args[1].shape[0] == 2 # Stereo output
    assert args[2] == 32000 # Sample rate

@patch("requests.get")
@patch("producer.AudioProducer.master_track")
@patch("c2pa_embedder.C2PAEmbedder.embed_mp3")
@patch("c2pa_embedder.C2PAEmbedder.embed_waveform_watermark")
def test_download_generation_endpoint(mock_embed_wm, mock_embed_mp3, mock_master, mock_get):
    from fastapi.testclient import TestClient
    from main import app
    from clerk_auth import get_current_user
    from api_v2 import get_db
    
    # Define side effect to write dummy file so copy and FileResponse work
    def side_effect_master(wav_path, output_path, style, **kwargs):
        with open(output_path, "wb") as f:
            f.write(b"mastered audio data")
    mock_master.side_effect = side_effect_master

    # 1. Mock DB connection and cursor
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value = mock_cur
    
    # DB select output for generation row
    mock_cur.fetchone.return_value = {
        "audio_url": "https://replicate.delivery/some_track.mp3",
        "prompt": "happy beat",
        "style": "house",
        "user_id": "user_test_id",
        "watermark_id": 123
    }
    
    # Yield mock db connection
    def mock_get_db():
        yield mock_conn
        
    # Override dependencies
    app.dependency_overrides[get_current_user] = lambda: {"id": "user_test_id", "user_id": "user_test_id"}
    app.dependency_overrides[get_db] = mock_get_db
    
    # 2. Mock requests.get response
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = b"dummy mp3 data"
    mock_get.return_value = mock_resp
    
    client = TestClient(app)
    
    generation_id = "gen_test123"
    cache_path = f"/tmp/remixa_cache/{generation_id}_treatment.mp3"
    
    # Clean cache if exists before test
    if os.path.exists(cache_path):
        os.remove(cache_path)
        
    try:
        # First request (should download, process, cache, and serve)
        resp = client.get(f"/api/v2/generations/{generation_id}/download")
        assert resp.status_code == 200
        assert mock_get.called
        assert mock_master.called
        assert mock_embed_mp3.called
        assert mock_embed_wm.called
        
        # Reset call counts
        mock_get.reset_mock()
        mock_master.reset_mock()
        
        # Second request (should serve directly from cache path without downloading or processing)
        with patch("os.path.exists", return_value=True):
            resp2 = client.get(f"/api/v2/generations/{generation_id}/download")
            assert resp2.status_code == 200
            assert not mock_get.called
            assert not mock_master.called
    finally:
        app.dependency_overrides.clear()
        if os.path.exists(cache_path):
            os.remove(cache_path)

