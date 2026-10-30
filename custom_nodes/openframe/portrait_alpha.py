"""Portable CPU ViTMatte refinement of explicit native person masks.

Reuses OpenFrame's semantic-matte12px trimap/locked-interior policy. Apache2
ViTMatte revision bf486d01a7d9e3dbcc8400f7942835caf0eaf76e; no RGB mutation,
remote service, platform-specific memory API, installation or model download.
"""
from functools import lru_cache
from pathlib import Path
import importlib.util
import numpy as np
import torch
import folder_paths
import comfy.model_management
from .sam_runtime_config import VITMATTE_REVISION


def portrait_alpha_available():
    root=Path(folder_paths.models_dir)/'matting/vitmatte'
    return importlib.util.find_spec('transformers') is not None and all((root/name).is_file()
        for name in ('pytorch_model.bin','config.json','preprocessor_config.json'))


@lru_cache(maxsize=1)
def _load(root):
    from transformers import VitMatteForImageMatting, VitMatteImageProcessor
    return (VitMatteImageProcessor.from_pretrained(root,local_files_only=True),
        VitMatteForImageMatting.from_pretrained(root,local_files_only=True).cpu().eval())


def portrait_trimap(coarse):
    """Shared fixed12px trimap, including strict eroded-interior/exterior locks."""
    import cv2
    kernel=np.ones((25,25),np.uint8)
    foreground=cv2.erode(coarse.astype(np.uint8),kernel,borderType=cv2.BORDER_CONSTANT,borderValue=0).astype(bool)
    support=cv2.dilate(coarse.astype(np.uint8),kernel).astype(bool)
    trimap=np.zeros(coarse.shape,np.uint8);trimap[support]=128;trimap[foreground]=255
    return trimap,foreground,support


def refine_image_alpha(image, mask, *, quantize_16_bit=True):
    """One IMAGE+MASK →soft MASK and provenance; preserves the input RGB."""
    import transformers
    if image.shape[0]!=1 or image.shape[-1]!=3 or max(image.shape[1:3])>1920 or tuple(mask.shape)!=tuple(image.shape[:3]):
        raise ValueError('Alpha refinement requires one RGB image and its native-size mask, at most1920 pixels per side')
    if not portrait_alpha_available():
        raise ValueError('Install the pinned ViTMatte files and ComfyUI Transformers dependency; no automatic download is attempted')
    comfy.model_management.throw_exception_if_processing_interrupted()
    rgb=np.clip(image[0].detach().cpu().numpy()*255,0,255).astype(np.uint8)
    coarse=mask[0].detach().cpu().numpy()>.5
    if not coarse.any(): raise ValueError('No person detected; source-preserving finishing cannot proceed')
    trimap,foreground,support=portrait_trimap(coarse)
    processor,model=_load(str(Path(folder_paths.models_dir)/'matting/vitmatte'))
    threads=torch.get_num_threads()
    try:
        torch.set_num_threads(min(threads,8))
        with torch.inference_mode():
            alpha=model(**processor(images=rgb,trimaps=trimap,return_tensors='pt')).alphas[0,0,:rgb.shape[0],:rgb.shape[1]].float().clamp(0,1).numpy()
        alpha[foreground]=1;alpha[~support]=0
        # Match the16-bit alpha retained and reviewed in the bounded proof.
        if quantize_16_bit:
            alpha=np.rint(alpha*65535).astype(np.float32)/65535
    finally:
        torch.set_num_threads(threads)
    return torch.from_numpy(alpha.copy())[None], {
        'method':'Native person mask →12px trimap →CPU ViTMatte →soft alpha',
        'vitmatte_revision':VITMATTE_REVISION,'transformers':transformers.__version__,
        'size':[image.shape[2],image.shape[1]],'mask_pixels':int(coarse.sum()),
        'alpha_over_half':int((alpha>=.5).sum()),'rgb_unchanged':True,
        'alpha_quantization_bits':16 if quantize_16_bit else None,
    }


class OpenFrameImageAlpha:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'image': ('IMAGE',), 'mask': ('MASK', {
            'openframe_portrait_alpha_available':portrait_alpha_available()})}}
    RETURN_TYPES=('MASK',)
    FUNCTION='refine'
    CATEGORY='OpenFrame/Image'

    def refine(self,image,mask):
        alpha,metadata=refine_image_alpha(image,mask)
        return {'result':(alpha,), 'ui':{'openframe_image_alpha':[metadata]}}


class OpenFramePortraitAlphas:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'source': ('IMAGE',), 'generated': ('IMAGE',),
            'source_mask': ('MASK', {'openframe_portrait_alpha_available':portrait_alpha_available()}),
            'generated_mask': ('MASK',)}}
    RETURN_TYPES=('MASK','MASK')
    RETURN_NAMES=('source_alpha','generated_alpha')
    FUNCTION='refine'
    CATEGORY='OpenFrame/Image'

    def refine(self,source,generated,source_mask,generated_mask):
        if source.shape!=generated.shape:
            raise ValueError('Source/generated portrait canvases must match without resizing')
        source_alpha,source_meta=refine_image_alpha(source,source_mask)
        generated_alpha,generated_meta=refine_image_alpha(generated,generated_mask)
        return {'result':(source_alpha,generated_alpha),'ui':{'openframe_portrait_alpha':[{
            'source':source_meta,'generated':generated_meta,
            'composite':'Native source/generated alpha multiplication; original-background restoration',
            'limits':'No geometry warp or exact identity guarantee; fractional edges mix old and new lighting',
        }]}}
