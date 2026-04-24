"""
TTS Engine Interface

This module defines the interface that plugin TTS engines must implement
to integrate with the application's TTS system.
"""

from dataclasses import dataclass
from typing import List, Dict, Any
from abc import ABC, abstractmethod


@dataclass
class VoiceInfo:
    """
    Information about a TTS voice/speaker
    """
    voice_id: str           # Unique identifier for the voice
    voice_name: str         # Display name for the voice
    language: str           # Language code (e.g., "zh-CN", "en-US")
    gender: str = ""        # Voice gender (optional)
    
    def __post_init__(self):
        """Validate voice info after initialization"""
        if not self.voice_id or not self.voice_name or not self.language:
            raise ValueError("voice_id, voice_name, and language are required")


@dataclass
class EngineInfo:
    """
    Information about a TTS engine
    """
    engine_id: str          # Unique identifier for the engine
    engine_name: str        # Display name for the engine
    version: str            # Engine version
    provider: str           # Engine provider/company
    
    def __post_init__(self):
        """Validate engine info after initialization"""
        if not self.engine_id or not self.engine_name:
            raise ValueError("engine_id and engine_name are required")


class TTSEngineInterface(ABC):
    """
    Abstract base class for TTS engines
    
    Plugin TTS engines must inherit from this class and implement
    all abstract methods to integrate with the application.
    """
    
    @abstractmethod
    def synthesize(self, text: str, voice: str, **kwargs) -> str:
        """
        Synthesize text to speech
        
        Args:
            text: Text to synthesize
            voice: Voice ID to use for synthesis
            **kwargs: Additional parameters (speed, pitch, volume, etc.)
            
        Returns:
            Path to the generated audio file
            
        Raises:
            TTSEngineError: If synthesis fails
        """
        pass
        
    @abstractmethod
    def get_voices(self) -> List[VoiceInfo]:
        """
        Get list of available voices for this engine
        
        Returns:
            List of VoiceInfo objects describing available voices
            
        Raises:
            TTSEngineError: If voice list cannot be retrieved
        """
        pass
        
    @abstractmethod
    def get_engine_info(self) -> EngineInfo:
        """
        Get information about this TTS engine
        
        Returns:
            EngineInfo object describing this engine
        """
        pass
        
    def validate_voice(self, voice_id: str) -> bool:
        """
        Validate that a voice ID is supported by this engine
        
        Args:
            voice_id: Voice ID to validate
            
        Returns:
            True if voice is supported, False otherwise
        """
        try:
            voices = self.get_voices()
            return any(voice.voice_id == voice_id for voice in voices)
        except Exception:
            return False
            
    def get_supported_parameters(self) -> Dict[str, Any]:
        """
        Get supported synthesis parameters for this engine
        
        Returns:
            Dictionary describing supported parameters and their types/ranges
        """
        # Default implementation - engines can override
        return {
            "speed": {"type": "float", "min": 0.5, "max": 2.0, "default": 1.0},
            "pitch": {"type": "float", "min": 0.5, "max": 2.0, "default": 1.0},
            "volume": {"type": "float", "min": 0.0, "max": 1.0, "default": 1.0}
        }


class TTSEngineError(Exception):
    """Exception raised by TTS engines"""
    pass