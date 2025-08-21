# app/__main__.py - PRODUCTION READY VERSION with ENHANCED DEBUG
"""
Main application entry point - Production Ready
Handles PyInstaller compatibility and application startup
Version: 2.1 - Enhanced Debug + Auto-Close Detection
"""

import sys
import os
from pathlib import Path
import traceback
from io import StringIO

def setup_console_redirect():
    """Setup stdout/stderr redirect for windowed mode"""
    if hasattr(sys, '_MEIPASS') and not hasattr(sys.stdout, 'buffer'):
        # Create log file for debugging
        log_dir = Path(sys.executable).parent / "logs"
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / "telplastina.log"
        
        # Redirect to file instead of void
        log_handle = open(log_file, 'w', encoding='utf-8')
        sys.stdout = log_handle
        sys.stderr = log_handle
        
        print(f"[MAIN] Console redirected to: {log_file}")

# Call BEFORE any AI imports
if hasattr(sys, '_MEIPASS'):
    setup_console_redirect()
    
# ========== CRITICAL: PYINSTALLER DEBUG ==========
def debug_pyinstaller_state():
    """Debug PyInstaller state untuk analyze masalah"""
    if not hasattr(sys, '_MEIPASS'):
        return
    
    print("\n🧪 [MAIN DEBUG] PyInstaller Environment Analysis")
    print("=" * 60)
    print(f"_MEIPASS: {sys._MEIPASS}")
    print(f"executable: {sys.executable}")
    
    # Debug torch.library sebelum import apapun
    if 'torch.library' in sys.modules:
        lib = sys.modules['torch.library']
        print(f"torch.library pre-loaded: {type(lib)}")
        is_blocker = 'TritonBlocker' in str(type(lib))
        print(f"Is TritonBlocker: {is_blocker}")
        print(f"Has _register_fake: {hasattr(lib, '_register_fake')}")
        print(f"Has register_fake: {hasattr(lib, 'register_fake')}")
        
        if hasattr(lib, 'Library'):
            try:
                test_lib = lib.Library("test")
                print(f"Library class: {type(test_lib)}")
                print(f"Library._register_fake: {hasattr(test_lib, '_register_fake')}")
            except Exception as e:
                print(f"Library test failed: {e}")
        else:
            print("No Library class found")
        
        if is_blocker:
            print("⚠️  PROBLEM: torch.library is TritonBlocker!")
    else:
        print("torch.library not pre-loaded")
    
    # Count triton modules
    triton_mods = [k for k in sys.modules.keys() if 'triton' in k.lower()]
    blocker_mods = [k for k in triton_mods if 'TritonBlocker' in str(type(sys.modules[k]))]
    print(f"Pre-existing triton modules: {len(triton_mods)} (Blockers: {len(blocker_mods)})")
    
    # Show some key modules
    for mod in triton_mods[:8]:  # Show first 8
        is_blocker = 'TritonBlocker' in str(type(sys.modules[mod]))
        print(f"  {mod}: {'BLOCKER' if is_blocker else 'Normal'}")
    
    # Test torch.library creation
    print("\nTesting torch.library functionality:")
    try:
        if 'torch.library' in sys.modules:
            lib = sys.modules['torch.library']
            if hasattr(lib, 'Library'):
                test_lib = lib.Library("test_lib")
                if hasattr(test_lib, '_register_fake'):
                    print("✅ torch.library._register_fake works")
                else:
                    print("❌ torch.library._register_fake missing")
            else:
                print("❌ torch.library.Library missing")
        else:
            print("❌ torch.library not available")
    except Exception as e:
        print(f"❌ torch.library test failed: {e}")
    
    print("=" * 60)
    print()

# ========== CRITICAL: PYINSTALLER EARLY SETUP ==========
def setup_pyinstaller_environment():
    """Setup PyInstaller environment BEFORE any other imports"""
    if not hasattr(sys, '_MEIPASS'):
        print("[ENV] Development mode, using normal configuration")
        return
    
    print("[ENV] PyInstaller build detected, applying early configuration...")
    
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
        # ✅ ENHANCED: Better torchvision fixes
        'TORCHVISION_DISABLE_META_REGISTRATION': '1',
        'TORCHVISION_DISABLE_EXTENSIONS': '1',  # NEW
        'TORCHVISION_DISABLE_VIDEO_OPT': '1',   # NEW
        'TORCH_LIBRARY_DISABLE': '1',
    }
    
    for key, value in critical_env.items():
        if key not in os.environ:
            os.environ[key] = value
    
    print(f"[ENV] Set {len(critical_env)} critical environment variables")

