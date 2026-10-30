"""Exact released Qwen inference followed by explicit native portrait finishing."""
import json
from pathlib import Path

# Comfy79cf native FluxKontextImageScale resolution list and nearest-ratio rule.
KONTEXT_SIZES = [(672,1568),(688,1504),(720,1456),(752,1392),(800,1328),(832,1248),
    (880,1184),(944,1104),(1024,1024),(1104,944),(1184,880),(1248,832),
    (1328,800),(1392,752),(1456,720),(1504,688),(1568,672)]

def portrait_relight_size(width, height):
    if not width or not height:
        raise ValueError('Portrait relighting requires the source dimensions')
    _, w, h = min((abs(width / height - w / h), w, h) for w, h in KONTEXT_SIZES)
    return w, h

def validate_portrait_relight(r):
    if r['task'] != 'image-edit' or r['effect_id'] != 'relight-image':
        raise ValueError('Portrait Relight is only for Relight Image')
    if any(r.get(k) for k in ('reference_asset_id','reference_asset_ids','mask_asset_id','image_layout','character_adapter_id','audio_asset_id')) or r.get('image_preservation','none') != 'none':
        raise ValueError('Portrait Relight uses one portrait; its foreground masks are computed by the exported workflow')
    if r['steps'] != 4 or r['guidance'] != 1 or r['strength'] != 1 or r['batch_size'] != 1 or r.get('negative_prompt','').strip():
        raise ValueError('The released Portrait Relight recipe requires four steps, CFG1, denoise1, one image and an empty negative prompt')
    if r.get('source_width') and r.get('source_height') and (r['width'],r['height']) != portrait_relight_size(r['source_width'],r['source_height']):
        raise ValueError('Use the native source-derived portrait canvas')

def build_portrait_relight_workflow(r, assets=None):
    graph=json.loads(Path(__file__).with_name('portrait_relight_graph.json').read_text())
    graph['image']['inputs']['image']=(assets or {}).get('source','source.png')
    graph['caption']['inputs']['value']=r['prompt']
    graph['sample']['inputs']['seed']=r['seed']
    prefix=str(r.get('job_id','OpenFrame-Portrait-Relight'))
    graph['save_uncomposited']['inputs']['filename_prefix']=prefix+'-raw'
    def node(name, kind, **inputs): graph[name]={'class_type':kind,'inputs':inputs}
    node('sam','CheckpointLoaderSimple',ckpt_name='sam3.1_multiplex_fp16.safetensors')
    node('subject','CLIPTextEncode',clip=['sam',1],text='human')
    for name, rgb in [('source',['source_scale',0]),('generated',['decode',0])]:
        node(name+'_track','SAM3_VideoTrack',images=rgb,model=['sam',0],conditioning=['subject',0],detection_threshold=.5,max_objects=1,detect_interval=1)
        node(name+'_colors','SCAIL2ColoredMask',driving_track_data=[name+'_track',0],ref_track_data=[name+'_track',0],object_indices='',sort_by='left_to_right',replacement_mode=True)
        node(name+'_mask','ImageToMask',image=[name+'_colors',1],channel='blue')
    node('portrait_alpha','OpenFramePortraitAlphas',source=['source_scale',0],generated=['decode',0],source_mask=['source_mask',0],generated_mask=['generated_mask',0])
    node('support','MaskComposite',destination=['portrait_alpha',0],source=['portrait_alpha',1],x=0,y=0,operation='multiply')
    node('composite','ImageCompositeMasked',destination=['source_scale',0],source=['decode',0],mask=['support',0],x=0,y=0,resize_source=False)
    final=['composite',0]
    if r.get('image_brightness',0):
        node('image_brightness','OpenFrameImageBrightness',image=final,brightness=float(r['image_brightness']))
        final=['image_brightness',0]
    node('save','SaveImage',images=final,filename_prefix=prefix)
    return graph
