"""
Runtime hook for XGBoost to handle missing VERSION file
"""

import sys
import os
import logging
def fix_xgboost_version():
    """Create missing XGBoost VERSION file at runtime"""
    if hasattr(sys, '_MEIPASS'):
        try:
            # Find xgboost directory in the bundle
            xgb_paths = [
                os.path.join(sys._MEIPASS, 'xgboost'),
                os.path.join(os.path.dirname(sys.executable), '_internal', 'xgboost')
            ]
            
            for xgb_path in xgb_paths:
                if os.path.exists(xgb_path):
                    version_file = os.path.join(xgb_path, 'VERSION')
                    
                    if not os.path.exists(version_file):
                        # Create VERSION file with default version
                        try:
                            with open(version_file, 'w') as f:
                                f.write('2.0.0')  # Default version
                            logging.info(f"[RUNTIME-XGBOOST] Created VERSION file: {version_file}")
                        except Exception as e:
                            logging.info(f"[RUNTIME-XGBOOST] Failed to create VERSION file: {e}")
                    else:
                        logging.info(f"[RUNTIME-XGBOOST] VERSION file already exists: {version_file}")
                    break
            else:
                logging.info("[RUNTIME-XGBOOST] XGBoost directory not found")
                
        except Exception as e:
            logging.info(f"[RUNTIME-XGBOOST] Error: {e}")

# Run the fix
fix_xgboost_version()