# Apply environment setup immediately
setup_pyinstaller_environment()

# ✅ ADD: Debug state BEFORE any imports
debug_pyinstaller_state()

# ========== APPLY EARLY PATCHES ==========
def apply_early_patches():
    """Apply early patches before any problematic imports"""
    if not hasattr(sys, '_MEIPASS'):
        return True
    
    try:
        from core.utils.pyinstaller_patches import apply_early_patches
        success = apply_early_patches()
        print(f"[EARLY PATCH] Early patches {'successful' if success else 'failed'}")
        return success
    except ImportError as e:
        print(f"[EARLY PATCH WARNING] Could not apply early patches: {e}")
        return False
    except Exception as e:
        print(f"[EARLY PATCH ERROR] Unexpected error: {e}")
        print(f"[EARLY PATCH ERROR] Traceback: {traceback.format_exc()}")
        return False

# Apply early patches
apply_early_patches()

# ✅ ADD: Debug state AFTER patches
if hasattr(sys, '_MEIPASS'):
    print("\n🧪 [POST-PATCH DEBUG] State after patches:")
    if 'torch.library' in sys.modules:
        lib = sys.modules['torch.library']
        is_blocker = 'TritonBlocker' in str(type(lib))
        print(f"  torch.library after patches: {'BLOCKER' if is_blocker else 'Normal'}")
        print(f"  Has _register_fake: {hasattr(lib, '_register_fake')}")
    else:
        print("  torch.library not yet loaded")
    print()

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
    print("[DEBUG] All required standard library modules loaded successfully")
except ImportError as e:
    print(f"[WARNING] Could not import some standard library modules: {e}")

# ========== PYSIDE6 IMPORTS ==========
try:
    from PySide6.QtWidgets import QApplication, QMessageBox, QDialog
    from PySide6.QtCore import QTimer, QThread, Qt
    from PySide6.QtGui import QPalette, QColor, QFont, QIcon
    print("[DEBUG] PySide6 modules imported successfully")
except ImportError as e:
    print(f"[CRITICAL ERROR] Could not import PySide6: {e}")
    sys.exit(1)

# ========== APPLICATION IMPORTS ==========
try:
    # Import main application modules
    from features.spect_viewer.gui.main_window_spect import MainWindowSpect
    from features.dicom_import.gui.doctor_selection_dialog import DoctorSelectionDialog
    print("[DEBUG] Application modules imported successfully")
except ImportError as e:
    print(f"[CRITICAL ERROR] Could not import application modules: {e}")
    print(f"[CRITICAL ERROR] Traceback: {traceback.format_exc()}")
    sys.exit(1)

