# app/__main__.py - PRODUCTION READY VERSION with ENHANCED DEBUG
"""
Main application entry point - Production Ready
Handles PyInstaller compatibility and application startup
Version: 2.1 - Enhanced Debug + Auto-Close Detection
"""


import sys
import logging
import os
import matplotlib
matplotlib.use('QtAgg') 
from pathlib import Path
import traceback
from io import StringIO
import datetime # NEW: Tambahkan import datetime
    
# ========== CRITICAL: PYINSTALLER DEBUG ==========
def debug_pyinstaller_state():
    """Debug PyInstaller state untuk analyze masalah"""
    if not hasattr(sys, '_MEIPASS'):
        return
    
    logging.info("\n  [MAIN DEBUG] PyInstaller Environment Analysis")
    logging.info("=" * 60)
    logging.info(f"_MEIPASS: {sys._MEIPASS}")
    logging.info(f"executable: {sys.executable}")
    
    # Debug torch.library sebelum import apapun
    if 'torch.library' in sys.modules:
        lib = sys.modules['torch.library']
        logging.info(f"torch.library pre-loaded: {type(lib)}")
        is_blocker = 'TritonBlocker' in str(type(lib))
        logging.info(f"Is TritonBlocker: {is_blocker}")
        logging.info(f"Has _register_fake: {hasattr(lib, '_register_fake')}")
        logging.info(f"Has register_fake: {hasattr(lib, 'register_fake')}")
        
        if hasattr(lib, 'Library'):
            try:
                test_lib = lib.Library("test")
                logging.info(f"Library class: {type(test_lib)}")
                logging.info(f"Library._register_fake: {hasattr(test_lib, '_register_fake')}")
            except Exception as e:
                logging.info(f"Library test failed: {e}")
        else:
            logging.info("No Library class found")
        
        if is_blocker:
            logging.info("⚠️  PROBLEM: torch.library is TritonBlocker!")
    else:
        logging.info("torch.library not pre-loaded")
    
    # Count triton modules
    triton_mods = [k for k in sys.modules.keys() if 'triton' in k.lower()]
    blocker_mods = [k for k in triton_mods if 'TritonBlocker' in str(type(sys.modules[k]))]
    logging.info(f"Pre-existing triton modules: {len(triton_mods)} (Blockers: {len(blocker_mods)})")
    
    # Show some key modules
    for mod in triton_mods[:8]:  # Show first 8
        is_blocker = 'TritonBlocker' in str(type(sys.modules[mod]))
        logging.info(f"  {mod}: {'BLOCKER' if is_blocker else 'Normal'}")
    
    # Test torch.library creation
    logging.info("\nTesting torch.library functionality:")
    try:
        if 'torch.library' in sys.modules:
            lib = sys.modules['torch.library']
            if hasattr(lib, 'Library'):
                test_lib = lib.Library("test_lib")
                if hasattr(test_lib, '_register_fake'):
                    logging.info("  torch.library._register_fake works")
                else:
                    logging.info(" torch.library._register_fake missing")
            else:
                logging.info(" torch.library.Library missing")
        else:
            logging.info(" torch.library not available")
    except Exception as e:
        logging.info(f" torch.library test failed: {e}")
    
    logging.info("=" * 60)
    logging.info("OK")

# ========== CRITICAL: PYINSTALLER EARLY SETUP ==========
def setup_pyinstaller_environment():
    """Setup PyInstaller environment BEFORE any other imports"""
    if not hasattr(sys, '_MEIPASS'):
        logging.info("[ENV] Development mode, using normal configuration")
        return
    
    logging.info("[ENV] PyInstaller build detected, applying early configuration...")
    
    # Critical environment variables - set BEFORE any torch-related imports
    critical_env = {
        'TRITON_DISABLE': '1', 
        'TORCH_TRITON_DISABLE': '1',
        'USE_TRITON': '0',
        'TORCH_DISABLE_TRITON_OPS': '1',
        'TORCH_DISABLE_TRITON_LIBRARY': '1',
        'TORCH_DISABLE_TRITON_REGISTRATION': '1',
        'TORCH_JIT': '0',
        'TORCH_JIT_LOG_LEVEL': 'ERROR',
        'TORCHDYNAMO_DISABLE': '1',
        'TORCH_COMPILE_DISABLE': '1',
        'TORCH_DYNAMO_DISABLE': '1',
        'TORCH_FX_DISABLE': '1',
        'PYTHONDONTWRITEBYTECODE': '1',
        'PYTHONOPTIMIZE': '1',
        #   ENHANCED: Better torchvision fixes
        'TORCHVISION_DISABLE_META_REGISTRATION': '1',
        'TORCHVISION_DISABLE_EXTENSIONS': '1',  # NEW
        'TORCHVISION_DISABLE_VIDEO_OPT': '1',   # NEW
        'TORCH_LIBRARY_DISABLE': '1',
    }
    
    for key, value in critical_env.items():
        if key not in os.environ:
            os.environ[key] = value
    
    logging.info(f"[ENV] Set {len(critical_env)} critical environment variables")

