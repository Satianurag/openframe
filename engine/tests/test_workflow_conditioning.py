"""Regression for source-frame animation versus loose reference conditioning."""
from unittest import TestCase
from engine.workflows import build_workflow, normalize_request, WorkflowError


class WanConditioningContract(TestCase):
    def condition(self, graph):
        return next(node['inputs'] for node in graph.values() if node['class_type']=='WanVaceToVideo')

    def test_image_animation_anchors_the_opening_frame(self):
        graph=build_workflow({'model_id':'wan-vace','effect_id':'image-to-video','prompt':'Gentle camera movement','seed':42}, {'source':'opening.png'})
        inputs=self.condition(graph)
        source=graph[inputs['control_video'][0]]
        self.assertEqual(source['class_type'],'LoadImage')
        self.assertEqual(source['inputs']['image'],'opening.png')
        mask=graph[inputs['control_masks'][0]]
        self.assertEqual(mask['class_type'],'SolidMask')
        self.assertEqual(mask['inputs']['value'],0)
        self.assertNotIn('reference_image',inputs)

    def test_reference_generation_remains_a_separate_constraint(self):
        graph=build_workflow({'model_id':'wan-vace','effect_id':'text-to-video','prompt':'A vase in a new studio','seed':42}, {'reference':'reference.png'})
        inputs=self.condition(graph)
        self.assertEqual(graph[inputs['reference_image'][0]]['inputs']['image'],'reference.png')
        self.assertNotIn('control_video',inputs)
        self.assertNotIn('control_masks',inputs)


class MaskConditioningContract(TestCase):
    def test_masked_prompt_enhancement_is_opt_in_and_dependencies_agree(self):
        from engine.models import required_model_files
        for effect, default in [('remove-object',False),('replace-object',False),('text-to-video',True)]:
            for supplied in ('missing',None,True,False):
                request={'model_id':'ltx-2.5','effect_id':effect,'prompt':'A clear wooden desk','seed':42}
                if supplied!='missing':request['enhance_prompt']=supplied
                normalized=normalize_request(request)
                expected=default if supplied in ('missing',None) else supplied
                self.assertEqual(normalized['enhance_prompt'],expected)
                self.assertEqual('enhance_prompt' in build_workflow(normalized),expected)
                files=required_model_files('ltx-2.5',request | {'task':normalized['task']})
                self.assertEqual(any(f.get('feature')=='enhance_prompt' for f in files),expected)

    def test_contour_feather_only_controls_compositing(self):
        graph=build_workflow({'model_id':'ltx-2.3','effect_id':'replace-object','prompt':'A black chess knight','seed':46})
        self.assertEqual(graph['source']['inputs']['feather_method'],'smooth-inward')
        self.assertEqual(graph['green_guide']['inputs']['mask'],['source',1])
        self.assertEqual(graph['save']['inputs']['mask'],['source',2])
        self.assertFalse(graph['save']['inputs']['match_lighting'])
        self.assertNotIn('sample_refinement',graph)

    def test_edit_margin_defaults_and_explicit_override(self):
        request={'model_id':'ltx-2.3','effect_id':'remove-object','prompt':'Empty surface','seed':42,'mask_edit_margin':None}
        self.assertEqual(normalize_request(request)['mask_edit_margin'],12)
        self.assertEqual(normalize_request(request | {'mask_tracking':False})['mask_edit_margin'],0)
        self.assertEqual(normalize_request(request | {'mask_edit_margin':4})['mask_edit_margin'],4)
        self.assertEqual(build_workflow(request)['source']['inputs']['edit_margin'],12)
        with self.assertRaises(WorkflowError):normalize_request(request | {'mask_edit_margin':65})


class ExpandConditioningContract(TestCase):
    def test_original_conditions_every_denoising_step_and_batch(self):
        for batch in (1, 2):
            with self.subTest(batch=batch):
                graph=build_workflow({'model_id':'flux3-klein','effect_id':'expand-image','provider':'local',
                    'prompt':'Continue the reading room','width':1824,'height':1024,
                    'source_width':768,'source_height':1024,'batch_size':batch,'seed':42}, {'source':'original.png'})
                masked=graph[graph['sample']['inputs']['latent_image'][0]]
                self.assertEqual(masked['class_type'],'SetLatentNoiseMask')
                outside=graph[masked['inputs']['mask'][0]]
                self.assertEqual(outside['class_type'],'InvertMask')
                self.assertEqual(outside['inputs']['mask'],['expand_canvas',1])
                latent=graph[masked['inputs']['samples'][0]]
                if batch>1:
                    self.assertEqual(latent['class_type'],'RepeatLatentBatch')
                    self.assertEqual(latent['inputs']['amount'],batch)
                    latent=graph[latent['inputs']['samples'][0]]
                self.assertEqual(latent['class_type'],'VAEEncode')
                self.assertEqual(latent['inputs']['pixels'],['expand_canvas',0])
                self.assertEqual(graph['save']['inputs']['source'],['expand_canvas',0])
                self.assertEqual(graph['save']['inputs']['mask'],['expand_canvas',1])
                self.assertEqual(graph['save']['inputs']['source_alpha'],['expand_canvas',2])
                self.assertEqual(graph['save']['inputs']['preservation'],'inside-mask')
                self.assertEqual(graph['save']['inputs']['feather'],0)
                self.assertTrue(graph['save']['inputs']['harmonize_outside'])

    def test_ordinary_generation_keeps_its_random_latent(self):
        graph=build_workflow({'model_id':'flux3-klein','effect_id':'create-image','provider':'local',
            'prompt':'A ceramic lamp','batch_size':2,'seed':42})
        latent=graph[graph['sample']['inputs']['latent_image'][0]]
        self.assertEqual(latent['class_type'],'EmptyFlux2LatentImage')
        self.assertEqual(latent['inputs']['batch_size'],2)
        self.assertNotIn('harmonize_outside',graph['save']['inputs'])


