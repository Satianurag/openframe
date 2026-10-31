"""CPU/transport contract checks; doubles here are never Cloud GPU evidence."""
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

from engine import cloud
from engine.runner import JobCancelled, ProviderError
from engine.workflows import build_workflow, normalize_request


class CloudSubmissionGuard(unittest.TestCase):
    def test_cached_unavailable_cloud_is_rejected_before_queueing(self):
        from fastapi.testclient import TestClient
        from backend.app import create_app

        with tempfile.TemporaryDirectory(prefix="openframe-cloud-guard-") as temp:
            app = create_app(Path(temp))
            with TestClient(app) as client:
                saved = client.patch("/api/settings", json={"comfy_cloud_api_key": "test-only-api-key"})
                self.assertEqual(saved.status_code, 200, saved.text)
                app.state.provider_checks["comfy-cloud"] = {
                    "available": False,
                    "detail": "Cloud is authenticated, but this workspace has no remaining free runs or credits.",
                }
                response = client.post("/api/jobs", json={
                    "model_id": "ltx-0.9.8",
                    "effect_id": "text-to-video",
                    "provider": "comfy-cloud",
                    "prompt": "A moving test subject",
                    "width": 256,
                    "height": 256,
                    "frames": 9,
                    "fps": 8,
                    "steps": 1,
                })
                self.assertEqual(response.status_code, 422, response.text)
                self.assertIn("no remaining free runs", response.json()["detail"])
                self.assertNotIn("test-only-api-key", response.text)
                self.assertEqual(client.get("/api/jobs").json()["total"], 0)