# Apply environment setup immediately
setup_pyinstaller_environment()

#   ADD: Debug state BEFORE any imports
debug_pyinstaller_state()

# ========== APPLY EARLY PATCHES ==========
def apply_early_patches():
    """Apply early patches before any problematic imports"""
    if not hasattr(sys, '_MEIPASS'):
        return True
    
    try:
        from core.utils.pyinstaller_patches import apply_early_patches
        success = apply_early_patches()
        logging.info(f"[EARLY PATCH] Early patches {'successful' if success else 'failed'}")
        return success
    except ImportError as e:
        logging.info(f"[EARLY PATCH WARNING] Could not apply early patches: {e}")
        return False
    except Exception as e:
        logging.info(f"[EARLY PATCH ERROR] Unexpected error: {e}")
        logging.info(f"[EARLY PATCH ERROR] Traceback: {traceback.format_exc()}")
        return False

# Apply early patches
apply_early_patches()

#   ADD: Debug state AFTER patches
if hasattr(sys, '_MEIPASS'):
    logging.info("\n  [POST-PATCH DEBUG] State after patches:")
    if 'torch.library' in sys.modules:
        lib = sys.modules['torch.library']
        is_blocker = 'TritonBlocker' in str(type(lib))
        logging.info(f"  torch.library after patches: {'BLOCKER' if is_blocker else 'Normal'}")
        logging.info(f"  Has _register_fake: {hasattr(lib, '_register_fake')}")
    else:
        logging.info("  torch.library not yet loaded")
    logging.info("OK")

# ========== STANDARD LIBRARY IMPORTS (SAFE) ==========
try:
    # Force early import of problematic standard library modules
    import unittest
    import unittest.mock
    import unittest.util
    import pydoc
    import pydoc_data.topics
    import textwrap
    import linecache
    import tokenize
    import keyword
    import inspect
    import doctest
    logging.info("[DEBUG] All required standard library modules loaded successfully")
except ImportError as e:
    logging.info(f"[WARNING] Could not import some standard library modules: {e}")

# ========== PYSIDE6 IMPORTS ==========
try:
    from PySide6.QtWidgets import QApplication, QMessageBox, QDialog
    from PySide6.QtCore import QTimer, QThread, Qt
    from PySide6.QtGui import QPalette, QColor, QFont, QIcon
    logging.info("[DEBUG] PySide6 modules imported successfully")
except ImportError as e:
    logging.info(f"[CRITICAL ERROR] Could not import PySide6: {e}")
    sys.exit(1)

# ========== APPLICATION IMPORTS ==========
# try:
#     # Import main application modules
#     from features.spect_viewer.gui.main_window_spect import MainWindowSpect
#     from features.dicom_import.gui.doctor_selection_dialog import DoctorSelectionDialog
#     logging.info("[DEBUG] Application modules imported successfully")
# except ImportError as e:
#     logging.info(f"[CRITICAL ERROR] Could not import application modules: {e}")
#     logging.info(f"[CRITICAL ERROR] Traceback: {traceback.format_exc()}")
#     sys.exit(1)

