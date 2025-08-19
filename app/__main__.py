# app/__main__.py - PRODUCTION READY VERSION
"""
Main application entry point - Production Ready
Handles PyInstaller compatibility and application startup
Version: 2.0 - Production Ready
"""

import sys
import os
from pathlib import Path
import traceback

# ========== CRITICAL: PYINSTALLER EARLY SETUP ==========
def setup_pyinstaller_environment():
    """Setup PyInstaller environment BEFORE any other imports"""
    if not hasattr(sys, '_MEIPASS'):
        print("[ENV] Development mode, using normal configuration")
        return
    
    print("[ENV] PyInstaller build detected, applying early configuration...")
    
    # Critical environment variables - set BEFORE any torch-related imports
    critical_env = {
        'TORCH_LOGS': '',
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
    }
    
    for key, value in critical_env.items():
        if key not in os.environ:
            os.environ[key] = value
    
    print(f"[ENV] Set {len(critical_env)} critical environment variables")

# Apply environment setup immediately
setup_pyinstaller_environment()

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
    from PySide6.QtWidgets import QApplication, QMessageBox
    from PySide6.QtCore import QTimer, QThread
    from PySide6.QtGui import QPalette, QColor, QFont
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
    
    def create_application(self):
        """Create and configure the Qt application"""
        try:
            self.app = QApplication(sys.argv)
            self.app.setStyle("Fusion")
            self.app.setPalette(make_light_palette())
            
            # Try to set Poppins font, fallback to system default
            try:
                self.app.setFont(QFont("Poppins"))
                print("[UI] Poppins font applied")
            except Exception:
                print("[UI] Using system default font")
            
            print("[DEBUG] Qt application created and configured")
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
        """Start a new session with doctor selection and error handling"""
        if self.is_shutting_down:
            return
        
        try:
            # Show doctor selection dialog
            dlg = DoctorSelectionDialog()
            if not dlg.exec():
                print("[DEBUG] Dialog cancelled, exiting application")
                self.shutdown_application()
                return

            session_code = dlg.selected_doctor_id
            selected_modality = dlg.selected_modality
            data_dir = Path("data")

            # Only PLANAR modality is supported
            if selected_modality == "Planar":
                print(f"[DEBUG] Starting PLANAR session with code: {session_code}")
                window = self.create_main_window(session_code, data_dir)
                if window:
                    self.setup_window_signals(window)
                    window.show()
                    self.windows.append(window)
                else:
                    # Failed to create window, try again
                    QTimer.singleShot(1000, self.start_new_session)
            else:
                QMessageBox.critical(
                    None, 
                    "Modality Not Supported", 
                    f"Modality '{selected_modality}' is not supported in this version.\n"
                    f"Only 'Planar' modality is currently available."
                )
                QTimer.singleShot(500, self.start_new_session)
                
        except Exception as e:
            print(f"[ERROR] Failed to start session: {e}")
            print(f"[ERROR] Traceback: {traceback.format_exc()}")
            
            # Show error dialog
            error_msg = (
                f"Failed to start application session.\n\n"
                f"Error: {str(e)}\n\n"
                f"Please check the console for more details."
            )
            QMessageBox.critical(None, "Application Error", error_msg)
            
            # Try to restart session after delay
            if not self.is_shutting_down:
                QTimer.singleShot(2000, self.start_new_session)
    
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
        self.is_shutting_down = True
        print("[DEBUG] Shutting down application...")
        
        # Close all windows
        for window in self.windows[:]:  # Copy list to avoid modification during iteration
            try:
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
        print("[DEBUG] Starting HotspotAnalyzer...")
        
        # Apply post-import patches
        self.apply_post_import_patches()
        
        # Create Qt application
        if not self.create_application():
            return 1
        
        # Setup application exit handler
        self.app.aboutToQuit.connect(self.shutdown_application)
        
        # Start the first session
        QTimer.singleShot(100, self.start_new_session)
        
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