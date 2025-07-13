# Di file backend, misal: backend/processing_wrapper.py

from pathlib import Path
from typing import List, Dict
# Import yang diperlukan oleh HotspotProcessor di sini
from .hotspot_processor import HotspotProcessor

def run_hotspot_processing_in_process(frames: List, scan_path: Path, patient_id: str) -> Dict:
    """
    Fungsi ini akan dijalankan dalam proses terpisah.
    """
    # Inisialisasi prosesor HANYA di dalam proses ini
    processor = HotspotProcessor()

    # Lakukan pemrosesan
    # (Salin logika dari _process_hotspot_frames_dual_view di sini)
    # Contoh sederhana:
    result = processor.process_image_with_xml(...) # Panggil fungsi asli Anda

    # Bersihkan direktori temporary jika perlu
    processor.cleanup()

    # Kembalikan hasilnya (harus bisa di-"pickle")
    return result