#   ADD: Debug state AFTER imports
if hasattr(sys, '_MEIPASS'):
    logging.info("\n  [POST-IMPORT DEBUG] State after all imports:")
    
    # Test torch import
    try:
        import torch
        logging.info("    torch import: SUCCESS")
        
        if hasattr(torch, 'library'):
            lib = torch.library
            is_blocker = 'TritonBlocker' in str(type(lib))
            logging.info(f"  torch.library: {'BLOCKER' if is_blocker else 'Normal'}")
            logging.info(f"  torch.library._register_fake: {hasattr(lib, '_register_fake')}")
        else:
            logging.info("  torch.library not available")
            
    except Exception as e:
        logging.info(f"   torch import failed: {e}")
    
    # Test torchvision import
    try:
        import torchvision
        logging.info("    torchvision import: SUCCESS")
    except Exception as e:
        logging.info(f"   torchvision import failed: {type(e).__name__}")
    
    # Test ultralytics import
    try:
        from ultralytics import YOLO
        logging.info("    ultralytics import: SUCCESS")
    except Exception as e:
        logging.info(f"   ultralytics import failed: {type(e).__name__}")
    
    # Test nnunet import
    try:
        from nnunetv2.inference.predict_from_raw_data import nnUNetPredictor
        logging.info("    nnunetv2 import: SUCCESS")
    except Exception as e:
        logging.info(f"   nnunetv2 import failed: {type(e).__name__}")
    
    logging.info("OK")

class StreamToLogger:
    """
    Kustom stream object untuk meredirect stdout dan stderr ke Python logger.
    Ini memastikan semua output logging.info() akan masuk ke file log.
    """
    def __init__(self, logger, log_level=logging.INFO):
        self.logger = logger
        self.log_level = log_level
        self.line_buffer = ''

    def write(self, buf):
        for line in buf.rstrip().splitlines():
            # Jika ada pesan yang dimulai dengan "DEBUG", kita asumsikan itu adalah log.
            # Jika tidak, kita log sebagai INFO.
            if line.startswith("DEBUG"):
                self.logger.log(logging.DEBUG, line.strip())
            else:
                self.logger.log(self.log_level, line.strip())

    def flush(self):
        pass

# -----------------------------------------------

# ========== UI THEME CONFIGURATION ==========
def make_light_palette() -> QPalette:
    """Create light theme palette for the application"""
    pal = QPalette()
    pal.setColor(QPalette.Window, QColor("#f5f6fa"))
    pal.setColor(QPalette.WindowText, QColor("#222"))
    pal.setColor(QPalette.Base, QColor("#ffffff"))
    pal.setColor(QPalette.AlternateBase, QColor("#f0f0f0"))
    pal.setColor(QPalette.Text, QColor("#222"))
    pal.setColor(QPalette.Button, QColor("#ebecef"))
    pal.setColor(QPalette.ButtonText, QColor("#222"))
    pal.setColor(QPalette.Highlight, QColor("#4e73ff"))
    pal.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    return pal

