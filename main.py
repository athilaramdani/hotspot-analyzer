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

# ✅ NEW: Ensure assets directory is accessible
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
            print(f"[ASSETS] Assets path: {assets_path}")
        else:
            print(f"[ASSETS] Assets path not found: {assets_path}")
            
    except Exception as e:
        print(f"[ASSETS] Error setting up assets path: {e}")

from app.__main__ import main

if __name__ == "__main__":
    setup_assets_path()
    multiprocessing.freeze_support()
    main()