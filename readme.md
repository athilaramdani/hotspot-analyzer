# HotspotAnalyzer | Medical AI Metastasis Detection

A comprehensive medical AI application for detecting and analyzing hotspots in nuclear medicine imaging using multiple AI models.

## ✨ Features

- **YOLO-based Hotspot Detection**: Real-time detection of abnormal areas
- **nnUNet Bone Segmentation**: Advanced bone region segmentation
- **XGBoost Classification**: Machine learning-based classification
- **DICOM Processing**: Full support for medical imaging standards
- **Professional GUI**: User-friendly PySide6 desktop interface
- **Cross-platform**: Windows, macOS, and Linux support

## 🔧 System Requirements

### Minimum Requirements
- **OS**: Windows 10/11, macOS 10.15+, or Ubuntu 18.04+
- **RAM**: 8GB (16GB recommended)
- **Storage**: 10GB free space
- **Python**: 3.8 - 3.11

### Recommended Requirements
- **RAM**: 16GB or more
- **GPU**: NVIDIA GPU with CUDA support (optional, for faster inference)
- **Storage**: SSD with 20GB+ free space

## 🚀 Quick Start (Windows)

### Option 1: Use Pre-built Installer (Recommended)
1. Download `HotspotAnalyzer V 1 0.zip`
2. extract zip and run the exe

### Option 2: Build from Source
```bash
# 1. Clone repository
git clone <repository-url>
cd hotspot-analyzer

# 2. Create virtual environment
python -m venv .venv
.venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements-windows.txt

# 4. Build executable
pyinstaller hotspot_analyzer.spec --clean --noconfirm

# 5. Run application
dist\HotspotAnalyzer\HotspotAnalyzer.exe
```

## 🖥️ Building on Different Platforms

### Windows Build

#### Prerequisites
```bash
# Install Python 3.8-3.11
# Download from: https://python.org

# Install Visual C++ Redistributable
# Download from: https://aka.ms/vs/17/release/vc_redist.x64.exe
```

#### Build Steps
```bash
# Create virtual environment
python -m venv .venv
.venv\Scripts\activate

# Install Windows-specific requirements
pip install -r requirements-windows.txt

# Install PyInstaller
pip install pyinstaller

# Build application
pyinstaller hotspot_analyzer.spec --clean --noconfirm

# Create installer (optional)
# Install Inno Setup from: https://jrsoftware.org/isinfo.php
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
```

### macOS Build

#### Prerequisites
```bash
# Install Python via Homebrew
brew install python@3.11

# Install Xcode Command Line Tools
xcode-select --install
```

#### Build Steps
```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install macOS-specific requirements
pip install -r requirements-mac.txt

# Install PyInstaller
pip install pyinstaller

# Build application
pyinstaller hotspot_analyzer.spec --clean --noconfirm

# Create .app bundle
# Output: dist/HotspotAnalyzer.app
```

#### Create DMG Installer (Optional)
```bash
# Install create-dmg
brew install create-dmg

# Create DMG
create-dmg \
  --volname "HotspotAnalyzer" \
  --window-pos 200 120 \
  --window-size 600 300 \
  --icon-size 100 \
  --icon "HotspotAnalyzer.app" 175 120 \
  --hide-extension "HotspotAnalyzer.app" \
  --app-drop-link 425 120 \
  "HotspotAnalyzer.dmg" \
  "dist/"
```

### Linux Build

#### Prerequisites (Ubuntu/Debian)
```bash
# Update system
sudo apt update

# Install Python and dependencies
sudo apt install python3.11 python3.11-venv python3-pip
sudo apt install build-essential

# Install Qt dependencies for PySide6
sudo apt install qt6-base-dev qt6-tools-dev-tools
sudo apt install libgl1-mesa-glx libegl1-mesa libxrandr2 libxss1 \
                 libxcursor1 libxcomposite1 libasound2 libxi6 libxtst6
```

#### Prerequisites (CentOS/RHEL/Fedora)
```bash
# Install Python
sudo dnf install python3.11 python3-pip python3-venv

# Install development tools
sudo dnf groupinstall "Development Tools"

# Install Qt dependencies
sudo dnf install qt6-qtbase-devel
```

