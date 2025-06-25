import argparse
import pydicom
from pathlib import Path

def rename_files_to_dcm(target_folder: Path, dry_run: bool = True):
    """
    Secara rekursif mencari file di dalam direktori target, memverifikasi apakah
    file tersebut adalah file DICOM, dan mengubah namanya dengan menambahkan ekstensi .dcm.

    Args:
        target_folder (Path): Path ke folder yang akan dipindai.
        dry_run (bool): Jika True, hanya akan mensimulasikan dan mencetak aksi.
                        Jika False, akan benar-benar mengubah nama file.
    """
    if not target_folder.is_dir():
        print(f"Error: Folder tidak ditemukan di '{target_folder}'")
        return

    print("="*50)
    print(f"Memindai folder: {target_folder}")
    if dry_run:
        print("MODE: Simulasi (Dry Run). Tidak ada file yang akan diubah.")
    else:
        print("MODE: Eksekusi Nyata. File akan diubah namanya.")
    print("="*50)

    # Menggunakan rglob('*') untuk mencari semua file secara rekursif
    files_to_check = list(target_folder.rglob('*'))
    renamed_count = 0
    skipped_count = 0

    for file_path in files_to_check:
        # 1. Abaikan jika ini adalah direktori atau sudah memiliki ekstensi .dcm
        if not file_path.is_file() or file_path.suffix.lower() == '.dcm':
            continue

        # 2. Verifikasi apakah ini benar-benar file DICOM
        try:
            # Coba baca header file. Jika berhasil, ini adalah file DICOM.
            # stop_before_pixels=True membuatnya sangat cepat karena tidak membaca data gambar.
            pydicom.dcmread(file_path, stop_before_pixels=True)
            is_dicom = True
        except pydicom.errors.InvalidDicomError:
            # Jika gagal, ini bukan file DICOM, jadi abaikan.
            is_dicom = False
        
        if not is_dicom:
            # print(f"Info: Mengabaikan file non-DICOM -> {file_path.name}")
            continue

        # 3. Jika ini adalah file DICOM tanpa ekstensi, ubah namanya.
        new_file_path = file_path.with_suffix('.dcm')

        if new_file_path.exists():
            print(f"Peringatan: Melewati '{file_path.name}' karena file '{new_file_path.name}' sudah ada.")
            skipped_count += 1
            continue
            
        print(f"Ditemukan DICOM tanpa ekstensi: '{file_path.name}'")
        
        if dry_run:
            print(f"  -> [SIMULASI] AKAN DIUBAH MENJADI: '{new_file_path.name}'")
        else:
            try:
                file_path.rename(new_file_path)
                print(f"  -> [BERHASIL] DIUBAH MENJADI: '{new_file_path.name}'")
            except Exception as e:
                print(f"  -> [GAGAL] Tidak dapat mengubah nama file: {e}")
                skipped_count += 1
                continue

        renamed_count += 1

    print("\n" + "="*50)
    print("Proses Selesai.")
    print(f"Total file berhasil diubah namanya: {renamed_count}")
    if skipped_count > 0:
        print(f"Total file dilewati (sudah ada/gagal): {skipped_count}")
    print("="*50)


if __name__ == "__main__":
    # Membuat parser untuk argumen command-line
    parser = argparse.ArgumentParser(
        description="Ubah nama file DICOM tanpa ekstensi menjadi .dcm secara rekursif.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "target_folder",
        type=str,
        help="Path lengkap ke folder yang ingin Anda pindai.\nContoh: \"C:\\Users\\Anda\\Desktop\\DataDICOM\""
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Jalankan dalam mode simulasi. Hanya akan menampilkan file yang akan diubah tanpa mengubahnya."
    )

    args = parser.parse_args()

    # Ubah string path menjadi objek Path
    folder_path = Path(args.target_folder)
    
    rename_files_to_dcm(folder_path, dry_run=args.dry_run)