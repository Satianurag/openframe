"""Graph contracts for the official LTX 2.5 Ingredients reference-sheet path."""
from unittest import TestCase

from engine.workflows import WorkflowError, build_workflow, normalize_request


def _request(**overrides):
    request = {"model_id": "ltx-2.5", "effect_id": "reference-to-video",
               "prompt": "The woman from the sheet walks through the location on the sheet.",
               "width": 960, "height": 544, "frames": 97, "fps": 24,
               "steps": 8, "guidance": 1, "seed": 42}
    request.update(overrides)
    return request


class ReferenceVideoGraph(TestCase):
    def test_three_references_build_one_sheet_and_the_official_ingredients_guide(self):
        assets = {"reference_0": "a.png", "reference_1": "b.png", "reference_2": "c.png"}
        graph = build_workflow(_request(generate_audio=True, reference_asset_ids=["a", "b", "c"]), assets)

        loads = [node for node in graph.values() if node["class_type"] == "LoadImage"]
        self.assertEqual(len(loads), 3)
        self.assertEqual([node["inputs"]["image"] for node in loads], ["a.png", "b.png", "c.png"])

        sheet = graph["reference_sheet"]
        self.assertEqual(sheet["class_type"], "OpenFrameReferenceSheet")
        self.assertEqual(sheet["inputs"]["columns"], 3)
        self.assertEqual(sheet["inputs"]["width"], 960)
        self.assertEqual(sheet["inputs"]["height"], 544)
        self.assertEqual([sheet["inputs"][f"image_{index}"] for index in range(1, 4)],
                         [["reference_0", 0], ["reference_1", 0], ["reference_2", 0]])

        adapter = graph["adapter"]
        self.assertEqual(adapter["class_type"], "LTXICLoRALoaderModelOnly")
        self.assertEqual(adapter["inputs"]["lora_name"], "ltx-2.3-22b-ic-lora-ingredients-0.9.safetensors")
        self.assertEqual(adapter["inputs"]["strength_model"], 1.3)

        repeat = graph["repeat_reference_sheet"]
        self.assertEqual(repeat["inputs"]["amount"], 97)
        self.assertEqual(repeat["inputs"]["image"], ["reference_sheet", 0])
        guide = graph["guide"]
        self.assertEqual(guide["class_type"], "LTXAddVideoICLoRAGuide")
        self.assertEqual(guide["inputs"]["image"], ["repeat_reference_sheet", 0])
        self.assertEqual(guide["inputs"]["latent_downscale_factor"], ["adapter", 1])
        self.assertEqual(graph["empty"]["inputs"]["length"], 97)
        self.assertIn("crop_guides", graph)

        classes = {node["class_type"] for node in graph.values()}
        for name in ("LTXVEmptyLatentAudio", "LTXVConcatAVLatent", "LTXVAudioVAEDecode", "LTXVSeparateAVLatent"):
            self.assertIn(name, classes)
        self.assertEqual(graph["save"]["inputs"]["audio"], ["decode_audio", 0])
        self.assertNotIn("source", graph)
        self.assertNotIn("source_audio", graph)

    def test_frames_must_remain_eight_n_plus_one(self):
        assets = {"reference_0": "a.png"}
        self.assertEqual(build_workflow(_request(frames=89, reference_asset_ids=["a"]), assets)["empty"]["inputs"]["length"], 89)
        with self.assertRaises(WorkflowError):
            build_workflow(_request(frames=100, reference_asset_ids=["a"]), assets)


class ReferenceLimits(TestCase):
    def test_nine_references_are_accepted_and_ten_are_rejected(self):
        nine = [f"reference-{index}" for index in range(9)]
        normalized = normalize_request(_request(reference_asset_ids=nine))
        self.assertEqual(normalized["reference_asset_ids"], nine)
        with self.assertRaises(WorkflowError):
            normalize_request(_request(reference_asset_ids=nine + ["reference-9"]))

    def test_existing_single_reference_video_tasks_keep_their_limit(self):
        for effect in ("image-to-video", "transition-video"):
            with self.subTest(effect=effect):
                request = {"model_id": "ltx-2.5", "effect_id": effect, "prompt": "Move",
                           "reference_asset_ids": ["one", "two"], "source_asset_id": "source"}
                with self.assertRaises(WorkflowError):
                    normalize_request(request)

    def test_reference_video_requires_at_least_one_reference(self):
        with self.assertRaises(WorkflowError):
            normalize_request(_request(reference_asset_ids=[]))
        with self.assertRaises(WorkflowError):
            normalize_request(_request(reference_asset_id="single"))


class ReferencePromptAndAudio(TestCase):
    def test_prompt_is_required(self):
        with self.assertRaises(WorkflowError):
            normalize_request(_request(prompt="   ", reference_asset_ids=["one"]))

    def test_audio_toggle_matches_other_generation_paths(self):
        assets = {"reference_0": "a.png"}
        generated = build_workflow(_request(generate_audio=True, reference_asset_ids=["one"]), assets)
        silent = build_workflow(_request(generate_audio=False, reference_asset_ids=["one"]), assets)
        self.assertIn("decode_audio", generated)
        self.assertEqual(generated["save"]["inputs"]["audio"], ["decode_audio", 0])
        self.assertNotIn("decode_audio", silent)
        self.assertNotIn("audio", silent["save"]["inputs"])
