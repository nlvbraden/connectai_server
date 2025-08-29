"""Audio processing for NetSapiens WebSocket streams."""

import logging
import base64
import numpy as np
from scipy.signal import resample_poly

logger = logging.getLogger(__name__)

# G.711 μ-law constants
ULAW_BIAS = 132
ULAW_CLIP = 32635
ULAW_MAX = 0x1FFF


def linear_to_ulaw(sample):
    """Convert a linear PCM sample to μ-law."""
    # Get the sign and absolute value
    sign = (sample >> 8) & 0x80
    if sign != 0:
        sample = -sample
    if sample > ULAW_CLIP:
        sample = ULAW_CLIP
    
    # Add bias
    sample = sample + ULAW_BIAS
    
    # Find exponent and mantissa
    exponent = 7
    mask = 0x4000
    while (sample & mask) == 0 and exponent > 0:
        exponent -= 1
        mask >>= 1
    
    mantissa = (sample >> (exponent + 3)) & 0x0F
    ulawbyte = ~(sign | (exponent << 4) | mantissa)
    
    return ulawbyte & 0xFF


def ulaw_to_linear(ulawbyte):
    """Convert a μ-law byte to linear PCM."""
    ulawbyte = ~ulawbyte
    sign = (ulawbyte & 0x80)
    exponent = (ulawbyte >> 4) & 0x07
    mantissa = ulawbyte & 0x0F
    sample = ((mantissa << 3) + ULAW_BIAS) << exponent
    sample = sample - ULAW_BIAS
    if sign != 0:
        sample = -sample
    return sample


# Pre-compute lookup tables for performance
ULAW_DECODE_TABLE = np.array([ulaw_to_linear(i) for i in range(256)], dtype=np.int16)
ULAW_ENCODE_DICT = {linear_to_ulaw(i - 32768): i - 32768 for i in range(65536)}


class AudioProcessor:
    """Handles audio processing for NetSapiens streams."""
    
    def __init__(self):
        # Sample rates
        self.netsapiens_rate = 8000  # NetSapiens: 8kHz μ-law
        self.gemini_input_rate = 16000  # Gemini input: 16kHz PCM
        self.gemini_output_rate = 24000  # Gemini output: 24kHz PCM
    
    async def process_incoming_audio(self, audio_payload: str) -> bytes:
        """Process incoming audio from NetSapiens for Gemini.
        
        Converts from base64-encoded 8kHz μ-law to 16kHz PCM.
        """
        try:
            # Decode base64
            if not audio_payload or not audio_payload.strip():
                return b""
            
            ulaw_bytes = base64.b64decode(audio_payload.strip())
            
            # Convert μ-law to PCM using lookup table
            pcm_samples = ULAW_DECODE_TABLE[np.frombuffer(ulaw_bytes, dtype=np.uint8)]
            
            # Resample from 8kHz to 16kHz using polyphase resampling (2x upsampling)
            resampled = resample_poly(pcm_samples, 2, 1)
            
            # Convert to bytes
            return resampled.astype(np.int16).tobytes()
            
        except Exception as e:
            logger.error(f"Error processing incoming audio: {str(e)}")
            return b""
    
    async def process_outgoing_audio(self, audio_data: bytes) -> str:
        """Process outgoing audio from Gemini for NetSapiens.
        
        Converts from 24kHz PCM to base64-encoded 8kHz μ-law.
        """
        try:
            # Convert bytes to numpy array
            pcm_samples = np.frombuffer(audio_data, dtype=np.int16)
            
            # Resample from 24kHz to 8kHz (1:3 downsampling)
            resampled = resample_poly(pcm_samples, 1, 3)
            
            # Ensure samples are in range
            resampled = np.clip(resampled, -32768, 32767).astype(np.int16)
            
            # Convert to μ-law using vectorized operation
            ulaw_bytes = np.array([linear_to_ulaw(sample) for sample in resampled], dtype=np.uint8)
            
            # Encode to base64
            return base64.b64encode(ulaw_bytes).decode('utf-8')
            
        except Exception as e:
            logger.error(f"Error processing outgoing audio: {str(e)}")
            return ""