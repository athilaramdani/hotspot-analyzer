
# Hook for scipy._lib._docscrape
from PyInstaller.utils.hooks import collect_submodules

# Collect all pydoc related modules
hiddenimports = [
    'pydoc',
    'pydoc_data',
    'pydoc_data.topics',
    'textwrap',
    'linecache',
    'tokenize',
    'keyword',
    'pkgutil',
    'warnings',
    'collections.abc',
    'inspect',
    'doctest'
]

# Also collect scipy._lib submodules
hiddenimports += collect_submodules('scipy._lib')