# ========== APPLICATION BOOTSTRAP ==========
class ApplicationBootstrap:
    """Handles application initialization and error recovery"""
    
    def __init__(self):
        self.app = None
        self.windows = []  # Keep references to prevent garbage collection
        self.is_shutting_down = False
        self.dialog_attempts = 0  # Track dialog attempts
        self.max_dialog_attempts = 3  # Maximum retry attempts
    
    def create_application(self):
        """Create and configure the Qt application"""
        try:
            self.app = QApplication(sys.argv)
            self.app.setStyle("Fusion")
            self.app.setPalette(make_light_palette())
            
            #   NEW: Set application icon
            try:
                from pathlib import Path
                icon_path = Path("assets/icon.ico")
                if icon_path.exists():
                    self.app.setWindowIcon(QIcon(str(icon_path)))
                    logging.info(f"[UI] Application icon loaded: {icon_path}")
                else:
                    logging.info(f"[UI] Icon file not found: {icon_path}")
            except Exception as e:
                logging.info(f"[UI] Failed to load application icon: {e}")
            
            #   NEW: Set application metadata
            self.app.setApplicationName("TELPLASTINA")
            self.app.setApplicationDisplayName("Bone Metastasis Analysis V1.6")
            self.app.setApplicationVersion("1.6")
            self.app.setOrganizationName("Telkom University & Universitas Padjadjaran")
            self.app.setOrganizationDomain("telplastina.ai")
            
            # Try to set Poppins font, fallback to system default
            try:
                self.app.setFont(QFont("Poppins"))
                logging.info("[UI] Poppins font applied")
            except Exception:
                logging.info("[UI] Using system default font")
            
            logging.info("[DEBUG] TELPLASTINA application created and configured")
            return True
            
        except Exception as e:
            logging.info(f"[CRITICAL ERROR] Failed to create Qt application: {e}")
            return False
    
    def apply_post_import_patches(self):
        """Apply patches after all imports are done"""
        if not hasattr(sys, '_MEIPASS'):
            return True
        
        try:
            from core.utils.pyinstaller_patches import apply_all_patches, validate_patches
            
            success = apply_all_patches()
            if success:
                validate_patches()
                logging.info("[PATCH] All patches applied and validated successfully")
            else:
                logging.info("[PATCH] Some patches failed, but continuing...")
            
            return True
        except Exception as e:
            logging.info(f"[PATCH ERROR] Error applying post-import patches: {e}")
            return False
    
    def start_new_session(self):
        """Start a new session with doctor selection and enhanced error handling"""
        if self.is_shutting_down:
            logging.info("[DEBUG] Shutdown in progress, skipping new session")
            return
        
        try:
            logging.info("[DEBUG] === Starting new session ===")
            
            #   ENHANCED: Add application state check
            if not self.app:
                logging.info("[ERROR] Qt application not available")
                self.shutdown_application()
                return
            
            #   ENHANCED: Ensure application is ready
            self.app.processEvents()  # Process any pending events
            
            #   ENHANCED: Add delay for PyInstaller environment
            if hasattr(sys, '_MEIPASS'):
                logging.info("[DEBUG] PyInstaller mode - adding startup delay...")
                QTimer.singleShot(500, self._create_dialog_delayed)
            else:
                logging.info("[DEBUG] Development mode - creating dialog immediately")
                self._create_dialog_delayed()
                
        except Exception as e:
            logging.info(f"[ERROR] Fatal error in start_new_session: {e}")
            logging.info(f"[ERROR] Traceback: {traceback.format_exc()}")
            
            # Show error dialog if possible
            try:
                if self.app:
                    error_msg = (
                        f"Failed to start application session.\n\n"
                        f"Error: {str(e)}\n\n"
                        f"Please check the console for more details."
                    )
                    QMessageBox.critical(None, "Application Error", error_msg)
            except Exception:
                pass  # Fallback if even error dialog fails
            
            # Try to restart session after delay
            if not self.is_shutting_down:
                logging.info("[DEBUG] Attempting to restart session in 3 seconds...")
                QTimer.singleShot(3000, self.start_new_session)

    def _create_dialog_delayed(self):
        """Create and show doctor selection dialog with enhanced debugging"""
        if self.is_shutting_down:
            logging.info("[DEBUG] Shutdown in progress, cancelling dialog creation")
            return
        
        # Check attempt count
        self.dialog_attempts += 1
        if self.dialog_attempts > self.max_dialog_attempts:
            logging.info(f"[ERROR] Maximum dialog attempts ({self.max_dialog_attempts}) reached, shutting down")
            self.shutdown_application()
            return
        
        try:
            logging.info(f"[DEBUG] Creating doctor selection dialog (attempt {self.dialog_attempts}/{self.max_dialog_attempts})...")
            
            #   ENHANCED: Import with error handling
            try:
                from features.dicom_import.gui.doctor_selection_dialog import DoctorSelectionDialog
                logging.info("[DEBUG] Dialog class imported successfully")
            except ImportError as e:
                logging.info(f"[ERROR] Failed to import dialog: {e}")
                self.shutdown_application()
                return
            
            #   ENHANCED: Create dialog with error handling
            try:
                dlg = DoctorSelectionDialog()
                logging.info("[DEBUG] Dialog instance created successfully")
            except Exception as e:
                logging.info(f"[ERROR] Failed to create dialog instance: {e}")
                logging.info(f"[ERROR] Dialog creation traceback: {traceback.format_exc()}")
                
                # Show simpler error and retry
                try:
                    QMessageBox.critical(
                        None, 
                        "Dialog Creation Error", 
                        f"Failed to create doctor selection dialog.\n\nError: {e}\n\nRetrying in 2 seconds..."
                    )
                except Exception:
                    pass
                
                QTimer.singleShot(2000, self.start_new_session)
                return
            
            #   ENHANCED: Set dialog properties for better visibility
            try:
                dlg.setWindowState(dlg.windowState() & ~Qt.WindowMinimized | Qt.WindowActive)
                dlg.raise_()
                dlg.activateWindow()
                logging.info("[DEBUG] Dialog window properties set")
            except Exception as e:
                logging.info(f"[WARNING] Failed to set dialog properties: {e}")
            
            #   ENHANCED: Show dialog with debugging
            logging.info("[DEBUG] Showing dialog to user...")
            try:
                dlg.show()  # Show first to ensure visibility
                self.app.processEvents()  # Process show event
                logging.info("[DEBUG] Dialog shown successfully")
            except Exception as e:
                logging.info(f"[ERROR] Failed to show dialog: {e}")
                self.shutdown_application()
                return
            
            #   ENHANCED: Execute dialog with timeout protection
            logging.info("[DEBUG] Waiting for user input...")
            
            # Add a timer to detect if dialog closes too quickly
            dialog_timer = QTimer()
            dialog_timer.setSingleShot(True)
            dialog_closed_quickly = False
            
            def check_quick_close():
                nonlocal dialog_closed_quickly
                if not dlg.isVisible():
                    dialog_closed_quickly = True
                    logging.info("[WARNING] Dialog closed very quickly - possible auto-close detected")
            
            dialog_timer.timeout.connect(check_quick_close)
            dialog_timer.start(100)  # Check after 100ms
            
            # Execute dialog
            try:
                result = dlg.exec()
                dialog_timer.stop()
                logging.info(f"[DEBUG] Dialog execution completed with result: {result}")
                logging.info(f"[DEBUG] Quick close detected: {dialog_closed_quickly}")
            except Exception as e:
                dialog_timer.stop()
                logging.info(f"[ERROR] Dialog execution failed: {e}")
                self.shutdown_application()
                return
            
            #   ENHANCED: Handle dialog result
            if not result or result == QDialog.Rejected:
                if dialog_closed_quickly:
                    logging.info("[DEBUG] Dialog closed quickly - attempting retry...")
                    # Retry after longer delay
                    QTimer.singleShot(2000, self.start_new_session)
                    return
                else:
                    logging.info("[DEBUG] User cancelled dialog, exiting application")
                    self.shutdown_application()
                    return
            
            #   ENHANCED: Process dialog results
            try:
                session_code = dlg.selected_doctor_id
                selected_modality = dlg.selected_modality
                
                logging.info(f"[DEBUG] Session selected - Code: {session_code}, Modality: {selected_modality}")
                
                if not session_code:
                    logging.info("[ERROR] No session code selected")
                    QMessageBox.warning(None, "Selection Error", "No doctor code was selected.")
                    QTimer.singleShot(1000, self.start_new_session)
                    return
                    
            except Exception as e:
                logging.info(f"[ERROR] Failed to get dialog results: {e}")
                QTimer.singleShot(1000, self.start_new_session)
                return
            
            #   ENHANCED: Create data directory
            try:
                data_dir = Path("data")
                data_dir.mkdir(exist_ok=True)
                logging.info(f"[DEBUG] Data directory confirmed: {data_dir}")
            except Exception as e:
                logging.info(f"[ERROR] Failed to create data directory: {e}")
            
            #   ENHANCED: Handle modality selection
            if selected_modality == "Planar":
                logging.info(f"[DEBUG] Starting PLANAR session with code: {session_code}")
                # Reset dialog attempts on successful dialog
                self.dialog_attempts = 0
                self._create_main_window_safe(session_code, data_dir)
            else:
                logging.info(f"[WARNING] Unsupported modality: {selected_modality}")
                try:
                    QMessageBox.critical(
                        None, 
                        "Modality Not Supported", 
                        f"Modality '{selected_modality}' is not supported in this version.\n"
                        f"Only 'Planar' modality is currently available."
                    )
                    # Return to dialog selection
                    QTimer.singleShot(1000, self.start_new_session)
                except Exception as e:
                    logging.info(f"[ERROR] Failed to show modality error: {e}")
                    self.shutdown_application()
                    
        except Exception as e:
            logging.info(f"[ERROR] Fatal error in _create_dialog_delayed: {e}")
            logging.info(f"[ERROR] Traceback: {traceback.format_exc()}")
            
            # Last resort: try to restart
            if not self.is_shutting_down:
                logging.info("[DEBUG] Fatal error occurred, attempting restart in 5 seconds...")
                QTimer.singleShot(5000, self.start_new_session)

    def _create_main_window_safe(self, session_code, data_dir):
        """Safely create main window with comprehensive error handling"""
        try:
            logging.info(f"[DEBUG] Creating main window for session: {session_code}")
            
            window = self.create_main_window(session_code, data_dir)
            if window:
                logging.info("[DEBUG] Main window created successfully")
                
                # Setup window
                self.setup_window_signals(window)
                
                # Show window
                try:
                    window.show()
                    window.raise_()
                    window.activateWindow()
                    logging.info("[DEBUG] Main window displayed")
                    
                    # Add to windows list
                    self.windows.append(window)
                    logging.info(f"[DEBUG] Active windows count: {len(self.windows)}")
                    
                except Exception as e:
                    logging.info(f"[ERROR] Failed to show main window: {e}")
                    window.deleteLater()
                    QTimer.singleShot(2000, self.start_new_session)
            else:
                logging.info("[ERROR] Failed to create main window - retrying session")
                QTimer.singleShot(3000, self.start_new_session)
                
        except Exception as e:
            logging.info(f"[ERROR] Error in _create_main_window_safe: {e}")
            logging.info(f"[ERROR] Traceback: {traceback.format_exc()}")
            QTimer.singleShot(3000, self.start_new_session)
    
    def create_main_window(self, session_code, data_dir):
        """Create main window with error handling"""
        try:
            #   PINDAHKAN IMPOR KE SINI
            # Impor hanya akan terjadi saat fungsi ini dipanggil oleh proses utama,
            # bukan oleh child process.
            from features.spect_viewer.gui.main_window_spect import MainWindowSpect
            
            window = MainWindowSpect(session_code=session_code, data_root=data_dir)
            logging.info(f"[DEBUG] Main window created successfully for session: {session_code}")
            return window
        except Exception as e:
            logging.info(f"[ERROR] Failed to create main window: {e}")
            logging.info(f"[ERROR] Traceback: {traceback.format_exc()}")
            
            error_msg = (
                f"Failed to create main window.\n\n"
                f"Error: {str(e)}\n\n"
                f"This might be due to missing model files or configuration issues."
            )
            QMessageBox.critical(None, "Window Creation Error", error_msg)
            return None
    
    def setup_window_signals(self, window):
        """Setup window signals and connections"""
        def handle_logout():
            """Handle logout and start new session"""
            if self.is_shutting_down:
                return
            
            logging.info("[DEBUG] Logout requested")
            try:
                window.hide()
                
                # Remove from windows list
                if window in self.windows:
                    self.windows.remove(window)
                
                # Schedule window deletion
                window.deleteLater()
                
                # Start new session after cleanup
                QTimer.singleShot(500, self.start_new_session)
                
            except Exception as e:
                logging.info(f"[ERROR] Error during logout: {e}")
                # Force restart session
                QTimer.singleShot(1000, self.start_new_session)
        
        # Connect logout signal if available
        try:
            if hasattr(window, 'logout_requested'):
                window.logout_requested.connect(handle_logout)
                logging.info("[DEBUG] Logout signal connected")
        except Exception as e:
            logging.info(f"[WARNING] Could not connect logout signal: {e}")
    
    def shutdown_application(self):
        """Gracefully shutdown the application"""
        #   ADD: Prevent recursive calls (extra safety)
        if self.is_shutting_down:
            return
            
        self.is_shutting_down = True
        logging.info("[DEBUG] Shutting down application...")
        
        # Close all windows
        for window in self.windows[:]:  # Copy list to avoid modification during iteration
            try:
                #   ADD: Disconnect window signals to prevent additional triggers
                if hasattr(window, 'logout_requested'):
                    try:
                        window.logout_requested.disconnect()
                    except:
                        pass
                
                window.close()
                window.deleteLater()
            except Exception as e:
                logging.info(f"[WARNING] Error closing window: {e}")
        
        self.windows.clear()
        
        # Quit application
        if self.app:
            self.app.quit()
        
    def run(self):
        """Main application run method"""
        logging.info("[DEBUG] Starting TELPLASTINA...")
        
        # Apply post-import patches
        self.apply_post_import_patches()
        
        # Create Qt application
        if not self.create_application():
            return 1
        
        #  REMOVED: aboutToQuit connection to prevent recursive loop
        # self.app.aboutToQuit.connect(self.shutdown_application)
        
        # Start the first session with longer delay for PyInstaller
        startup_delay = 1500 if hasattr(sys, '_MEIPASS') else 100
        logging.info(f"[DEBUG] Starting session with {startup_delay}ms delay...")
        QTimer.singleShot(startup_delay, self.start_new_session)
        
        # Run the application event loop
        try:
            exit_code = self.app.exec()
            logging.info(f"[DEBUG] Application exited with code: {exit_code}")
            return exit_code
        except Exception as e:
            logging.info(f"[CRITICAL ERROR] Application crashed: {e}")
            logging.info(f"[CRITICAL ERROR] Traceback: {traceback.format_exc()}")
            return 1

