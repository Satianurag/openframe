"""Run with the ComfyUI Python environment and OpenFrame on PYTHONPATH."""
import json
from pathlib import Path
import subprocess
import tempfile
import sys
sys.argv = [sys.argv[0], '--cpu']
import comfy.options
comfy.options.enable_args_parsing()
import numpy as np
import torch
from PIL import Image
import folder_paths
from custom_nodes.openframe.nodes import OpenFrameVideoInput, OpenFrameSaveVideo, OpenFrameGreenFill, OpenFramePadForRefinement, _frames, _match_plate_lighting
from custom_nodes.openframe.media import composite_frame


def validate():
    with tempfile.TemporaryDirectory(prefix='openframe-media-check-') as directory:
        base = Path(directory)
        (base/'input').mkdir(); (base/'output').mkdir(); (base/'temp').mkdir()
        folder_paths.set_input_directory(str(base/'input'))
        folder_paths.set_output_directory(str(base/'output'))
        folder_paths.set_temp_directory(str(base/'temp'))
        frames = []
        yy, xx = np.mgrid[:96,:128]
        background = np.stack([40+xx//2,50+yy,60+xx//3],axis=-1).astype(np.uint8)
        for i in range(25):
            frame = background.copy()
            tile = np.tile(np.array([[110,240],[240,110]],dtype=np.uint8),(12,12))
            frame[32:56,20+i:44+i,0] = tile
            frame[32:56,20+i:44+i,1:] = 20
            frames.append(frame)
        source=base/'input/source.mkv'
        subprocess.run(['ffmpeg','-v','error','-f','rawvideo','-pix_fmt','rgb24','-s','128x96','-r','16','-i','pipe:0','-f','lavfi','-i','sine=frequency=440:sample_rate=48000:duration=1.5625','-map','0:v','-map','1:a','-c:v','ffv1','-c:a','pcm_s16le','-shortest',str(source)],input=np.stack(frames).tobytes(),check=True)
        mask=np.zeros((96,128),np.uint8); mask[32:56,24:48]=255
        Image.fromarray(mask).save(base/'input/mask.png')
        load=OpenFrameVideoInput().load
        images,generation,blend=load('source.mkv',128,96,9,16,'mask.png',True,2,2,.25,'flow')
        assert images.shape==(9,96,128,3)
        assert generation.shape==blend.shape==(9,96,128)
        np.testing.assert_allclose(images[0].numpy()*255,frames[4],atol=.001)
        actual=blend[-1].numpy()>0
        expected=np.zeros_like(actual);expected[32:56,32:56]=True
        iou=float((actual & expected).sum()/(actual | expected).sum())
        assert iou>.7, f'Optical-flow temporal mask IoU {iou}'
        static=load('source.mkv',128,96,9,16,'mask.png',False,2,2,.25,'static')[2]
        assert torch.equal(static[0],static[-1])
        assert torch.count_nonzero(static[0][torch.from_numpy(mask==0)])==0
        inward=load('source.mkv',128,96,9,16,'mask.png',False,2,2,.25,'static',feather_method='inward')[2]
        assert inward[0,32,24] == 0 and static[0,32,24] > 0
        assert inward[0,35,27] == 1
        assert torch.count_nonzero(inward[0][torch.from_numpy(mask==0)]) == 0
        new_images,new_generation,new_blend=load('source.mkv',128,96,9,16,'mask.png',False,2,2,.25,'static',feather_method='smooth-inward')
        old_images,old_generation,_=load('source.mkv',128,96,9,16,'mask.png',False,2,2,.25,'static',feather_method='inward')
        assert torch.equal(new_images,old_images) and torch.equal(new_generation,old_generation)
        assert torch.count_nonzero(new_blend[0][torch.from_numpy(mask==0)]) == 0
        generator=torch.Generator().manual_seed(73)
        generated=torch.rand((96,128,3),generator=generator)*1.2-.1
        opacity=torch.rand((96,128),generator=generator)
        expected_pixels=((generated*opacity[...,None]+images[0]*(1-opacity[...,None])).clamp(0,1).numpy()*255).round().astype(np.uint8)
        np.testing.assert_array_equal(composite_frame(generated.numpy(),images[0].numpy(),opacity.numpy()),expected_pixels)
        assert OpenFrameVideoInput.INPUT_TYPES()['optional']['feather_method'][1]['default'] == 'gaussian'
        padded,padded_mask=OpenFramePadForRefinement().pad(images,generation)
        assert padded.shape==(9,128,128,3)
        assert torch.equal(padded[:,:96],images)
        assert torch.count_nonzero(padded_mask[:,96:])==0
        filled=OpenFrameGreenFill().fill(images,generation)[0]
        assert torch.equal(filled[generation==0],images[generation==0])
        saved=OpenFrameSaveVideo().save(torch.ones_like(images),16,9,'../../check',True,True,'source.mkv',.25,images,blend,export_mask=True)
        output=Path(saved['result'][0])
        assert output.is_relative_to(base/'output')
        info=json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames','-show_streams','-of','json',str(output)]))
        video=next(s for s in info['streams'] if s['codec_type']=='video')
        assert (int(video['width']),int(video['height']),int(video['nb_read_frames']))==(128,96,9)
        assert any(s['codec_type']=='audio' for s in info['streams'])
        decoded=_frames(output,128,96,16,9)
        outside=(blend.numpy()==0)
        # H264 quantization changes encoded pixels; the pre-encode plate is exact.
        mean_error=float(np.abs(decoded.astype(float)-images.numpy()*255)[outside].mean())
        assert mean_error<3,mean_error
        assert len(saved['ui']['videos'])==2
        assert saved['ui']['videos'][1]['role']=='mask'
        silent=base/'input/silent.mkv'
        subprocess.run(['ffmpeg','-v','error','-i',str(source),'-map','0:v:0','-c:v','copy','-an',str(silent)],check=True)
        waveform=torch.sin(torch.arange(9000)*(.2)).reshape(1,1,-1).to(torch.bfloat16)
        generated=OpenFrameSaveVideo().save(images,16,9,'generated-audio',False,True,'silent.mkv',audio={'waveform':waveform,'sample_rate':16000},export_mask=False)
        generated_probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',generated['result'][0]]))
        assert any(s['codec_type']=='audio' for s in generated_probe['streams'])
        # A changed mask position must not carry a brightness offset into the plate.
        colour_errors = []
        biased = np.clip(background.astype(float) + 25, 0, 255).astype(np.uint8)
        for index in range(9):
            selected = np.zeros((96, 128), np.float32)
            selected[27:61, 19+index:53+index] = 1
            plate = frames[index+4]
            matched = _match_plate_lighting(biased, plate, selected)
            restored = np.where(selected[..., None] > 0, matched, plate)
            assert np.array_equal(restored[selected == 0], plate[selected == 0])
            colour_errors.append(float(np.abs(matched.astype(float)-background)[selected > 0].mean()))
        assert max(colour_errors) < 3, colour_errors
        assert np.array_equal(_match_plate_lighting(biased, background, np.zeros((96,128))), background)
        assert np.array_equal(_match_plate_lighting(biased, background, np.ones((96,128))), biased)
        inputs = OpenFrameSaveVideo.INPUT_TYPES()
        assert 'match_lighting' not in inputs['required']
        assert inputs['optional']['match_lighting'][1]['default'] is False
        try:
            load('source.mkv',128,96,25,16,trim_start=1)
        except ValueError as exc:
            assert 'Source supplies' in str(exc)
        else:
            raise AssertionError('Short source was silently repeated')
        return {'source_trim_frame':4,'frames':9,'dimensions':[128,96],'audio_preserved':True,'generated_audio_fallback_for_silent_source':True,'bfloat16_audio_supported':True,'refinement_padding_preserves_original_pixels':True,'outside_encoded_mean_error_255':mean_error,'flow_mask_last_frame_iou':iou,'static_mask_stable':True,'short_source_rejected':True,'mask_video_exported':True,'gradient_domain_moving_mask_max_error_255':max(colour_errors),'legacy_colour_match_default_off':True,'inward_feather_zero_at_boundary':True,'legacy_feather_default_preserved':True}

if __name__=='__main__':
    print(json.dumps(validate(),indent=2))