# ✅ ADD: Debug state AFTER imports
if hasattr(sys, '_MEIPASS'):
    print("\n🧪 [POST-IMPORT DEBUG] State after all imports:")
    
    # Test torch import
    try:
        import torch
        print("  ✅ torch import: SUCCESS")
        
        if hasattr(torch, 'library'):
            lib = torch.library
            is_blocker = 'TritonBlocker' in str(type(lib))
            print(f"  torch.library: {'BLOCKER' if is_blocker else 'Normal'}")
            print(f"  torch.library._register_fake: {hasattr(lib, '_register_fake')}")
        else:
            print("  torch.library not available")
            
    except Exception as e:
        print(f"  ❌ torch import failed: {e}")
    
    # Test torchvision import
    try:
        import torchvision
        print("  ✅ torchvision import: SUCCESS")
    except Exception as e:
        print(f"  ❌ torchvision import failed: {type(e).__name__}")
    
    # Test ultralytics import
    try:
        from ultralytics import YOLO
        print("  ✅ ultralytics import: SUCCESS")
    except Exception as e:
        print(f"  ❌ ultralytics import failed: {type(e).__name__}")
    
    # Test nnunet import
    try:
        from nnunetv2.inference.predict_from_raw_data import nnUNetPredictor
        print("  ✅ nnunetv2 import: SUCCESS")
    except Exception as e:
        print(f"  ❌ nnunetv2 import failed: {type(e).__name__}")
    
    print()

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
            
            # ✅ NEW: Set application icon
            try:
                from pathlib import Path
                icon_path = Path("assets/icon.ico")
                if icon_path.exists():
                    self.app.setWindowIcon(QIcon(str(icon_path)))
                    print(f"[UI] Application icon loaded: {icon_path}")
                else:
                    print(f"[UI] Icon file not found: {icon_path}")
            except Exception as e:
                print(f"[UI] Failed to load application icon: {e}")
            
            # ✅ NEW: Set application metadata
            self.app.setApplicationName("TELPLASTINA")
            self.app.setApplicationDisplayName("TELPLASTINA - Bone Metastasis Analysis V1.0")
            self.app.setApplicationVersion("1.0")
            self.app.setOrganizationName("Telkom University & Universitas Padjadjaran")
            self.app.setOrganizationDomain("telplastina.ai")
            
            # Try to set Poppins font, fallback to system default
            try:
                self.app.setFont(QFont("Poppins"))
                print("[UI] Poppins font applied")
            except Exception:
                print("[UI] Using system default font")
            
            print("[DEBUG] TELPLASTINA application created and configured")
            return True
            
        except Exception as e:
            print(f"[CRITICAL ERROR] Failed to create Qt application: {e}")
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
                print("[PATCH] All patches applied and validated successfully")
            else:
                print("[PATCH] Some patches failed, but continuing...")
            
            return True
        except Exception as e:
            print(f"[PATCH ERROR] Error applying post-import patches: {e}")
            return False
    
    def start_new_session(self):
        """Start a new session with doctor selection and enhanced error handling"""
        if self.is_shutting_down:
            print("[DEBUG] Shutdown in progress, skipping new session")
            return
        
        try:
            print("[DEBUG] === Starting new session ===")
            
            # ✅ ENHANCED: Add application state check
            if not self.app:
                print("[ERROR] Qt application not available")
                self.shutdown_application()
                return
            
            # ✅ ENHANCED: Ensure application is ready
            self.app.processEvents()  # Process any pending events
            
            # ✅ ENHANCED: Add delay for PyInstaller environment
            if hasattr(sys, '_MEIPASS'):
                print("[DEBUG] PyInstaller mode - adding startup delay...")
                QTimer.singleShot(500, self._create_dialog_delayed)
            else:
                print("[DEBUG] Development mode - creating dialog immediately")
                self._create_dialog_delayed()
                
        except Exception as e:
            print(f"[ERROR] Fatal error in start_new_session: {e}")
            print(f"[ERROR] Traceback: {traceback.format_exc()}")
            
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
                print("[DEBUG] Attempting to restart session in 3 seconds...")
                QTimer.singleShot(3000, self.start_new_session)

    def _create_dialog_delayed(self):
        """Create and show doctor selection dialog with enhanced debugging"""
        if self.is_shutting_down:
            print("[DEBUG] Shutdown in progress, cancelling dialog creation")
            return
        
        # Check attempt count
        self.dialog_attempts += 1
        if self.dialog_attempts > self.max_dialog_attempts:
            print(f"[ERROR] Maximum dialog attempts ({self.max_dialog_attempts}) reached, shutting down")
            self.shutdown_application()
            return
        
        try:
            print(f"[DEBUG] Creating doctor selection dialog (attempt {self.dialog_attempts}/{self.max_dialog_attempts})...")
            
            # ✅ ENHANCED: Import with error handling
            try:
                from features.dicom_import.gui.doctor_selection_dialog import DoctorSelectionDialog
                print("[DEBUG] Dialog class imported successfully")
            except ImportError as e:
                print(f"[ERROR] Failed to import dialog: {e}")
                self.shutdown_application()
                return
            
            # ✅ ENHANCED: Create dialog with error handling
            try:
                dlg = DoctorSelectionDialog()
                print("[DEBUG] Dialog instance created successfully")
            except Exception as e:
                print(f"[ERROR] Failed to create dialog instance: {e}")
                print(f"[ERROR] Dialog creation traceback: {traceback.format_exc()}")
                
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
            
            # ✅ ENHANCED: Set dialog properties for better visibility
            try:
                dlg.setWindowState(dlg.windowState() & ~Qt.WindowMinimized | Qt.WindowActive)
                dlg.raise_()
                dlg.activateWindow()
                print("[DEBUG] Dialog window properties set")
            except Exception as e:
                print(f"[WARNING] Failed to set dialog properties: {e}")
            
            # ✅ ENHANCED: Show dialog with debugging
            print("[DEBUG] Showing dialog to user...")
            try:
                dlg.show()  # Show first to ensure visibility
                self.app.processEvents()  # Process show event
                print("[DEBUG] Dialog shown successfully")
            except Exception as e:
                print(f"[ERROR] Failed to show dialog: {e}")
                self.shutdown_application()
                return
            
            # ✅ ENHANCED: Execute dialog with timeout protection
            print("[DEBUG] Waiting for user input...")
            
            # Add a timer to detect if dialog closes too quickly
            dialog_timer = QTimer()
            dialog_timer.setSingleShot(True)
            dialog_closed_quickly = False
            
            def check_quick_close():
                nonlocal dialog_closed_quickly
                if not dlg.isVisible():
                    dialog_closed_quickly = True
                    print("[WARNING] Dialog closed very quickly - possible auto-close detected")
            
            dialog_timer.timeout.connect(check_quick_close)
            dialog_timer.start(100)  # Check after 100ms
            
            # Execute dialog
            try:
                result = dlg.exec()
                dialog_timer.stop()
                print(f"[DEBUG] Dialog execution completed with result: {result}")
                print(f"[DEBUG] Quick close detected: {dialog_closed_quickly}")
            except Exception as e:
                dialog_timer.stop()
                print(f"[ERROR] Dialog execution failed: {e}")
                self.shutdown_application()
                return
            
            # ✅ ENHANCED: Handle dialog result
            if not result or result == QDialog.Rejected:
                if dialog_closed_quickly:
                    print("[DEBUG] Dialog closed quickly - attempting retry...")
                    # Retry after longer delay
                    QTimer.singleShot(2000, self.start_new_session)
                    return
                else:
                    print("[DEBUG] User cancelled dialog, exiting application")
                    self.shutdown_application()
                    return
            
            # ✅ ENHANCED: Process dialog results
            try:
                session_code = dlg.selected_doctor_id
                selected_modality = dlg.selected_modality
                
                print(f"[DEBUG] Session selected - Code: {session_code}, Modality: {selected_modality}")
                
                if not session_code:
                    print("[ERROR] No session code selected")
                    QMessageBox.warning(None, "Selection Error", "No doctor code was selected.")
                    QTimer.singleShot(1000, self.start_new_session)
                    return
                    
            except Exception as e:
                print(f"[ERROR] Failed to get dialog results: {e}")
                QTimer.singleShot(1000, self.start_new_session)
                return
            
            # ✅ ENHANCED: Create data directory
            try:
                data_dir = Path("data")
                data_dir.mkdir(exist_ok=True)
                print(f"[DEBUG] Data directory confirmed: {data_dir}")
            except Exception as e:
                print(f"[ERROR] Failed to create data directory: {e}")
            
            # ✅ ENHANCED: Handle modality selection
            if selected_modality == "Planar":
                print(f"[DEBUG] Starting PLANAR session with code: {session_code}")
                # Reset dialog attempts on successful dialog
                self.dialog_attempts = 0
                self._create_main_window_safe(session_code, data_dir)
            else:
                print(f"[WARNING] Unsupported modality: {selected_modality}")
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
                    print(f"[ERROR] Failed to show modality error: {e}")
                    self.shutdown_application()
                    
        except Exception as e:
            print(f"[ERROR] Fatal error in _create_dialog_delayed: {e}")
            print(f"[ERROR] Traceback: {traceback.format_exc()}")
            
            # Last resort: try to restart
            if not self.is_shutting_down:
                print("[DEBUG] Fatal error occurred, attempting restart in 5 seconds...")
                QTimer.singleShot(5000, self.start_new_session)

    def _create_main_window_safe(self, session_code, data_dir):
        """Safely create main window with comprehensive error handling"""
        try:
            print(f"[DEBUG] Creating main window for session: {session_code}")
            
            window = self.create_main_window(session_code, data_dir)
            if window:
                print("[DEBUG] Main window created successfully")
                
                # Setup window
                self.setup_window_signals(window)
                
                # Show window
                try:
                    window.show()
                    window.raise_()
                    window.activateWindow()
                    print("[DEBUG] Main window displayed")
                    
                    # Add to windows list
                    self.windows.append(window)
                    print(f"[DEBUG] Active windows count: {len(self.windows)}")
                    
                except Exception as e:
                    print(f"[ERROR] Failed to show main window: {e}")
                    window.deleteLater()
                    QTimer.singleShot(2000, self.start_new_session)
            else:
                print("[ERROR] Failed to create main window - retrying session")
                QTimer.singleShot(3000, self.start_new_session)
                
        except Exception as e:
            print(f"[ERROR] Error in _create_main_window_safe: {e}")
            print(f"[ERROR] Traceback: {traceback.format_exc()}")
            QTimer.singleShot(3000, self.start_new_session)
    
    def create_main_window(self, session_code, data_dir):
        """Create main window with error handling"""
        try:
            window = MainWindowSpect(session_code=session_code, data_root=data_dir)
            print(f"[DEBUG] Main window created successfully for session: {session_code}")
            return window
        except Exception as e:
            print(f"[ERROR] Failed to create main window: {e}")
            print(f"[ERROR] Traceback: {traceback.format_exc()}")
            
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
            
            print("[DEBUG] Logout requested")
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
                print(f"[ERROR] Error during logout: {e}")
                # Force restart session
                QTimer.singleShot(1000, self.start_new_session)
        
        # Connect logout signal if available
        try:
            if hasattr(window, 'logout_requested'):
                window.logout_requested.connect(handle_logout)
                print("[DEBUG] Logout signal connected")
        except Exception as e:
            print(f"[WARNING] Could not connect logout signal: {e}")
    
    def shutdown_application(self):
        """Gracefully shutdown the application"""
        # ✅ ADD: Prevent recursive calls (extra safety)
        if self.is_shutting_down:
            return
            
        self.is_shutting_down = True
        print("[DEBUG] Shutting down application...")
        
        # Close all windows
        for window in self.windows[:]:  # Copy list to avoid modification during iteration
            try:
                # ✅ ADD: Disconnect window signals to prevent additional triggers
                if hasattr(window, 'logout_requested'):
                    try:
                        window.logout_requested.disconnect()
                    except:
                        pass
                
                window.close()
                window.deleteLater()
            except Exception as e:
                print(f"[WARNING] Error closing window: {e}")
        
        self.windows.clear()
        
        # Quit application
        if self.app:
            self.app.quit()
        
    def run(self):
        """Main application run method"""
        print("[DEBUG] Starting TELPLASTINA...")
        
        # Apply post-import patches
        self.apply_post_import_patches()
        
        # Create Qt application
        if not self.create_application():
            return 1
        
        # ❌ REMOVED: aboutToQuit connection to prevent recursive loop
        # self.app.aboutToQuit.connect(self.shutdown_application)
        
        # Start the first session with longer delay for PyInstaller
        startup_delay = 1500 if hasattr(sys, '_MEIPASS') else 100
        print(f"[DEBUG] Starting session with {startup_delay}ms delay...")
        QTimer.singleShot(startup_delay, self.start_new_session)
        
        # Run the application event loop
        try:
            exit_code = self.app.exec()
            print(f"[DEBUG] Application exited with code: {exit_code}")
            return exit_code
        except Exception as e:
            print(f"[CRITICAL ERROR] Application crashed: {e}")
            print(f"[CRITICAL ERROR] Traceback: {traceback.format_exc()}")
            return 1

# ========== MAIN FUNCTION ==========
def main():
    """Main application entry point with comprehensive error handling"""
    try:
        # Validate Python version
        if sys.version_info < (3, 8):
            print(f"[ERROR] Python 3.8+ required, but {sys.version} found")
            sys.exit(1)
        
        # Check if running as PyInstaller bundle
        if hasattr(sys, '_MEIPASS'):
            print(f"[DEBUG] Running as PyInstaller bundle: {sys._MEIPASS}")
        else:
            print("[DEBUG] Running in development mode")
        
        # Create and run application
        bootstrap = ApplicationBootstrap()
        exit_code = bootstrap.run()
        
        # Clean exit
        print("[DEBUG] Application terminated normally")
        sys.exit(exit_code)
        
    except KeyboardInterrupt:
        print("\n[DEBUG] Application interrupted by user (Ctrl+C)")
        sys.exit(0)
    except Exception as e:
        print(f"[CRITICAL ERROR] Fatal error in main(): {e}")
        print(f"[CRITICAL ERROR] Traceback: {traceback.format_exc()}")
        
        # Try to show error dialog if Qt is available
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