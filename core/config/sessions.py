# core/config/sessions.py
"""
Session management configuration untuk Hotspot Analyzer
"""
from typing import Dict, List, Optional
from pathlib import Path
from datetime import datetime
import json

# Available patient session codes
AVAILABLE_SESSION_CODES = [
    "NSY",  
    "ATL",  
    "NBL",  
]

# Available modalities
AVAILABLE_MODALITIES = [
    "SPECT",
    "PET"
]

# Session code descriptions (optional)
SESSION_CODE_DESCRIPTIONS = {
    "NSY": "Neurological Surgery Department",
    "ATL": "Atlantic Medical Center", 
    "NBL": "Neurobiology Laboratory",
}

# Default session settings
DEFAULT_SESSION_CONFIG = {
    "auto_login": False,
    "remember_last_session": True,
    "default_modality": "SPECT",
    "session_timeout_minutes": 60,
    "max_concurrent_sessions": 3
}

class SessionManager:
    """Manages user sessions and login state"""
    
    def __init__(self, config_dir: Path = None):
        self.config_dir = config_dir or Path("config")
        self.config_file = self.config_dir / "sessions.json"
        self.current_session: Optional[Dict] = None
        self._load_config()
    
    def _load_config(self):
        """Load session configuration from file"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    self.config = json.load(f)
            else:
                self.config = DEFAULT_SESSION_CONFIG.copy()
                self._save_config()
        except Exception as e:
            print(f"[WARNING] Failed to load session config: {e}")
            self.config = DEFAULT_SESSION_CONFIG.copy()
    
    def _save_config(self):
        """Save session configuration to file"""
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            print(f"[WARNING] Failed to save session config: {e}")
    
    def get_available_session_codes(self) -> List[str]:
        """Get list of available session codes"""
        return AVAILABLE_SESSION_CODES.copy()
    
    def get_available_modalities(self) -> List[str]:
        """Get list of available modalities"""
        return AVAILABLE_MODALITIES.copy()
    
    def get_session_description(self, session_code: str) -> str:
        """Get description for session code"""
        return SESSION_CODE_DESCRIPTIONS.get(session_code, f"Session {session_code}")
    
    def validate_session_code(self, session_code: str) -> bool:
        """Validate if session code is available"""
        return session_code in AVAILABLE_SESSION_CODES
    
    def validate_modality(self, modality: str) -> bool:
        """Validate if modality is available"""
        return modality in AVAILABLE_MODALITIES
    
    def create_session(self, session_code: str, modality: str, user_data: Dict = None) -> Dict:
        """Create a new session"""
        if not self.validate_session_code(session_code):
            raise ValueError(f"Invalid session code: {session_code}")
        
        if not self.validate_modality(modality):
            raise ValueError(f"Invalid modality: {modality}")
        
        session = {
            "session_id": f"{session_code}_{modality}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "session_code": session_code,
            "modality": modality,
            "start_time": datetime.now().isoformat(),
            "user_data": user_data or {},
            "is_active": True
        }
        
        self.current_session = session
        
        # Save last session if enabled
        if self.config.get("remember_last_session", True):
            self.config["last_session"] = {
                "session_code": session_code,
                "modality": modality
            }
            self._save_config()
        
        print(f"[SESSION] Created session: {session['session_id']}")
        return session
    
    def get_current_session(self) -> Optional[Dict]:
        """Get current active session"""
        return self.current_session
    
    def get_last_session(self) -> Optional[Dict]:
        """Get last used session info"""
        return self.config.get("last_session")
    
    def end_session(self):
        """End current session"""
        if self.current_session:
            self.current_session["end_time"] = datetime.now().isoformat()
            self.current_session["is_active"] = False
            print(f"[SESSION] Ended session: {self.current_session['session_id']}")
            self.current_session = None
    
    def get_session_config(self, key: str, default=None):
        """Get session configuration value"""
        return self.config.get(key, default)
    
    def set_session_config(self, key: str, value):
        """Set session configuration value"""
        self.config[key] = value
        self._save_config()

# Global session manager instance
_session_manager = None

def get_session_manager() -> SessionManager:
    """Get global session manager instance"""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager

# Convenience functions
def get_available_session_codes() -> List[str]:
    """Get available session codes"""
    return get_session_manager().get_available_session_codes()

def get_available_modalities() -> List[str]:
    """Get available modalities"""
    return get_session_manager().get_available_modalities()

def validate_session_code(session_code: str) -> bool:
    """Validate session code"""
    return get_session_manager().validate_session_code(session_code)

def validate_modality(modality: str) -> bool:
    """Validate modality"""
    return get_session_manager().validate_modality(modality)

def create_session(session_code: str, modality: str, user_data: Dict = None) -> Dict:
    """Create new session"""
    return get_session_manager().create_session(session_code, modality, user_data)

def get_current_session() -> Optional[Dict]:
    """Get current session"""
    return get_session_manager().get_current_session()

def end_session():
    """End current session"""
    get_session_manager().end_session()

def get_session_description(session_code: str) -> str:
    """Get session description"""
    return get_session_manager().get_session_description(session_code)