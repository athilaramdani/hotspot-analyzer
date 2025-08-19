# Buat file: hooks/hook-nnunetv2.py
"""
PyInstaller hook for nnUNetv2 to handle dynamic trainer class imports
"""

from PyInstaller.utils.hooks import collect_all, collect_submodules

# Collect all nnunetv2 resources
datas, binaries, hiddenimports = collect_all('nnunetv2')

# ✅ CRITICAL: Add specific trainer classes yang di-import secara dynamic
trainer_classes = []
try:
    # Try to import base trainer
    import nnunetv2.training.nnUNetTrainer.nnUNetTrainer
    trainer_classes.append('nnunetv2.training.nnUNetTrainer.nnUNetTrainer')
except ImportError:
    pass

hiddenimports.extend(trainer_classes)

# ✅ Add semua training submodules
training_modules = collect_submodules('nnunetv2.training')
hiddenimports.extend(training_modules)

# ✅ Add modules yang dibutuhkan untuk inference
inference_modules = [
    'nnunetv2.inference.predict_from_raw_data',
    'nnunetv2.inference.sliding_window_prediction',
    'nnunetv2.imageio',
    'nnunetv2.utilities.file_path_utilities',
    'nnunetv2.utilities.utils',
    'nnunetv2.utilities.plans_handling',
    'nnunetv2.utilities.label_handling',
    'nnunetv2.configuration',
    'nnunetv2.paths'
]

hiddenimports.extend(inference_modules)

# ✅ Add dependencies
dependency_modules = collect_submodules('dynamic_network_architectures')
hiddenimports.extend(dependency_modules)

dependency_modules = collect_submodules('batchgenerators')
hiddenimports.extend(dependency_modules)

try:
    dependency_modules = collect_submodules('acvl_utils')
    hiddenimports.extend(dependency_modules)
except:
    pass

print(f"[HOOK-NNUNET] Added {len(hiddenimports)} hidden imports for nnUNetv2")
print(f"[HOOK-NNUNET] Trainer classes included for dynamic loading")

# ✅ Exclude test modules
excludedimports = [
    'nnunetv2.tests',
    'nnunetv2.testing',
    'nnunetv2.evaluation.test'
]