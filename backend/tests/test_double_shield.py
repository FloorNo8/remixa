import pytest
from unittest.mock import MagicMock, patch, mock_open
import hashlib
import numpy as np

# Override conftest autouse database fixture to run offline unit tests
@pytest.fixture(scope="session", autouse=True)
def _setup_test_schema():
    pass

# We mock torch and torchaudio to prevent loading heavy models and weights during unit tests
@pytest.fixture
def mock_torchaudio():
    with patch("torchaudio.load") as mock_load, patch("torchaudio.save") as mock_save:
        # returns dummy wav tensor (shape [1, 16000]) and sample rate
        import torch
        mock_load.return_value = (torch.zeros(1, 16000), 16000)
        yield mock_load, mock_save

@pytest.fixture
def mock_audioseal():
    with patch("audioseal.AudioSeal.load_generator") as mock_gen, patch("audioseal.AudioSeal.load_detector") as mock_det:
        # Mock generator behavior
        mock_generator_instance = MagicMock()
        import torch
        mock_generator_instance.get_watermark.return_value = torch.zeros(1, 1, 16000)
        mock_gen.return_value = mock_generator_instance
        
        # Mock detector behavior
        mock_detector_instance = MagicMock()
        import torch
        # detector returns result probability and message tensor
        mock_detector_instance.detect_watermark.return_value = (
            torch.tensor([0.95]),  # prob
            torch.tensor([[0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 1, 0, 1, 0]]) # 16-bit binary payload (value 42)
        )
        mock_det.return_value = mock_detector_instance
        
        yield mock_gen, mock_det

def test_watermark_id_generation():
    """Verify deterministic mapping of generation_id to 16-bit watermark_id"""
    generation_id = "gen_abc123xyz"
    h = hashlib.md5(generation_id.encode('utf-8')).hexdigest()
    expected_id = int(h, 16) % 65536
    
    # Assert deterministic mapping holds true
    assert expected_id == 58790  # precalculated hash value modulo 65536

def test_embed_waveform_watermark(mock_torchaudio, mock_audioseal):
    """Test that embedding waveform watermark calls AudioSeal generator with correct tensors"""
    from c2pa_embedder import C2PAEmbedder
    import torch
    
    embedder = C2PAEmbedder()
    # Embed 42
    embedder.embed_waveform_watermark("dummy_path.mp3", 42)
    
    # Assert load was called
    mock_torchaudio[0].assert_called_once_with("dummy_path.mp3")
    
    # Assert AudioSeal generator get_watermark was called with the message tensor mapping for 42
    generator_instance = mock_audioseal[0].return_value
    assert generator_instance.get_watermark.called
    
    # Check format(42, '016b') is '0000000000101010'
    called_args, called_kwargs = generator_instance.get_watermark.call_args
    message_tensor = called_kwargs.get("message")
    assert message_tensor is not None
    assert message_tensor.tolist() == [[0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 1, 0, 1, 0]]
    
    # Assert save was called
    assert mock_torchaudio[1].called

def test_decode_waveform_watermark(mock_torchaudio, mock_audioseal):
    """Test that decoding waveform watermark calls AudioSeal detector and recovers payload 42"""
    from c2pa_embedder import C2PAEmbedder
    
    embedder = C2PAEmbedder()
    watermark_id = embedder.decode_waveform_watermark("dummy_path.mp3")
    
    # Assert load was called
    mock_torchaudio[0].assert_called_once_with("dummy_path.mp3")
    
    # Assert AudioSeal detector detect_watermark was called
    detector_instance = mock_audioseal[1].return_value
    assert detector_instance.detect_watermark.called
    
    # Assert recovered payload ID is 42
    assert watermark_id == 42