class HostedCloudContract(unittest.TestCase):
    def request(self, effect="replace-object", **changes):
        return normalize_request(dict(job_id="contract-check", model_id="ltx-2.3", effect_id=effect,
            prompt="A black chess knight on the table", width=288, height=320, frames=9, fps=24,
            seed=46, mask_tracking_method="static", **changes))

    def test_native_graph_preserves_sampling_and_has_no_custom_utilities(self):
        for effect in ("text-to-video", "image-to-video", "replace-object", "remove-object", "restyle"):
            with self.subTest(effect=effect):
                request = self.request(effect)
                logical = build_workflow(request)
                original = copy.deepcopy(logical)
                graph = cloud.native_graph(logical, request, {"source": "prepared.mp4", "generation_mask": "mask.mp4"})
                self.assertEqual(logical, original)
                self.assertFalse(any(n["class_type"].startswith("OpenFrame") for n in graph.values()))
                for key in ("noise", "sampler", "sigmas", "sample", "refinement_noise", "refinement_sampler", "refinement_sigmas", "sample_refinement", "inpaint_lora"):
                    if key in logical:
                        self.assertEqual(graph[key], logical[key], key)
                for node in graph.values():
                    for value in node["inputs"].values():
                        if isinstance(value, list) and len(value) == 2:
                            self.assertIn(value[0], graph)
                if effect == "remove-object":
                    self.assertEqual(graph["green_guide_colour"]["inputs"]["width"], 160)
                    self.assertIn("sample_refinement", graph)
                if effect == "replace-object":
                    self.assertNotIn("sample_refinement", graph)
                self.assertEqual(graph["save"]["class_type"], "SaveImage")

    def test_exact_missing_weight_is_rejected_without_substitution(self):
        graph = {"model": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "ltx-2.3-22b-dev.safetensors"}}}
        catalog = {"CheckpointLoaderSimple": {"input": {"required": {"ckpt_name": ["COMBO", {"options": ["another-model.safetensors"]}]}}}}
        with self.assertRaisesRegex(ProviderError, "No model substitution"):
            cloud._validate(graph, catalog)

    def test_api_key_precedence_never_reads_cli_session(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(cloud, "find_cli", return_value="/installed/comfy"), patch.object(cloud, "_cli") as cli:
            status = cloud.auth_status({"comfy_cloud_api_key": "test-secret"}, refresh=True)
        self.assertEqual(status["mode"], "api-key")
        cli.assert_not_called()
        self.assertNotIn("test-secret", json.dumps(status))

    def test_local_sam2_capability_requires_exact_checkpoint_and_package_flag(self):
        from engine.cloud_tracking import tracker_status
        class Response:
            def raise_for_status(self): pass
            def json(self):
                return {"OpenFrameVideoInput": {"input": {"optional": {"tracking_method": [["sam2", "flow", "static"], metadata]}}}}
        for metadata, expected in (({"openframe_sam2_available": True, "openframe_sam2_checkpoint": "sam2.1_hiera_small.pt"}, True),
                                   ({"openframe_sam2_available": True, "openframe_sam2_checkpoint": "other.pt"}, False),
                                   ({"openframe_sam2_available": False, "openframe_sam2_checkpoint": "sam2.1_hiera_small.pt"}, False)):
            with patch("engine.cloud_tracking.httpx.get", return_value=Response()):
                self.assertEqual(tracker_status({})["available"], expected)

    def test_cli_transfer_cancellation_terminates_child_without_retry(self):
        from unittest.mock import MagicMock
        process = MagicMock()
        process.communicate.return_value = ("", "")
        with patch.object(cloud, "find_cli", return_value="/installed/comfy"), patch.object(cloud.subprocess, "Popen", return_value=process) as spawn:
            with self.assertRaises(JobCancelled):
                cloud._cli({}, ["download", "example", "--where", "cloud"], cancel=lambda: (_ for _ in ()).throw(JobCancelled("cancelled")))
        spawn.assert_called_once()
        process.terminate.assert_called_once()

    def test_auth_response_omits_tokens_and_custom_url_cannot_reuse_session(self):
        cloud._AUTH_CACHE.clear()
        payload = {"signed_in": True, "base_url": cloud.HOSTED_URL, "session": {"access_token": "do-not-expose"}}
        with patch.dict(os.environ, {}, clear=True), patch.object(cloud, "find_cli", return_value="/installed/comfy"), patch.object(cloud, "_cli", return_value=payload):
            status = cloud.auth_status({}, refresh=True)
            custom = cloud.auth_status({"comfy_cloud_url": "https://private.example"})
        self.assertEqual(status["mode"], "cli-oauth")
        self.assertEqual(custom["mode"], "missing")
        self.assertNotIn("do-not-expose", json.dumps(status))
        cloud._AUTH_CACHE.clear()

    def test_prepared_input_roundtrip_is_lossless_and_padding_is_not_stretched(self):
        from custom_nodes.openframe import media
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.mp4"
            subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=288x320:rate=24:duration=0.5", "-c:v", "libx264", str(source)], check=True)
            mask = root / "mask.png"
            image = np.zeros((320, 288), np.uint8); image[100:200, 90:190] = 255
            Image.fromarray(image).save(mask)
            request = self.request("remove-object")
            logical, prepared, original, alpha, tracking = cloud.prepare(request, {"source": source, "mask": mask}, root, lambda: None)
            decoded = media.decode_frames(prepared["source"], 320, 320, 24, 9)
            self.assertTrue(np.array_equal(decoded[:, :, :288], original))
            self.assertTrue(np.array_equal(decoded[:, :, 288:], np.repeat(original[:, :, -1:], 32, axis=2)))
            self.assertTrue((alpha[:, image == 0] == 0).all())
            generation = media.decode_frames(prepared["generation_mask"], 320, 320, 24, 9)
            self.assertTrue((generation[:, :, 288:] == 0).all())

    def test_cli_cancellation_is_confirmed_and_never_retried_as_submission(self):
        commands = []
        def command(settings, args, timeout=0):
            commands.append(args)
            if args[0] == "run":
                return {"prompt_id": "real-id-placeholder"}
            if args[:2] == ["jobs", "status"]:
                return {"status": "cancelled"}
            return {}
        count = 0
        def cancel():
            nonlocal count
            count += 1
            if count > 1:
                raise JobCancelled("User cancelled")
        with tempfile.TemporaryDirectory() as temp, patch.object(cloud, "_cli", side_effect=command):
            with self.assertRaises(JobCancelled):
                cloud._run_cli({}, {}, Path(temp), {}, lambda *_: None, cancel)
        self.assertEqual(sum(command[0] == "run" for command in commands), 1)
        self.assertTrue(any(command[:2] == ["jobs", "cancel"] for command in commands))
        self.assertEqual(commands[-1][:2], ["jobs", "status"])


if __name__ == "__main__":
    unittest.main()
