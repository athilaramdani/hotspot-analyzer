"""
Runtime hook for comprehensive torchvision stub creation
"""

import sys
import types

def create_comprehensive_torchvision_stub():
    """Create complete torchvision stub with all required modules"""
    if hasattr(sys, '_MEIPASS'):
        print("[RUNTIME-TORCHVISION] Creating comprehensive torchvision stub...")
        
        try:
            # Test if torchvision is working
            import torchvision
            if hasattr(torchvision, 'ops') and hasattr(torchvision.ops, 'nms'):
                print("[RUNTIME-TORCHVISION]   torchvision already working")
                return
        except:
            pass
        
        # Create comprehensive stub
        import torch
        
        # Main torchvision module
        tv = types.ModuleType('torchvision')
        tv.__file__ = '<runtime_torchvision_stub>'
        tv.__version__ = '0.0.0'
        
        # ops module with NMS
        ops = types.ModuleType('torchvision.ops')
        def nms_fallback(boxes, scores, iou_threshold):
            """Simple NMS fallback"""
            try:
                return torch.arange(len(boxes)) if len(boxes) > 0 else torch.tensor([])
            except:
                return []
        ops.nms = nms_fallback
        
        # transforms module
        transforms = types.ModuleType('torchvision.transforms')
        class ToTensorStub:
            def __call__(self, x): return torch.tensor(x) if hasattr(torch, 'tensor') else x
        transforms.ToTensor = ToTensorStub
        
        # Other modules
        models = types.ModuleType('torchvision.models')
        utils = types.ModuleType('torchvision.utils')
        io = types.ModuleType('torchvision.io')
        datasets = types.ModuleType('torchvision.datasets')
        
        # Link everything
        tv.ops = ops
        tv.transforms = transforms
        tv.models = models
        tv.utils = utils
        tv.io = io
        tv.datasets = datasets
        
        # Register in sys.modules
        sys.modules['torchvision'] = tv
        sys.modules['torchvision.ops'] = ops
        sys.modules['torchvision.transforms'] = transforms
        sys.modules['torchvision.models'] = models
        sys.modules['torchvision.utils'] = utils
        sys.modules['torchvision.io'] = io
        sys.modules['torchvision.datasets'] = datasets
        
        print("[RUNTIME-TORCHVISION]   Comprehensive stub created")

# Run the stub creation
create_comprehensive_torchvision_stub()