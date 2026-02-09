# F:/projek dosen/prototype riset/hotspotAnalyzer/main.py
"""
TELPLASTINA - Telkom Enhanced Planar Scintigraphy Analysis
AI-powered bone scan metastasis detection and analysis platform

Developed by:
- Telkom University (AI/ML Technology)
- Universitas Padjadjaran (Medical Expertise)
"""
import multiprocessing
import sys
import os
from pathlib import Path
import logging
#   NEW: Ensure assets directory is accessible
def setup_assets_path():
    """Setup assets path for icon loading"""
    try:
        if hasattr(sys, '_MEIPASS'):
            # PyInstaller bundle
            assets_path = Path(sys._MEIPASS) / "assets"
        else:
            # Development mode
            assets_path = Path(__file__).parent / "assets"
        
        if assets_path.exists():
            logging.info(f"[ASSETS] Assets path: {assets_path}")
        else:
            logging.info(f"[ASSETS] Assets path not found: {assets_path}")
            
    except Exception as e:
        logging.info(f"[ASSETS] Error setting up assets path: {e}")

if __name__ == "__main__":
    # CRITICAL: freeze_support() must be called BEFORE importing the main app logic
    # to prevent recursive process spawning loop on Windows.
    multiprocessing.freeze_support()
    
    setup_assets_path()
    
    # Import main only after freeze_support
    from app.__main__ import main
    main()