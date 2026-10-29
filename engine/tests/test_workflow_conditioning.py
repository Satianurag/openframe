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
