"""Isolated orchestration regressions; real FFmpeg/Pillow, explicitly stubbed inference."""
import copy
import io
import json
import shutil
import subprocess
import time
import unittest
import wave
import zipfile
from pathlib import Path
from unittest.mock import patch

import test_backend as base
from backend.store import Store
from engine.runner import JobCancelled
from engine.workflows import build_workflow


class AppWorkflowTests(unittest.TestCase):
    def setUp(self):
        base.BackendIntegration.setUp(self)
        self.asset_roles = []

    tearDown = base.BackendIntegration.tearDown
    tearDownClass = classmethod(base.BackendIntegration.tearDownClass.__func__)
    request = base.BackendIntegration.request
    upload_video = base.BackendIntegration.upload_video
    upload_mask = base.BackendIntegration.upload_mask
    wait = base.BackendIntegration.wait

    @classmethod
    def setUpClass(cls):
        base.BackendIntegration.setUpClass.__func__(cls)
        cls.render_video = Path(cls.fixture_dir.name) / 'nine.mp4'
        subprocess.run(['ffmpeg','-nostdin','-v','error','-i',str(cls.video),'-frames:v','9','-an','-c:v','libx264','-threads','1',str(cls.render_video)],check=True,timeout=30)
        audio=io.BytesIO()
        with wave.open(audio,'wb') as output:
            output.setnchannels(1);output.setsampwidth(2);output.setframerate(8000);output.writeframes(b'\0\0'*16000)
        cls.recording=audio.getvalue()
        longer=io.BytesIO()
        with wave.open(longer,'wb') as output:
            output.setnchannels(1);output.setsampwidth(2);output.setframerate(8000);output.writeframes(b'\0\0'*48000)
        cls.speech_recording=longer.getvalue()

    def fake_runner(self, request, assets, output_dir, settings, on_progress, is_cancelled):
        self.calls.append(copy.deepcopy(request));self.started.set()
        self.asset_roles.append(sorted(assets))
        if request['prompt']=='block until cancelled' and sum(item['prompt']=='block until cancelled' for item in self.calls)==1:
            deadline=time.monotonic()+5
            while time.monotonic()<deadline and not is_cancelled():time.sleep(.01)
            if is_cancelled():raise JobCancelled('Isolated cancellation')
            raise RuntimeError('Cancellation did not arrive')
        if request['prompt']=='fail once' and sum(item['prompt']=='fail once' for item in self.calls)==1:
            raise RuntimeError('Deliberate first-attempt failure')
        on_progress(.5,'Explicit inference test double')
        from PIL import Image
        outputs=[]
        if request['task']=='text-to-speech':
            target=Path(output_dir)/'speech.wav';target.write_bytes(self.recording)
            outputs=[{'path':str(target),'kind':'audio','role':'result'}]
        elif request['task'] in {'text-to-image','image-edit','background-removal'}:
            for index in range(request.get('batch_size',1)):
                target=Path(output_dir)/f'image-{index}.png'
                Image.new('RGBA',(256,256),(30+index,60,90,128)).save(target)
                outputs.append({'path':str(target),'kind':'image','role':'result'})
        else:
            target=Path(output_dir)/'result.mp4';shutil.copyfile(self.render_video,target)
            outputs=[{'path':str(target),'kind':'video','role':'result'}]
        workflow={} if request.get('task')=='reference-video' else build_workflow(request,{role:Path(item).name for role,item in assets.items()})
        return {'outputs':outputs,'workflow':workflow,'metadata':{'execution':'test-double; no model inference'}}

    def document(self, app='cinema-studio', state=None, ids=None):
        response=self.client.post(f'/api/apps/{app}/documents',json={'title':'Isolated draft','state':state or {},'asset_ids':ids or []})
        self.assertEqual(response.status_code,201,response.text);return response.json()

    def shot(self, ident='a', **changes):
        return {'id':ident,'label':ident,'request':self.request(**changes),'source_from_previous':False}

    def sequence(self, doc, shots, **changes):
        episode={'title':'Measured episode','target_duration':30,'shots':shots,**changes}
        response=self.client.post(f"/api/apps/{doc['app_id']}/documents/{doc['id']}/sequences",json={'expected_revision':doc['revision'],'episodes':[episode]})
        self.assertEqual(response.status_code,201,response.text);return response.json()

    def start_sequence(self, sequence):
        response=self.client.post(f"/api/sequences/{sequence['id']}/start",json={'expected_revision':sequence['revision']})
        self.assertEqual(response.status_code,200,response.text)

    def wait_sequence(self, ident, expected='succeeded'):
        deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            value=self.client.get(f'/api/sequences/{ident}').json()
            if value['status'] in {'succeeded','failed','cancelled'}:
                self.assertEqual(value['status'],expected,value);return value
            time.sleep(.03)
        self.fail('Sequence did not settle')

    def test_document_revision_reference_and_sensitive_state_guards(self):
        media=self.upload_mask()
        path='/api/apps/mini-apps/documents'
        self.assertEqual(self.client.post(path,json={'state':{'source_asset_id':media['id']}}).status_code,422)
        doc=self.document('mini-apps',{'source_asset_id':media['id']},[media['id']])
        url=f"{path}/{doc['id']}"
        updated=self.client.patch(url,json={'expected_revision':1,'title':'Changed'}).json()
        self.assertEqual(updated['revision'],2)
        self.assertEqual(self.client.patch(url,json={'expected_revision':1,'title':'Stale'}).status_code,409)
        self.assertEqual(self.client.patch(url,json={'expected_revision':2,'title':'Changed'}).json()['revision'],2)
        self.assertEqual(self.client.delete(f"/api/assets/{media['id']}").status_code,409)
        self.assertEqual(self.client.patch(url,json={'expected_revision':2,'state':{'config':{'access_token':'never-store'}}}).status_code,422)
        response=self.client.patch(url,json={'expected_revision':2,'state':{},'asset_ids':[]})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(self.client.delete(f"/api/assets/{media['id']}").status_code,200)
        self.assertEqual(self.client.post('/api/apps/content-factory/documents',json={'state':{'length':16}}).status_code,422)

    def test_scoped_image_job_snapshot_retry_and_bundle(self):
        source=self.upload_mask();doc=self.document('mini-apps',{'source_asset_id':source['id']},[source['id']])
        request=self.request(model_id='flux-klein-4b',effect_id='edit-image',source_asset_id=source['id'],batch_size=2)
        endpoint=f"/api/apps/mini-apps/documents/{doc['id']}/jobs"
        body={'expected_revision':1,'operation':'edit-image','request':request,'step_id':'portrait'}
        response=self.client.post(endpoint,json=body);self.assertEqual(response.status_code,201,response.text)
        job=self.wait(response.json()['id']);self.assertEqual([item['kind'] for item in job['outputs']],['image','image'])
        self.assertEqual(job['request']['frames'],1)
        self.assertEqual(self.client.get('/api/apps/mini-apps/jobs').json()['total'],1)
        self.assertEqual(self.client.get('/api/apps/cinema-studio/jobs').json()['total'],0)
        self.client.patch(f"/api/apps/mini-apps/documents/{doc['id']}",json={'expected_revision':1,'state':{'prompt':'New draft'},'asset_ids':[]})
        self.assertEqual(self.client.post(endpoint,json=body).status_code,409)
        context=self.client.get(f"/api/jobs/{job['id']}/app-context").json()
        self.assertEqual(context['document_snapshot']['state']['source_asset_id'],source['id'])
        retry=self.client.post(f"/api/jobs/{job['id']}/retry");self.assertEqual(retry.status_code,201,retry.text)
        repeated=self.wait(retry.json()['id']);self.assertEqual(repeated['app_context'],job['app_context'])
        bundle=self.client.get(f"/api/jobs/{job['id']}/bundle?include_media=true")
        self.assertEqual(bundle.status_code,200,bundle.text[:200] if bundle.status_code!=200 else '')
        with zipfile.ZipFile(io.BytesIO(bundle.content)) as archive:
            self.assertIn('APP-CONTEXT.json',archive.namelist())
            self.assertTrue(any(name.endswith('/speech.py') for name in archive.namelist()))
        self.assertEqual(self.client.delete(f"/api/assets/{source['id']}").status_code,409)

    def test_unsupported_operations_never_enqueue_and_inputs_must_be_attached(self):
        doc=self.document('content-factory')
        before=len(self.calls)
        response=self.client.post(f"/api/apps/content-factory/documents/{doc['id']}/jobs",json={'expected_revision':1,'operation':'generate-series','request':self.request()})
        self.assertEqual(response.status_code,409,response.text);self.assertEqual(len(self.calls),before)
        source=self.upload_mask();doc=self.document('mini-apps')
        response=self.client.post(f"/api/apps/mini-apps/documents/{doc['id']}/jobs",json={'expected_revision':1,'operation':'edit-image','request':self.request(model_id='flux-klein-4b',effect_id='edit-image',source_asset_id=source['id'])})
        self.assertEqual(response.status_code,422,response.text)
        response=self.client.post('/api/jobs',json=self.request(model_id='flux-klein-4b',effect_id='create-image',provider='comfy-cloud'))
        self.assertEqual(response.status_code,422,response.text)

    def test_audio_ingestion_speech_output_and_recording_interval(self):
        response=self.client.post('/api/assets',files={'file':('voice.wav',self.recording,'audio/wav')})
        self.assertEqual(response.status_code,201,response.text);audio=response.json()
        self.assertEqual(audio['kind'],'audio');self.assertAlmostEqual(audio['duration'],2)
        self.assertEqual(self.client.get(f"/api/assets/{audio['id']}/frame").status_code,422)
        source=self.upload_mask()
        request=self.request(model_id='wan-s2v',effect_id='speak',source_asset_id=source['id'],audio_asset_id=audio['id'],audio_start=1.5,frames=73,fps=16)
        self.assertEqual(self.client.post('/api/jobs',json=request).status_code,422)
        longer=self.client.post('/api/assets',files={'file':('long.wav',self.speech_recording,'audio/wav')}).json()
        request.update(audio_start=.25,audio_asset_id=longer['id'])
        response=self.client.post('/api/jobs',json=request);self.assertEqual(response.status_code,201,response.text)
        self.wait(response.json()['id'])
        response=self.client.post('/api/jobs',json=self.request(model_id='kokoro-82m',effect_id='generate-speech',prompt='A short spoken test.'))
        self.assertEqual(response.status_code,201,response.text)
        job=self.wait(response.json()['id']);self.assertEqual(job['outputs'][0]['kind'],'audio')
        self.assertEqual(job['request']['frames'],1)

    def test_reviewed_sequence_previous_frame_and_exact_assembly(self):
        doc=self.document();second=self.shot('b',effect_id='image-to-video');second['source_from_previous']=True
        sequence=self.sequence(doc,[self.shot(),second])
        self.assertEqual(sequence['status'],'draft');self.assertEqual(len(self.calls),0)
        self.assertEqual(self.client.post(f"/api/sequences/{sequence['id']}/start",json={'expected_revision':99}).status_code,409)
        self.start_sequence(sequence);done=self.wait_sequence(sequence['id'])
        self.assertEqual(done['completed_shots'],2)
        episode=done['episodes'][0];self.assertAlmostEqual(episode['actual_duration'],18/8,places=3)
        self.assertEqual(episode['target_duration'],30)
        self.assertEqual(episode['output']['frame_count'],18)
        first,second=episode['shots'];self.assertTrue(second['resolved_request']['source_asset_id'])
        self.assertEqual(second['dependency']['job_id'],first['job_id'])
        self.assertEqual(self.calls[1]['effect_id'],'image-to-video')
        self.assertEqual(self.client.delete(f"/api/jobs/{first['job_id']}").status_code,409)
        self.assertEqual(self.client.delete(f"/api/assets/{episode['output']['id']}").status_code,409)

    def test_sequence_partial_failure_retries_only_incomplete_shot(self):
        sequence=self.sequence(self.document(),[self.shot(),self.shot('b',prompt='fail once')]);self.start_sequence(sequence)
        failed=self.wait_sequence(sequence['id'],'failed');first_id=failed['episodes'][0]['shots'][0]['job_id']
        self.assertEqual(failed['completed_shots'],1);self.assertIsNone(failed['episodes'][0]['output'])
        response=self.client.post(f"/api/sequences/{sequence['id']}/retry");self.assertEqual(response.status_code,200,response.text)
        done=self.wait_sequence(sequence['id']);self.assertEqual(done['episodes'][0]['shots'][0]['job_id'],first_id)
        self.assertEqual(len(self.calls),3);self.assertEqual(len(done['episodes'][0]['shots'][1]['attempt_job_ids']),2)

    def test_sequence_cancellation_and_restart_never_auto_resubmit(self):
        sequence=self.sequence(self.document(),[self.shot(prompt='block until cancelled'),self.shot('b')]);self.start_sequence(sequence)
        self.assertTrue(self.started.wait(3));self.client.post(f"/api/sequences/{sequence['id']}/cancel")
        self.wait_sequence(sequence['id'],'cancelled');self.assertEqual(len(self.calls),1)
        worker=self.app.state.worker;worker.stop()
        with self.app.state.store.connection() as db:
            row=db.execute('SELECT record FROM sequences WHERE id=?',(sequence['id'],)).fetchone();record=json.loads(row[0]);record.update(status='running',cancel_requested=False)
            db.execute('UPDATE sequences SET status=?,record=? WHERE id=?',('running',json.dumps(record),sequence['id']))
        self.app.state.store.recover()
        failed=self.client.get(f"/api/sequences/{sequence['id']}").json();self.assertEqual(failed['status'],'failed')
        self.assertEqual(len(self.calls),1);self.assertIn('restart',failed['error'].lower())

    def test_sequence_rejects_silent_retime_and_unanalyzed_links(self):
        doc=self.document()
        body={'expected_revision':1,'episodes':[{'shots':[self.shot(),self.shot('b',fps=16)]}]}
        self.assertEqual(self.client.post(f"/api/apps/cinema-studio/documents/{doc['id']}/sequences",json=body).status_code,422)
        body['episodes'][0].update(shots=[self.shot()],keep_shot_audio=True)
        self.assertEqual(self.client.post(f"/api/apps/cinema-studio/documents/{doc['id']}/sequences",json=body).status_code,422)
        linked=self.document('content-factory',{'reference_url':'https://example.com/clip'})
        self.assertEqual(self.client.post(f"/api/apps/content-factory/documents/{linked['id']}/sequences",json={'expected_revision':1,'episodes':[{'target_duration':30,'shots':[self.shot()]}]}).status_code,422)

    def test_planner_submission_is_recorded_and_never_autorenders(self):
        def planner(request, settings, progress, cancelled, submitted, *, references=None):
            submitted({'provider':'local','prompt_id':'local-prompt'})
            return {'episodes':[{'title':'Proposed','target_duration':30,'shots':[{'id':'one','prompt':'A distinct visual description.','camera':'Static','voiceover':'','duration':10}]}],'metadata':{'model_id':'qwen3.8-planner','execution':'test-double','input_scope':'Text brief only; no media references supplied.'}}
        doc=self.document('content-factory')
        with patch('engine.planner.plan_video',planner):
            response=self.client.post(f"/api/apps/content-factory/documents/{doc['id']}/plans",json={'expected_revision':1,'prompt':'A short narrative','target_duration':30})
            self.assertEqual(response.status_code,201,response.text);ident=response.json()['id']
            deadline=time.monotonic()+5
            while time.monotonic()<deadline:
                plan=self.client.get(f'/api/plans/{ident}').json()
                if plan['status'] in {'succeeded','failed'}:break
                time.sleep(.02)
        self.assertEqual(plan['status'],'succeeded',plan);self.assertEqual(plan['provider_job']['prompt_id'],'local-prompt')
        self.assertEqual(len(self.calls),0)
        self.assertIn('Text brief only',plan['proposal']['metadata']['input_scope'])

    def test_asset_roles_are_persisted_and_legacy_roles_are_resolved(self):
        response=self.client.post('/api/jobs',json=self.request())
        job=self.wait(response.json()['id']);ident=job['outputs'][0]['id']
        self.assertEqual(self.client.get(f'/api/assets/{ident}').json()['role'],'result')
        record=self.app.state.store.get('assets',ident);record.pop('role')
        with self.app.state.store.connection() as db:
            db.execute('UPDATE assets SET record=? WHERE id=?',(json.dumps(record),ident))
        job['outputs'][0]['role']='mask';self.app.state.store.update_job(job['id'],{'outputs':job['outputs']})
        self.assertEqual(self.client.get(f'/api/assets/{ident}').json()['role'],'mask')
        self.assertEqual(next(item for item in self.client.get('/api/assets').json()['items'] if item['id']==ident)['role'],'mask')

    def test_wrong_media_or_partial_image_batch_cannot_be_success(self):
        def wrong(request,assets,output_dir,*args):
            path=Path(output_dir)/'wrong.png';path.write_bytes(self.mask)
            return {'outputs':[{'path':str(path),'role':'result'}]}
        with patch('engine.runner.run_job',wrong):
            response=self.client.post('/api/jobs',json=self.request())
            failed=self.wait(response.json()['id'],'failed');self.assertIn('final video',failed['error'])
            response=self.client.post('/api/jobs',json=self.request(model_id='flux-klein-4b',effect_id='create-image',batch_size=2))
            failed=self.wait(response.json()['id'],'failed');self.assertIn('2 final image',failed['error'])

    def test_explicit_soundtrack_assembly_is_bounded_to_actual_duration(self):
        audio=self.client.post('/api/assets',files={'file':('speech.wav',self.recording,'audio/wav')}).json()
        doc=self.document(state={'attachment_asset_ids':[audio['id']]},ids=[audio['id']])
        sequence=self.sequence(doc,[self.shot()],audio_asset_id=audio['id'],audio_start=.25)
        self.start_sequence(sequence);done=self.wait_sequence(sequence['id'])
        output=done['episodes'][0]['output'];self.assertTrue(output['has_audio'])
        self.assertEqual(output['frame_count'],9);self.assertAlmostEqual(output['duration'],1.125,places=2)

    def test_cancelled_sequence_resume_keeps_completed_shot(self):
        sequence=self.sequence(self.document(),[self.shot(),self.shot('b',prompt='block until cancelled')])
        self.start_sequence(sequence)
        deadline=time.monotonic()+5
        while len(self.calls)<2 and time.monotonic()<deadline:time.sleep(.02)
        self.assertEqual(len(self.calls),2)
        self.client.post(f"/api/sequences/{sequence['id']}/cancel")
        cancelled=self.wait_sequence(sequence['id'],'cancelled')
        first=cancelled['episodes'][0]['shots'][0]['job_id']
        response=self.client.post(f"/api/sequences/{sequence['id']}/resume")
        self.assertEqual(response.status_code,200,response.text)
        done=self.wait_sequence(sequence['id'])
        self.assertEqual(done['episodes'][0]['shots'][0]['job_id'],first)
        self.assertEqual(len(self.calls),3)

    def bundle(self, ident):
        response=self.client.get(f'/api/jobs/{ident}/bundle?include_media=true')
        self.assertEqual(response.status_code,200,response.text if response.status_code!=200 else '')
        return zipfile.ZipFile(io.BytesIO(response.content))

    def test_klein_reference_bundle_relocates_every_original_input(self):
        from PIL import Image
        import hashlib
        assets=[]
        for color in ['red','green','blue']:
            data=io.BytesIO();Image.new('RGB',(256,256),color).save(data,'PNG')
            assets.append(self.client.post('/api/assets',files={'file':(color+'.png',data.getvalue(),'image/png')}).json())
        response=self.client.post('/api/jobs',json=self.request(model_id='flux-klein-4b',effect_id='edit-image',source_asset_id=assets[0]['id'],reference_asset_ids=[item['id'] for item in assets[1:]]))
        self.assertEqual(response.status_code,201,response.text);job=self.wait(response.json()['id'])
        with self.bundle(job['id']) as archive:
            manifest=json.loads(archive.read('manifest.json'));graph=json.loads(archive.read('workflow_api.json'))
            self.assertEqual(set(manifest['inputs']),{'source','reference_0','reference_1'})
            for role,node in [('source','image'),('reference_0','reference_0'),('reference_1','reference_1')]:
                item=manifest['inputs'][role]
                self.assertEqual(graph[node]['inputs']['image'],item['comfy_filename'])
                self.assertEqual(hashlib.sha256(archive.read(item['archive_path'])).hexdigest(),item['sha256'])
            self.assertEqual(json.loads(archive.read('workflow_executed_api.json')),self.app.state.store.get('jobs',job['id'])['workflow'])
            requirements=json.loads(archive.read('MODEL-REQUIREMENTS.json'))
            self.assertEqual(len(requirements['model_files']),3)
            self.assertTrue(all(item['destination'].startswith('models/') for item in requirements['model_files']))
            self.assertNotIn('sam2_package',requirements)
            self.assertIn('custom_nodes/openframe/speech.py',archive.namelist())

    def reference_images(self, count):
        from PIL import Image
        assets=[]
        for index in range(count):
            data=io.BytesIO();Image.new('RGB',(256,256),((index*11)%256,(index*29)%256,90)).save(data,'PNG')
            response=self.client.post('/api/assets',files={'file':(f'ref-{index}.png',data.getvalue(),'image/png')})
            self.assertEqual(response.status_code,201,response.text);assets.append(response.json())
        return assets

    def test_reference_video_accepts_document_subset_in_order_and_retry_preserves_it(self):
        references=self.reference_images(50);ids=[item['id'] for item in references]
        doc=self.document('cinema-studio',{'reference_asset_ids':ids},ids)
        self.assertEqual(doc['state']['reference_asset_ids'],ids)
        active=ids[:3]
        endpoint=f"/api/apps/cinema-studio/documents/{doc['id']}/jobs"
        body={'expected_revision':doc['revision'],'operation':'reference-to-video',
              'request':self.request(model_id='ltx-2.5',effect_id='reference-to-video',reference_asset_ids=active,steps=8,fps=24)}
        response=self.client.post(endpoint,json=body)
        self.assertEqual(response.status_code,201,response.text);job=response.json()
        self.assertEqual(job['request']['reference_asset_ids'],active)
        self.wait(job['id'])
        self.assertEqual(self.asset_roles[-1],['reference_0','reference_1','reference_2'])
        context=self.client.get(f"/api/jobs/{job['id']}/app-context").json()
        self.assertEqual(context['document_snapshot']['state']['reference_asset_ids'],ids)
        retry=self.client.post(f"/api/jobs/{job['id']}/retry")
        self.assertEqual(retry.status_code,201,retry.text);replacement=retry.json()
        self.assertEqual(replacement['request']['reference_asset_ids'],active)
        self.assertNotEqual(replacement['id'],job['id'])
        self.wait(replacement['id'])
        self.assertEqual(self.asset_roles[-1],['reference_0','reference_1','reference_2'])

    def test_reference_limits_scope_and_catalog_surface(self):
        references=self.reference_images(11);ids=[item['id'] for item in references]
        request=lambda model_id='ltx-2.5',**changes:self.request(model_id=model_id,steps=8,fps=24,**changes)
        empty=self.client.post('/api/jobs',json=request(effect_id='reference-to-video'))
        self.assertEqual(empty.status_code,422,empty.text)
        self.assertIn('one to nine',empty.text)
        for count in (1,9):
            response=self.client.post('/api/jobs',json=request(effect_id='reference-to-video',reference_asset_ids=ids[:count]))
            self.assertEqual(response.status_code,201,response.text)
            self.assertEqual(response.json()['request']['reference_asset_ids'],ids[:count])
            self.wait(response.json()['id'])
            self.assertEqual(self.asset_roles[-1],[f'reference_{index}' for index in range(count)])
        over=self.client.post('/api/jobs',json=request(effect_id='reference-to-video',reference_asset_ids=ids[:10]))
        self.assertEqual(over.status_code,422,over.text)
        self.assertIn('at most 9',over.text)
        unsupported=self.client.post('/api/jobs',json=request(model_id='ltx-2.3',effect_id='reference-to-video',reference_asset_ids=ids[:1]))
        self.assertEqual(unsupported.status_code,422,unsupported.text)
        self.assertIn('does not support',unsupported.text)
        legacy=self.client.post('/api/jobs',json=request(effect_id='image-to-video',source_asset_id=ids[0]))
        self.assertEqual(legacy.status_code,201,legacy.text)
        self.wait(legacy.json()['id'])
        self.assertEqual(self.asset_roles[-1],['source'])
        for extra in ({'reference_asset_id':ids[1]},{'reference_asset_ids':ids[1:3]}):
            i2v=self.client.post('/api/jobs',json=request(effect_id='image-to-video',source_asset_id=ids[0],**extra))
            self.assertEqual(i2v.status_code,422,i2v.text)
        duplicate=self.client.post('/api/jobs',json=request(effect_id='reference-to-video',reference_asset_ids=[ids[0],ids[0]]))
        self.assertEqual(duplicate.status_code,422,duplicate.text)
        self.assertIn('distinct',duplicate.text)
        singular=self.client.post('/api/jobs',json=request(effect_id='reference-to-video',reference_asset_id=ids[0]))
        self.assertEqual(singular.status_code,422,singular.text)
        self.assertIn('ordered reference_asset_ids',singular.text)
        with_source=self.client.post('/api/jobs',json=request(effect_id='reference-to-video',source_asset_id=ids[0],reference_asset_ids=ids[1:4]))
        self.assertEqual(with_source.status_code,422,with_source.text)
        self.assertIn('accepts only reference images',with_source.text)
        unknown=self.client.post('/api/jobs',json=request(effect_id='reference-to-video',reference_asset_ids=['0'*32]))
        self.assertEqual(unknown.status_code,404,unknown.text)
        doc=self.document('cinema-studio',{'reference_asset_ids':ids[:1]},ids[:1])
        foreign=self.client.post(f"/api/apps/cinema-studio/documents/{doc['id']}/jobs",json={
            'expected_revision':doc['revision'],'operation':'reference-to-video',
            'request':request(effect_id='reference-to-video',reference_asset_ids=ids[:2])})
        self.assertEqual(foreign.status_code,422,foreign.text)
        self.assertIn('Attach all render inputs',foreign.text)
        catalog=self.client.get('/api/catalog').json()
        effect=next(item for item in catalog['effects'] if item['id']=='reference-to-video')
        self.assertEqual((effect['min_references'],effect['max_references']),(1,9))
        self.assertEqual(effect['model_ids'],['ltx-2.5'])
        model=next(item for item in catalog['models'] if item['id']=='ltx-2.5')
        self.assertEqual(model['reference_limits_by_task']['reference-video'],9)
        apps=self.client.get('/api/apps').json()
        cinema=next(item for item in apps['items'] if item['id']=='cinema-studio')
        operation=next(item for item in cinema['operations'] if item['id']=='reference-to-video')
        self.assertTrue(operation['available'])
        self.assertEqual(operation['model_ids'],['ltx-2.5'])
        self.assertEqual((operation['min_references'],operation['max_references']),(1,9))
        self.assertEqual(operation['reference_limits_by_model'],{'ltx-2.5':{'min':1,'max':9}})
        image_operation=next(item for item in cinema['operations'] if item['id']=='image-to-video')
        self.assertEqual(image_operation['reference_limits_by_model']['ltx-2.5'],{'min':0,'max':1})

    def test_speech_and_talking_video_bundles_include_dependencies_and_trim(self):
        response=self.client.post('/api/jobs',json=self.request(model_id='kokoro-82m',effect_id='generate-speech',prompt='Package this speech graph.'))
        job=self.wait(response.json()['id'])
        with self.bundle(job['id']) as archive:
            requirements=json.loads(archive.read('MODEL-REQUIREMENTS.json'))
            self.assertEqual(requirements['system_dependencies'],['espeak-ng'])
            self.assertIn('kokoro==0.9.4',requirements['python_dependencies'])
            self.assertTrue(any('en_core_web_sm-3.8.0' in item for item in requirements['python_dependencies']))
            self.assertEqual(len(requirements['model_files']),6)
            self.assertTrue(all('/voices/' not in item['destination'] for item in requirements['model_files']))
            self.assertEqual(json.loads(archive.read('workflow_api.json'))['save']['class_type'],'OpenFrameSaveAudio')
        source=self.upload_mask();audio=self.client.post('/api/assets',files={'file':('input.wav',self.speech_recording,'audio/wav')}).json()
        response=self.client.post('/api/jobs',json=self.request(model_id='wan-s2v',effect_id='speak',source_asset_id=source['id'],audio_asset_id=audio['id'],audio_start=.25,frames=73,fps=16))
        self.assertEqual(response.status_code,201,response.text);job=self.wait(response.json()['id'])
        with self.bundle(job['id']) as archive:
            manifest=json.loads(archive.read('manifest.json'));graph=json.loads(archive.read('workflow_api.json'))
            self.assertEqual(archive.read(manifest['inputs']['audio']['archive_path']),self.speech_recording)
            self.assertEqual(graph['speech']['inputs']['audio'],manifest['inputs']['audio']['comfy_filename'])
            self.assertEqual(graph['speech_range']['inputs']['start_index'],.25)
            self.assertEqual(graph['speech_range']['inputs']['duration'],73/16)
            requirements=json.loads(archive.read('MODEL-REQUIREMENTS.json'))
            self.assertEqual(requirements['model_id'],'wan-s2v')
            self.assertEqual(len(requirements['model_files']),4)
            self.assertIn('models/audio_encoders/wav2vec2_large_english_fp16.safetensors',{item['destination'] for item in requirements['model_files']})
            self.assertEqual(graph['condition']['class_type'],'WanSoundImageToVideo')
            self.assertFalse(any('in-outpainting' in item['file'] for item in requirements['model_files']))

    def test_wan_motion_and_character_requirements_are_task_specific(self):
        source=self.upload_video();image=self.upload_mask()
        for effect in ['motion-transfer','character-replacement']:
            request=self.request(model_id='wan-animate',effect_id=effect,source_asset_id=source['id'],reference_asset_id=image['id'])
            if effect=='character-replacement':request.update(mask_asset_id=image['id'],mask_tracking_method='sam2')
            response=self.client.post('/api/jobs',json=request)
            self.assertEqual(response.status_code,201,response.text);job=self.wait(response.json()['id'])
            with self.bundle(job['id']) as archive:
                requirements=json.loads(archive.read('MODEL-REQUIREMENTS.json'))
                self.assertIn('ComfyUI-WanAnimatePreprocess',requirements['additional_node_packages'][0]['repository'])
                self.assertIn('onnxruntime>=1.20,<2',requirements['additional_node_packages'][0]['dependencies'])
                self.assertEqual('sam2_package' in requirements,effect=='character-replacement')
                self.assertEqual(any('relight_lora' in item['file'] for item in requirements['model_files']),effect=='character-replacement')

    def test_sequence_shot_bundle_includes_derived_frame_and_sequence_provenance(self):
        second=self.shot('b',effect_id='image-to-video');second['source_from_previous']=True
        sequence=self.sequence(self.document(),[self.shot(),second]);self.start_sequence(sequence)
        done=self.wait_sequence(sequence['id']);shot=done['episodes'][0]['shots'][1]
        with self.bundle(shot['job_id']) as archive:
            context=json.loads(archive.read('APP-CONTEXT.json'))
            manifest=json.loads(archive.read('manifest.json'))
            self.assertEqual(manifest['app_context']['group_id'],sequence['id'])
            self.assertEqual(manifest['inputs']['source']['id'],shot['dependency']['derived_asset_id'])
            self.assertIn(manifest['inputs']['source']['archive_path'],archive.namelist())
        provenance=done['episodes'][0]['provenance']
        self.assertEqual(provenance['shots'][1]['dependency'],shot['dependency'])
        self.assertEqual(provenance['expected_frames'],18)

    def test_speak_enforces_native_limits_and_preserves_legacy_exports(self):
        source=self.upload_mask();audio=self.client.post('/api/assets',files={'file':('voice.wav',self.speech_recording,'audio/wav')}).json()
        request=self.request(model_id='wan-s2v',effect_id='speak',source_asset_id=source['id'],audio_asset_id=audio['id'],frames=73,fps=16)
        for changes,explanation in [({'model_id':'ltx-2.3'},'does not support'),({'fps':24},'exactly 16'),({'frames':69},'from 73'),({'frames':74},'multiples')]:
            response=self.client.post('/api/jobs',json={**request,**changes})
            self.assertEqual(response.status_code,422,response.text);self.assertIn(explanation,response.text)
        doc=self.document('mini-apps',{'source_asset_id':source['id'],'audio_asset_id':audio['id']},[source['id'],audio['id']])
        response=self.client.post(f"/api/apps/mini-apps/documents/{doc['id']}/jobs",json={'expected_revision':doc['revision'],'operation':'speak','request':request})
        self.assertEqual(response.status_code,201,response.text)
        job=self.wait(response.json()['id'])
        old_request={**job['request'],'model_id':'ltx-2.3','frames':49,'fps':24}
        old_graph={'legacy':{'class_type':'OpenFrameSaveVideo','inputs':{'filename_prefix':'stored-ltx-speech'}}}
        self.app.state.store.update_job(job['id'],{'request':old_request,'workflow':old_graph})
        self.assertEqual(self.client.get(f"/api/jobs/{job['id']}/workflow").json(),old_graph)
        with self.bundle(job['id']) as archive:
            self.assertEqual(json.loads(archive.read('workflow_api.json')),old_graph)
        self.app.state.store.update_job(job['id'],{'workflow':None})
        self.assertEqual(self.client.get(f"/api/jobs/{job['id']}/workflow").status_code,422)
        self.assertEqual(self.client.get(f"/api/jobs/{job['id']}/bundle").status_code,422)
        self.assertEqual(self.client.post(f"/api/jobs/{job['id']}/retry").status_code,422)
