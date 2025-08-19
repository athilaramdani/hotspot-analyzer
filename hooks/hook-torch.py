
from PyInstaller.utils.hooks import collect_all, collect_submodules

# Kumpulkan semua resource utama dari torch
datas, binaries, hiddenimports = collect_all('torch')

# Pastikan torch.testing (termasuk _comparison) ikut ter-bundle
try:
    hiddenimports += collect_submodules('torch.testing')
except Exception:
    pass

# (opsional) functorch kadang lazy-load; aman untuk ikutkan submodules-nya
try:
    hiddenimports += collect_submodules('torch._functorch')
except Exception:
    pass

# Exclude triton sepenuhnya
excludedimports = ['triton', 'triton.*']

# Tambahan modul terkait nnUNet
hiddenimports += [
    'nnunetv2',
    'dynamic_network_architectures',
    'batchgenerators',
    'acvl_utils',
]

# Tambahan modul ultralytics/YOLO
hiddenimports += [
    'ultralytics',
    'ultralytics.models',
    'ultralytics.models.yolo',
    'ultralytics.utils',
    'ultralytics.engine',
    'ultralytics.nn',
]

# Exclude paket test (JANGAN exclude torch.testing)
excludedimports += [
    'torch.test',
    'nnunetv2.tests',
    'ultralytics.tests',
]

print(f"Torch hook: collected {len(hiddenimports)} hidden imports, {len(datas)} datas, {len(binaries)} binaries")