class ImagePreservationConditioningContract(TestCase):
    def test_both_preservation_modes_anchor_the_native_source(self):
        for mode in ('inside-mask', 'outside-mask'):
            for batch in (1, 2):
                with self.subTest(mode=mode, batch=batch):
                    graph=build_workflow({'model_id':'flux3-klein','effect_id':'edit-image','provider':'local',
                        'prompt':'Preserve the lamp and replace the background','image_preservation':mode,
                        'width':768,'height':1024,'batch_size':batch,'seed':42},
                        {'source':'original.png','mask':'paint.png'})
                    self.assertEqual(graph['mask']['class_type'],'OpenFrameLoadImageMask')
                    self.assertEqual(graph['mask']['inputs']['image'],'paint.png')
                    self.assertEqual(graph['edit_canvas']['inputs']['image'],['image',0])
                    self.assertEqual(graph['edit_canvas']['inputs']['mask'],['mask',0])
                    self.assertEqual(graph['edit_canvas']['inputs']['preservation'],mode)
                    self.assertEqual(graph['canvas_encode']['inputs']['pixels'],['edit_canvas',0])
                    self.assertEqual(graph['canvas_noise_mask']['inputs']['mask'],['edit_canvas',1])
                    self.assertEqual(graph['sample']['inputs']['latent_image'],['canvas_noise_mask',0])
                    self.assertEqual('canvas_batch' in graph,batch>1)
                    self.assertEqual(graph['save']['inputs']['mask'],['mask',0])
                    self.assertEqual(graph['save']['inputs']['source'],['image',0])
                    self.assertNotIn('harmonize_outside',graph['save']['inputs'])


class LongCatMergeContract(TestCase):
    def test_distillation_replaces_parameters_without_inplace_mapped_writes(self):
        graph=build_workflow({'model_id':'longcat-avatar-1.5','effect_id':'speak','provider':'local',
            'prompt':'A speaker facing the camera','seed':42})
        self.assertFalse(graph['distill']['inputs']['low_mem_load'])
        self.assertTrue(graph['distill']['inputs']['merge_loras'])
        self.assertEqual(graph['distill']['inputs']['strength'],1.0)
        self.assertEqual(graph['scheduler']['class_type'],'OpenFrameLongCat15Scheduler')


class Animate2RecipeContract(TestCase):
    def test_base_and_distilled_defaults_remain_distinct(self):
        for model,steps,guidance in [('wan-animate-2',40,3),('wan-animate-2-distilled',10,1)]:
            graph=build_workflow({'model_id':model,'effect_id':'motion-transfer','provider':'local',
                'prompt':'Character appearance: a woman in a blue jacket. Background: a grey studio.','seed':42})
            self.assertEqual(graph['sample']['inputs']['steps'],steps)
            self.assertEqual(graph['sample']['inputs']['cfg'],guidance)
            self.assertEqual(graph['sample']['inputs']['sampler_name'],'euler')
            self.assertEqual(graph['motion_prompt']['inputs']['text'],'')
            self.assertEqual(graph['condition']['inputs']['reference_image'],['reference_fit',0])
            self.assertEqual(graph['reference_vision']['inputs']['image'],['reference_fit',0])
            self.assertEqual(graph['reference_fit']['inputs']['image'],['reference',0])
            self.assertEqual(graph['reference_fit']['inputs']['crop'],'center')
            self.assertEqual(graph['reference_fit']['inputs']['upscale_method'],'area')

    def test_explicit_motion_caption_and_sampling_values_are_retained(self):
        graph=build_workflow({'model_id':'wan-animate-2','effect_id':'motion-transfer','provider':'local',
            'prompt':'A woman in a blue jacket','motion_prompt':'A person turns and raises one arm.',
            'steps':30,'guidance':4,'seed':42})
        self.assertEqual(graph['motion_prompt']['inputs']['text'],'A person turns and raises one arm.')
        self.assertEqual(graph['sample']['inputs']['steps'],30)
        self.assertEqual(graph['sample']['inputs']['cfg'],4)
