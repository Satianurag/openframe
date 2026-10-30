"""Contracts that distinguish the new capabilities from prompt-only substitutes."""
import json
from unittest import TestCase
from engine.workflows import build_workflow,normalize_request,WorkflowError
from engine.planner import _parse_batch,PlanningError,normalize_plan_request


class ImageConditioning(TestCase):
    def test_edit_keeps_source_and_each_reference_as_separate_constraints(self):
        graph=build_workflow({'model_id':'flux-klein-4b','effect_id':'edit-image','prompt':'Keep the person and use the lamp from the second reference.','source_asset_id':'person','reference_asset_ids':['lamp','palette'],'batch_size':2,'seed':1},{'source':'person.png','reference_0':'lamp.png','reference_1':'palette.png'})
        self.assertEqual([graph[key]['inputs']['image'] for key in ('image','reference_0','reference_1')],['person.png','lamp.png','palette.png'])
        self.assertEqual(graph['empty']['inputs']['batch_size'],2)
        self.assertEqual(sum(node['class_type']=='ReferenceLatent' for node in graph.values()),6)
        self.assertEqual(graph['save']['class_type'],'SaveImage')

    def test_fifth_image_is_rejected_instead_of_silently_dropped(self):
        with self.assertRaises(WorkflowError):
            normalize_request({'model_id':'flux-klein-4b','effect_id':'edit-image','prompt':'Edit','source_asset_id':'source','reference_asset_ids':['a','b','c','d']})

    def test_image_requests_do_not_inherit_video_duration(self):
        request=normalize_request({'model_id':'flux-klein-4b','effect_id':'create-image','prompt':'A studio portrait','frames':97,'fps':24})
        self.assertEqual((request['frames'],request['fps']),(1,1.0))


class MotionAndSpeechConditioning(TestCase):
    def test_motion_uses_detected_pose_and_face_without_background_replacement(self):
        graph=build_workflow({'model_id':'wan-animate','effect_id':'motion-transfer','prompt':'Follow the performer','seed':1})
        condition=graph['condition']['inputs']
        self.assertEqual(condition['face_video'],['pose_detect',1])
        self.assertEqual(graph[condition['pose_video'][0]]['inputs']['pose_data'],['pose_detect',0])
        self.assertNotIn('background_video',condition)
        self.assertNotIn('mask',graph['save']['inputs'])

    def test_character_replacement_conditions_background_and_keeps_composite_mask_separate(self):
        graph=build_workflow({'model_id':'wan-animate','effect_id':'character-replacement','prompt':'Replace the performer','seed':1})
        condition=graph['condition']['inputs']
        self.assertEqual(condition['character_mask'],['source',1])
        self.assertEqual(graph[condition['background_video'][0]]['inputs']['destination'],['source',0])
        self.assertEqual(graph['save']['inputs']['mask'],['source',2])
        self.assertEqual(graph['source']['inputs']['feather_method'],'smooth-inward')

    def test_speech_conditions_latent_and_preserves_the_uploaded_waveform(self):
        graph=build_workflow({'model_id':'wan-s2v','effect_id':'speak','prompt':'Speak naturally','seed':1,'audio_start':1.25,'frames':77,'fps':16},{'source':'portrait.png','audio':'speech.wav'})
        self.assertEqual(graph['speech']['inputs']['audio'],'speech.wav')
        self.assertEqual(graph['speech_range']['inputs']['start_index'],1.25)
        self.assertEqual(graph['condition']['class_type'],'WanSoundImageToVideo')
        self.assertEqual(graph['condition']['inputs']['audio_encoder_output'],['encode_speech',0])
        self.assertEqual(graph['condition']['inputs']['ref_image'],['image',0])
        self.assertEqual(graph['encode_speech']['inputs']['audio'],['speech_range',0])
        self.assertEqual(graph['save']['inputs']['audio'],['speech_range',0])
        self.assertNotIn('decode_audio',graph)

    def test_speech_rejects_invalid_temporal_settings_and_unverified_model(self):
        for change in [{'fps':24},{'frames':69},{'model_id':'ltx-2.3'}]:
            with self.assertRaises(WorkflowError):
                normalize_request({'model_id':'wan-s2v','effect_id':'speak','prompt':'Speak naturally','frames':77,'fps':16,**change})


class PlannerOutputContract(TestCase):
    def shot(self,camera='Slow close-up push-in'):
        return {'prompt':'A ceramic lamp rests on a desk at dusk and gradually lights the nearby notebook.','camera':camera,'voiceover':''}

    def test_camera_narration_is_not_accepted_as_a_camera_instruction(self):
        with self.assertRaises(PlanningError):
            _parse_batch(json.dumps({'title':'Lamp','shots':[self.shot('The lamp glows softly in the dim room.')]}),1,[])

    def test_reviewable_concrete_shot_is_accepted(self):
        result=_parse_batch(json.dumps({'title':'Lamp','shots':[self.shot()]}),1,[])
        self.assertEqual(result['shots'][0]['camera'],'Slow close-up push-in')

    def test_missing_or_repeated_shots_cannot_fake_requested_duration(self):
        raw=json.dumps({'title':'Lamp','shots':[self.shot()]})
        with self.assertRaises(PlanningError):_parse_batch(raw,2,[])
        with self.assertRaises(PlanningError):_parse_batch(raw,1,[self.shot()])
        self.assertEqual(normalize_plan_request({'prompt':'A short story','target_duration':300,'episodes':4})['target_duration'],300)
        with self.assertRaises(PlanningError):normalize_plan_request({'prompt':'Story','target_duration':305})
