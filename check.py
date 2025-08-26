#!/usr/bin/env python3
"""
Script untuk menghitung jumlah file .pyd dan .dll secara rekursif
"""

import os
from pathlib import Path
from collections import defaultdict
import sys

def count_files_recursive(directory_path, extensions=['.pyd', '.dll']):
    """
    Menghitung file dengan ekstensi tertentu secara rekursif
    
    Args:
        directory_path (str): Path ke direktori yang akan dicari
        extensions (list): List ekstensi file yang dicari
    
    Returns:
        dict: Dictionary berisi hasil counting
    """
    directory = Path(directory_path)
    
    if not directory.exists():
        print(f"❌ Direktori tidak ditemukan: {directory_path}")
        return None
    
    if not directory.is_dir():
        print(f"❌ Path bukan direktori: {directory_path}")
        return None
    
    # Counter untuk menyimpan hasil
    results = {
        'files': defaultdict(list),  # Menyimpan path file
        'counts': defaultdict(int),  # Menyimpan jumlah
        'sizes': defaultdict(int),   # Menyimpan total ukuran
        'total_files': 0,
        'total_size': 0
    }
    
    print(f"🔍 Mencari file {', '.join(extensions)} di: {directory_path}")
    print("=" * 60)
    
    try:
        # Scan semua file secara rekursif
        for ext in extensions:
            pattern = f"**/*{ext}"
            files = list(directory.glob(pattern))
            
            for file_path in files:
                try:
                    file_size = file_path.stat().st_size
                    results['files'][ext].append(str(file_path))
                    results['counts'][ext] += 1
                    results['sizes'][ext] += file_size
                    results['total_files'] += 1
                    results['total_size'] += file_size
                    
                    # Print setiap file yang ditemukan
                    size_mb = file_size / (1024 * 1024)
                    print(f"  {ext}: {file_path.name} ({size_mb:.2f} MB)")
                    
                except (OSError, PermissionError) as e:
                    print(f"  ⚠️  Error accessing {file_path}: {e}")
                    continue
    
    except Exception as e:
        print(f"❌ Error during scan: {e}")
        return None
    
    return results

def print_summary(results):
    """Print ringkasan hasil"""
    if not results:
        return
    
    print("\n" + "=" * 60)
    print("📊 RINGKASAN HASIL")
    print("=" * 60)
    
    for ext in results['counts'].keys():
        count = results['counts'][ext]
        size_mb = results['sizes'][ext] / (1024 * 1024)
        print(f"Ekstensi {ext}:")
        print(f"  📁 Jumlah file: {count}")
        print(f"  💾 Total ukuran: {size_mb:.2f} MB")
        print()
    
    total_size_mb = results['total_size'] / (1024 * 1024)
    print(f"🎯 TOTAL:")
    print(f"  📁 Total semua file: {results['total_files']}")
    print(f"  💾 Total ukuran: {total_size_mb:.2f} MB")

def save_to_file(results, output_file="file_count_result.txt"):
    """Simpan hasil ke file teks"""
    if not results:
        return
    
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("File Counter Results\n")
            f.write("=" * 50 + "\n\n")
            
            for ext in results['files'].keys():
                f.write(f"Files with extension {ext}:\n")
                f.write("-" * 30 + "\n")
                
                for file_path in results['files'][ext]:
                    f.write(f"  {file_path}\n")
                
                count = results['counts'][ext]
                size_mb = results['sizes'][ext] / (1024 * 1024)
                f.write(f"\nCount: {count} files\n")
                f.write(f"Total size: {size_mb:.2f} MB\n\n")
            
            total_size_mb = results['total_size'] / (1024 * 1024)
            f.write(f"TOTAL: {results['total_files']} files, {total_size_mb:.2f} MB\n")
        
        print(f"📄 Hasil disimpan ke: {output_file}")
        
    except Exception as e:
        print(f"❌ Error saving to file: {e}")

def main():
    """Main function"""
    # Default ke direktori saat ini jika tidak ada argument
    if len(sys.argv) > 1:
        target_directory = sys.argv[1]
    else:
        target_directory = input("Masukkan path direktori (tekan Enter untuk direktori saat ini): ").strip()
        if not target_directory:
            target_directory = "."
    
    # Ekstensi yang dicari
    extensions = ['.pyd', '.dll']
    
    # Hitung file
    results = count_files_recursive(target_directory, extensions)
    
    if results:
        # Tampilkan ringkasan
        print_summary(results)
        
        # Tanya apakah ingin simpan ke file
        save_choice = input("\n💾 Simpan hasil ke file? (y/n): ").strip().lower()
        if save_choice in ['y', 'yes']:
            output_filename = input("Nama file output (default: file_count_result.txt): ").strip()
            if not output_filename:
                output_filename = "file_count_result.txt"
            save_to_file(results, output_filename)

if __name__ == "__main__":
    main()