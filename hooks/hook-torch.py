
from PyInstaller.utils.hooks import collect_all, collect_submodules

# Collect all torch modules
datas, binaries, hiddenimports = collect_all('torch')

# Add specific torch modules that might be missing
hiddenimports += [
    'torch._dynamo',
    'torch._dynamo.config',
    'torch._dynamo.convert_frame',
    'torch._dynamo.eval_frame',
    'torch._dynamo.resume_execution', 
    'torch._dynamo.symbolic_convert',
    'torch._dynamo.trace_rules',
    'torch._dynamo.variables',
    'torch._dynamo.variables.base',
    'torch._dynamo.guards',
    'torch._dynamo.polyfills',
    'torch._dynamo.polyfills.fx',
    'torch._dynamo.polyfills.loader',
    'torch._functorch',
    'torch._inductor',
    'torch._C._nn',
    'torch._C._autograd',
    'torch._C._te',
    'torch._C._fft',
    'torch._C._linalg',
    'torch._C._sparse',
    'torch._C._special',
    'torch._ops',
    'torch._ops.ops',
    'torch.utils.checkpoint',
    'torch.testing._internal',
    'torch.testing._internal.logging_tensor',
    'torch.testing._internal.common_utils',
    'torch.testing._internal.common_dtype',
    'torch.testing._internal.common_device_type',
]

# Exclude triton completely
excludedimports = ['triton', 'triton.*']

# Add nnUNet related modules  
hiddenimports += [
    'nnunetv2',
    'dynamic_network_architectures',
    'batchgenerators',
    'acvl_utils',
]

# Add ultralytics modules
hiddenimports += [
    'ultralytics',
    'ultralytics.models',
    'ultralytics.models.yolo',
    'ultralytics.utils',
    'ultralytics.engine',
    'ultralytics.nn',
]

# Exclude tests and development files
excludedimports += [
    'torch.test', 
    'torch.testing',
    'nnunetv2.tests',
    'ultralytics.tests',
]

print(f"Torch hook: collected {len(hiddenimports)} hidden imports")
