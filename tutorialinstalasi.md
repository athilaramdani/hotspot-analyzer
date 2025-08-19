# 🚀 Panduan Build HotspotAnalyzer dengan PyInstaller

## 📋 Persiapan

### 1. Install PyInstaller
```bash
pip install pyinstaller
```

### 2. Pastikan Requirements Terinstall
```bash
pip install -r requirements.txt
```

pyinstaller hotspot_analyzer.spec --clean --noconfirm

### 3. Struktur Project
Pastikan struktur project Anda seperti ini:
```
project_root/
├── main.py
├── requirements.txt
├── hotspot_analyzer.spec    # File spec yang disediakan
├── build.py                 # Script build yang disediakan
├── .env
├── config/
│   ├── doctor_tags.json
│   └── sessions.json
├── assets/
├── models/
├── core/
├── features/
└── data/
```

## 🔧 Langkah-langkah Build

### Metode 1: Menggunakan Build Script (Recommended)

1. **Copy file artifacts yang disediakan:**
   - `hotspot_analyzer.spec`
   - `build.py`

2. **Jalankan build script:**
   ```bash
   python build.py
   ```

3. **Hasil build akan ada di:**
   ```
   dist/hotspotAnalyzer/
   ├── hotspotAnalyzer.exe
   ├── config/
   ├── data/
   ├── assets/
   ├── models/
   ├── logs/
   ├── temp/
   └── run_hotspot_analyzer.bat
   ```

### Metode 2: Manual PyInstaller

1. **Menggunakan spec file:**
   ```bash
   pyinstaller hotspot_analyzer.spec
   ```

2. **Atau command manual (tanpa spec):**
   ```bash
   pyinstaller --onedir ^
   --add-data "config;config" ^
   --add-data "assets;assets" ^
   --add-data "models;models" ^
   --add-data "segmentation;segmentation" ^
   --add-data ".env;." ^
   --hidden-import "PySide6.QtCore" ^
   --hidden-import "PySide6.QtGui" ^
   --hidden-import "PySide6.QtWidgets" ^
   --hidden-import "numpy" ^
   --hidden-import "torch" ^
   --hidden-import "ultralytics" ^
   --hidden-import "pydicom" ^
   --hidden-import "cv2" ^
   --name "hotspotAnalyzer" ^
   main.py
   ```

## ⚠️ Troubleshooting Umum

### 1. Import Error saat Runtime
**Problem:** Module tidak ditemukan saat menjalankan exe
**Solution:** Tambahkan ke `hiddenimports` di spec file:
```python
hiddenimports = [
    'nama_module_yang_missing',
    # ...
]
```

### 2. File/Folder Tidak Tercopy
**Problem:** Config atau data tidak ada di exe
**Solution:** Tambahkan ke `datas` di spec file:
```python
datas = [
    ('source_folder', 'dest_folder'),
    # ...
]
```

### 3. PyTorch/CUDA Issues
**Problem:** Error dengan PyTorch atau CUDA
**Solution:** Pastikan menggunakan CPU version untuk distribusi:
```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
```

### 4. Aplikasi Crash saat Startup
**Problem:** Exe crash tanpa error message
**Solution:** 
- Set `console=True` di spec file untuk debugging
- Check dependency conflicts
- Pastikan semua path relatif benar

### 5. Size Terlalu Besar
**Problem:** File exe terlalu besar (>1GB)
**Solution:**
- Gunakan `--exclude-module` untuk exclude module yang tidak perlu
- Gunakan virtual environment yang clean
- Consider menggunakan `--onefile` dengan eksternal data folder

## 📦 Optimasi Build

### 1. Mengurangi Size
```bash
# Exclude modules yang tidak perlu
--exclude-module tkinter
--exclude-module matplotlib.backends.backend_tkagg
```

### 2. Speed Optimization
```bash
# Disable UPX compression jika menyebabkan masalah
--noupx
```

### 3. Debug Mode
```bash
# Untuk debugging
--debug=imports
--debug=bootloader
```

## 🎯 Final Structure
Setelah build sukses, Anda akan mendapat:

```
hotspotAnalyzer/
├── hotspotAnalyzer.exe          # Main executable
├── _internal/                   # Dependencies (jangan dihapus!)
├── config/
│   ├── doctor_tags.json
│   └── sessions.json
├── data/
│   ├── PLANAR/
│   ├── SPECT/
│   ├── PET/
│   └── DICOM/
├── assets/
├── models/
├── logs/
├── temp/
└── run_hotspot_analyzer.bat     # Launcher batch file
```

## 🚀 Distribusi

### Untuk Distribusi:
1. **Zip seluruh folder `hotspotAnalyzer`**
2. **User tinggal extract dan double-click `hotspotAnalyzer.exe`**
3. **Atau gunakan batch file untuk launcher yang lebih user-friendly**

### Requirements untuk End User:
- Windows 10/11 (64-bit)
- Tidak perlu install Python atau dependencies
- Minimal 8GB RAM (untuk AI models)
- GPU optional (akan fallback ke CPU)

## 💡 Tips

1. **Test di clean environment** sebelum distribusi
2. **Include README** dengan instruksi penggunaan
3. **Consider membuat installer** menggunakan tools seperti Inno Setup
4. **Monitor memory usage** - aplikasi AI bisa memory-intensive
5. **Backup data directory** sebelum update aplikasi

## 🐛 Debug Tips

Jika ada masalah:
1. Jalankan dari command prompt untuk melihat error
2. Check logs di folder `logs/`
3. Gunakan `console=True` di spec file
4. Test import manual di Python console
5. Check file permissions di folder data