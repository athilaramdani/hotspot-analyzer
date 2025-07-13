# backend/processing_wrapper.py

from pathlib import Path
from typing import Dict

# Pastikan path import ini benar sesuai struktur proyek Anda
from .hotspot_processor import HotspotProcessor
from .image_converter import load_frames_and_metadata_matrix

# --- Pastikan definisi fungsi ini menerima DUA argumen: scan_path dan patient_id ---
def run_hotspot_processing_in_process(scan_path: Path, patient_id: str) -> Dict | None:
    """
    Fungsi ini dijalankan di proses terpisah untuk isolasi total.
    """
    try:
        # 1. Inisialisasi prosesor HANYA di dalam proses ini
        print(f"[PROCESS-{patient_id}] Inisialisasi HotspotProcessor...")
        processor = HotspotProcessor()

        # 2. Lakukan pekerjaan backend
        print(f"[PROCESS-{patient_id}] Memuat data matriks dari {scan_path.name}...")
        frame_bb, _ = load_frames_and_metadata_matrix(scan_path)
        
        # Anda mungkin perlu menyesuaikan pemanggilan di bawah ini dengan metode asli di HotspotProcessor.
        # Saya asumsikan ada metode bernama `process_dual_view`.
        print(f"[PROCESS-{patient_id}] Memulai pemrosesan hotspot...")
        hotspot_data = processor.process_dual_view(frame_bb, scan_path, patient_id)
        
        # 3. Bersihkan sumber daya prosesor jika ada
        if hasattr(processor, 'cleanup'):
            processor.cleanup()

        print(f"[PROCESS-{patient_id}] Pemrosesan selesai.")
        # 4. Kembalikan hasilnya
        return hotspot_data

    except Exception as e:
        # Cetak error yang terjadi di dalam proses worker
        import traceback
        print(f"[FATAL IN PROCESS-{patient_id}] Gagal memproses {scan_path.name}: {e}")
        traceback.print_exc()
        return None