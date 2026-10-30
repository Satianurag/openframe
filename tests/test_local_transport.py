"""Actual HTTP adapter against a deterministic in-memory Comfy server; no inference."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import httpx
from engine.runner import _run_local
from engine.workflows import normalize_request


class LocalMediaTransport(unittest.TestCase):
    def run_transport(self, request, groups, inputs):
        uploads=[];graphs=[];downloads=[]
        def server(message):
            if message.url.path=='/upload/image':
                uploads.append(message.content)
                return httpx.Response(200,json={'name':f'input-{len(uploads)}'+('.wav' if b'.wav"' in message.content else '.png'),'subfolder':'isolated'})
            if message.url.path=='/prompt':
                import json
                graphs.append(json.loads(message.content)['prompt'])
                return httpx.Response(200,json={'prompt_id':'isolated-prompt'})
            if message.url.path.startswith('/history/'):
                return httpx.Response(200,json={'isolated-prompt':{'status':{'completed':True},'outputs':{'preview':{'images':[{'filename':'ignore.png'}]},'save':groups}}})
            if message.url.path=='/view':
                filename=message.url.params['filename'];downloads.append(filename)
                return httpx.Response(200,content=('bytes:'+filename).encode())
            if message.url.path=='/object_info':return httpx.Response(200,json={})
            raise AssertionError(message.url)
        client_type=httpx.Client
        with tempfile.TemporaryDirectory(prefix='openframe-transport-test-') as folder:
            root=Path(folder);output=root/'result';output.mkdir();assets={}
            for role,suffix in inputs.items():
                source=root/(role+suffix);source.write_bytes(b'isolated-upload');assets[role]=str(source)
            normalized=normalize_request(request);normalized['job_id']='isolated-job'
            with patch('engine.runner.httpx.Client',side_effect=lambda **kwargs:client_type(transport=httpx.MockTransport(server),**kwargs)),patch('websocket.create_connection',side_effect=OSError('Use history transport')),patch('engine.runner.time.sleep'),patch('engine.export.to_ui_workflow',side_effect=ValueError('No live schema in transport fixture')):
                result=_run_local(normalized,assets,output,{'comfy_url':'http://test.invalid'},lambda *args:None,lambda:False)
            payloads=[Path(item['path']).read_bytes() for item in result['outputs']]
            self.assertTrue(all(Path(item['path']).parent==output for item in result['outputs']))
        return result,uploads,graphs,downloads,payloads

    def test_image_batch_preserves_reference_uploads_and_ignores_previews(self):
        result,uploads,graphs,downloads,payloads=self.run_transport(
            {'model_id':'flux-klein-4b','effect_id':'edit-image','prompt':'Adjust lighting','width':256,'height':256,'batch_size':2},
            {'images':[{'filename':'../first.png','subfolder':'batch'},{'filename':'second.png','subfolder':'batch'}]},
            {'source':'.png','reference_0':'.png','reference_1':'.png'})
        self.assertEqual(len(uploads),3)
        self.assertEqual([item['kind'] for item in result['outputs']],['image','image'])
        self.assertEqual(downloads,['../first.png','second.png'])
        self.assertEqual(payloads,[b'bytes:../first.png',b'bytes:second.png'])
        self.assertEqual(graphs[0]['image']['inputs']['image'],'isolated/input-1.png')
        self.assertEqual(graphs[0]['reference_1']['inputs']['image'],'isolated/input-3.png')
        self.assertIn('No live schema',result['metadata']['ui_export_error'])

    def test_speech_singular_audio_group_downloads_wav_as_audio(self):
        result,uploads,graphs,downloads,payloads=self.run_transport(
            {'model_id':'kokoro-82m','effect_id':'generate-speech','prompt':'Actual adapter contract.'},
            {'audio':[{'filename':'spoken.wav','role':'result','type':'output'}]}, {})
        self.assertEqual(result['outputs'][0]['kind'],'audio')
        self.assertEqual(result['outputs'][0]['role'],'result')
        self.assertEqual(payloads,[b'bytes:spoken.wav']);self.assertEqual(uploads,[])
        self.assertEqual(graphs[0]['save']['class_type'],'OpenFrameSaveAudio')

    def test_speech_capability_requires_matching_audio_encoder_and_native_nodes(self):
        from engine.runner import check_provider
        classes={name:{} for name in ['OpenFrameSaveVideo','OpenFrameVideoInput','OpenFrameGreenFill','OpenFramePadForRefinement','AudioEncoderEncode','WanSoundImageToVideo']}
        classes['UNETLoader']={'input':{'required':{'unet_name':[['wan2.2_s2v_14B_bf16.safetensors']]}}}
        classes['AudioEncoderLoader']={'input':{'required':{'audio_encoder_name':[[]]}}}
        def server(request):return httpx.Response(200,json=classes if request.url.path=='/object_info' else {'devices':[]})
        client_type=httpx.Client
        with patch('engine.runner.httpx.Client',side_effect=lambda **kwargs:client_type(transport=httpx.MockTransport(server),**kwargs)):
            self.assertNotIn('wan-s2v',check_provider('local',{'comfy_url':'http://test.invalid'})['models'])
            classes['AudioEncoderLoader']['input']['required']['audio_encoder_name'][0].append('wav2vec2_large_english_fp16.safetensors')
            self.assertIn('wan-s2v',check_provider('local',{'comfy_url':'http://test.invalid'})['models'])
            classes.pop('AudioEncoderEncode')
            self.assertNotIn('wan-s2v',check_provider('local',{'comfy_url':'http://test.invalid'})['models'])
