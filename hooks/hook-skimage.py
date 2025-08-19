
# Hook for scikit-image
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# Collect all skimage submodules
hiddenimports = collect_submodules('skimage')
datas = collect_data_files('skimage')

# Add specific modules that might be missing
hiddenimports += [
    'skimage.filters.thresholding',
    'skimage._shared.utils',
    'skimage._shared.coord',
    'lazy_loader',
]