# ========== MAIN FUNCTION ==========
# ========== MAIN FUNCTION ==========
def main():
    """Main application entry point with comprehensive error handling"""
    # ==========================================================
    # ✅ KONFIGURASI LOGGING
    # ==========================================================
    # Menonaktifkan logger yang tidak relevan
    logging.getLogger('matplotlib.font_manager').disabled = True
    logging.getLogger('matplotlib').disabled = True

    # Tentukan path log file berdasarkan mode aplikasi
    if hasattr(sys, '_MEIPASS'):
        log_dir = Path(sys.executable).parent / "logs"
    else:
        log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    log_file_path = log_dir / f"telplastina_log_{timestamp}.log"
    
    # Buat FileHandler dengan level DEBUG
    file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    
    # Buat StreamHandler untuk konsol dengan level INFO
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(logging.INFO)
    
    # Atur format logging
    log_format = "%(asctime)s - [%(levelname)s] - %(message)s"
    formatter = logging.Formatter(log_format, datefmt="%Y-%m-%d %H:%M:%S")
    file_handler.setFormatter(formatter)
    stream_handler.setFormatter(formatter)
    
    # Dapatkan root logger dan tambahkan handlers
    # Root logger level harus terendah untuk memastikan semua pesan tertangkap
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(stream_handler)
    
    logging.info("Logger berhasil dikonfigurasi. Memulai aplikasi...")
    # ==========================================================
    # ==========================================================
    try:
        # Validate Python version
        if sys.version_info < (3, 8):
            logging.error(f"Python 3.8+ required, but {sys.version} found")
            sys.exit(1)
        
        # Check if running as PyInstaller bundle
        if hasattr(sys, '_MEIPASS'):
            logging.info(f"Running as PyInstaller bundle: {sys._MEIPASS}")
        else:
            logging.info("Running in development mode")
        
        # Buat dan jalankan aplikasi
        bootstrap = ApplicationBootstrap()
        exit_code = bootstrap.run()
        
        # Exit dengan kode yang tepat
        logging.info("Aplikasi terminated normally")
        sys.exit(exit_code)
        
    except KeyboardInterrupt:
        logging.info("\nApplication interrupted by user (Ctrl+C)")
        sys.exit(0)
    except Exception as e:
        logging.critical(f"Fatal error in main(): {e}", exc_info=True)
        
        # Log error terakhir sebelum keluar
        logging.shutdown()
        
        # Coba tampilkan dialog error jika Qt tersedia
        try:
            if 'QApplication' in globals():
                app = QApplication.instance()
                if not app:
                    app = QApplication(sys.argv)
                
                error_msg = (
                    f"A fatal error occurred:\n\n"
                    f"{str(e)}\n\n"
                    f"The application will now exit.\n"
                    f"Please check the console for more details."
                )
                QMessageBox.critical(None, "Fatal Error", error_msg)
        except Exception:
            pass  # Qt not available or failed
        
        sys.exit(1)

# ========== ENTRY POINT ==========
if __name__ == "__main__":
    main()