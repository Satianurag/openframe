"""Exercise real SAM2 tracking with the available Comfy device and pinned checkpoint."""
import sys,time,json
sys.argv=['sam2-check']
import comfy.options
comfy.options.enable_args_parsing()
from pathlib import Path
import numpy as np
import folder_paths
folder_paths.models_dir=str(Path('artifacts/validation/comfy/models').resolve())
folder_paths.set_temp_directory(str(Path('artifacts/validation/comfy/temp').resolve()))
Path(folder_paths.get_temp_directory()).mkdir(exist_ok=True)
from custom_nodes.openframe.nodes import _sam2_masks
import comfy.model_management
frames=[]
yy,xx=np.mgrid[:96,:128]
for i in range(5):
    im=np.full((96,128,3),55,np.uint8)
    obj=(xx-(35+2*i))**2+(yy-48)**2<=15**2
    im[obj]=[220,40,30]
    frames.append(im)
first=((xx-35)**2+(yy-48)**2<=15**2).astype(np.float32)
start=time.monotonic()
masks=_sam2_masks(np.stack(frames),first)
expected=(xx-43)**2+(yy-48)**2<=15**2
last=masks[-1]>.5
iou=float((last&expected).sum()/(last|expected).sum())
assert masks.shape==(5,96,128)
assert np.array_equal(masks[0],first)
assert iou>.7,iou
result={'device':str(comfy.model_management.get_torch_device()),'frames':5,'last_frame_iou':iou,'elapsed_seconds':round(time.monotonic()-start,2),'first_mask_exact':True}
Path('artifacts/validation/sam2-check.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