#### Build Steps
```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install Linux-specific requirements
pip install -r requirements-linux.txt

# Install PyInstaller
pip install pyinstaller

# Build application
pyinstaller hotspot_analyzer.spec --clean --noconfirm

# Run application
./dist/HotspotAnalyzer/HotspotAnalyzer
```

#### Create AppImage (Optional)
```bash
# Download linuxdeploy
wget https://github.com/linuxdeploy/linuxdeploy/releases/download/continuous/linuxdeploy-x86_64.AppImage
chmod +x linuxdeploy-x86_64.AppImage

# Create AppImage
./linuxdeploy-x86_64.AppImage --appdir dist/HotspotAnalyzer --output appimage
```

## 📦 Requirements Files

The project includes platform-specific requirements:

- `requirements-windows.txt` - Windows dependencies
- `requirements-mac.txt` - macOS dependencies  
- `requirements-linux.txt` - Linux dependencies
- `requirements.txt` - Base requirements (all platforms)

## 🐳 Docker Support (Linux Only)

```bash
# Build Docker image
docker build -t hotspot-analyzer .

# Run with X11 forwarding (GUI support)
docker run -it --rm \
  -e DISPLAY=$DISPLAY \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  hotspot-analyzer
```

**Note**: Docker GUI support is experimental and not recommended for production use.

## 🛠️ Development Setup

### Setting up Development Environment
```bash
# Clone repository
git clone <repository-url>
cd hotspot-analyzer

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Install development dependencies
pip install -r requirements-dev.txt

# Run in development mode
python -m app
```

### Code Structure
```
hotspot-analyzer/
├── app/                    # Main application
├── core/                   # Core utilities
├── features/              # Feature modules
│   ├── spect_viewer/      # SPECT imaging viewer
│   ├── dicom_import/      # DICOM processing
│   └── pet_viewer/        # PET imaging viewer
├── models/                # AI model files
├── config/                # Configuration files
├── hooks/                 # PyInstaller hooks
├── assets/                # Application assets
└── docs/                  # Documentation
```

## 🚨 Troubleshooting

### Common Build Issues

#### "Module not found" errors
```bash
# Clear pip cache
pip cache purge

# Reinstall requirements
pip uninstall -r requirements.txt -y
pip install -r requirements-<platform>.txt
```

#### PyInstaller memory errors
```bash
# Increase virtual memory (Windows)
# Or use lighter compression in .spec file
```

#### Qt/PySide6 issues on Linux
```bash
# Install missing Qt libraries
sudo apt install qt6-base-dev qt6-tools-dev-tools

# Set Qt platform plugin
export QT_QPA_PLATFORM=xcb
```

#### CUDA/PyTorch issues
```bash
# For CPU-only build
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu

# For CUDA build
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
```

### Performance Optimization

#### For faster builds
```bash
# Use cached build
pyinstaller hotspot_analyzer.spec --noconfirm

# Skip cleaning (faster subsequent builds)
pyinstaller hotspot_analyzer.spec
```

#### For smaller executables
- Remove unused dependencies from requirements
- Exclude large data files from build
- Use UPX compression (optional)

## 📖 Usage

1. **Launch Application**: Run the executable or use `python -m app`
2. **Import DICOM**: Click "Import DICOM" and select medical imaging files
3. **Select Session**: Choose appropriate session type (PLANAR/SPECT)
4. **AI Processing**: The application automatically runs AI analysis
5. **View Results**: Review hotspot detection, segmentation, and classification results
6. **Export**: Save results in various formats

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is ...

## 🙏 Acknowledgments

- **Medical AI Research Team** - For domain expertise and testing
- **PyTorch Community** - For deep learning frameworks
- **nnUNet Team** - For medical image segmentation
- **Ultralytics** - For YOLO object detection
- **Qt/PySide6** - For GUI framework

## 📞 Support

For technical support or questions:
- Create an issue on GitHub
- Contact the development team
- Check the [documentation](docs/)

---

**Built with ❤️ for medical AI research Telkom University**