"""Isolated API/storage tests. Inference is explicitly a test double, never GPU evidence."""
from __future__ import annotations

import copy
import io
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
import unittest
import uuid
import zipfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image

from backend.app import create_app
from backend.store import Store, now
from engine.runner import JobCancelled
from engine.workflows import build_workflow


class BackendIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture_dir = tempfile.TemporaryDirectory(prefix="openframe-api-fixtures-")
        cls.video = Path(cls.fixture_dir.name) / "source.mp4"
        subprocess.run([
            "ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=256x256:rate=8:duration=2",
            "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=16000:duration=2", "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-shortest", str(cls.video)
        ], check=True, timeout=30)
        buffer = io.BytesIO()
        Image.new("RGB", (256, 256), "white").save(buffer, "PNG")
        cls.mask = buffer.getvalue()

    @classmethod
    def tearDownClass(cls):
        cls.fixture_dir.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="openframe-api-test-")
        self.root = Path(self.temp.name)
        self.started = threading.Event()
        self.calls = []
        self.patch = patch("engine.runner.run_job", self.fake_runner)
        self.patch.start()
        self.app = create_app(self.root)
        self.client = TestClient(self.app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.patch.stop()
        self.temp.cleanup()

    def fake_runner(self, request, assets, output_dir, settings, on_progress, is_cancelled):
        self.calls.append(dict(request))
        self.started.set()
        if request["prompt"] == "block until cancelled":
            deadline = time.monotonic() + 5
            while not is_cancelled() and time.monotonic() < deadline:
                time.sleep(0.01)
            if is_cancelled():
                raise JobCancelled("Test cancellation")
            raise RuntimeError("Test timed out waiting for cancellation")
        if request["prompt"] == "fail explicitly":
            raise RuntimeError("Deliberate test engine error")
        on_progress(0.5, "Test double processing; no GPU inference")
        result = Path(output_dir) / "result.mp4"
        shutil.copyfile(self.video, result)
        filenames = {"source": "uploaded_source.mp4", "mask": "uploaded_mask.png", "reference": "uploaded_reference.png"}
        graph = build_workflow(request, {role: filenames[role] for role in assets})
        return {"outputs": [{"path": str(result), "kind": "video", "role": "result"}], "workflow": graph,
                "ui_workflow": {"version": 0.4, "nodes": [{"widgets_values": ["uploaded_source.mp4", "uploaded_mask.png"]}], "links": []},
                "metadata": {"execution": "test-double; not GPU evidence"}}

    def request(self, **changes):
        request = {"model_id": "ltx-0.9.8", "effect_id": "text-to-video", "provider": "local",
                   "prompt": "A moving test subject", "width": 256, "height": 256, "frames": 9, "fps": 8, "steps": 1}
        request.update(changes)
        return request

    def upload_video(self):
        with self.video.open("rb") as handle:
            response = self.client.post("/api/assets", files={"file": ("source.mp4", handle, "video/mp4")})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def upload_mask(self, name="mask.png"):
        response = self.client.post("/api/assets", files={"file": (name, self.mask, "image/png")})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def submit(self, **changes):
        response = self.client.post("/api/jobs", json=self.request(**changes))
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def wait(self, ident, expected="succeeded"):
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            job = self.client.get(f"/api/jobs/{ident}").json()
            if job["status"] in {"succeeded", "failed", "cancelled"}:
                self.assertEqual(job["status"], expected, job)
                return job
            time.sleep(0.02)
        self.fail(f"Job {ident} did not reach {expected}")

    def test_catalog_health_settings_and_redaction(self):
        self.assertEqual(self.client.get("/api/health").json()["status"], "ok")
        catalogue = self.client.get("/api/catalog").json()
        self.assertEqual({p["id"] for p in catalogue["providers"]}, {"local", "modal", "comfy-cloud"})
        secret = "test-only-provider-secret-value"
        result = self.client.patch("/api/settings", json={"comfy_cloud_api_key": secret, "default_provider": "modal"})
        self.assertEqual(result.status_code, 200, result.text)
        self.assertNotIn(secret, result.text)
        self.assertTrue(result.json()["has_comfy_cloud_api_key"])
        self.assertNotIn(secret, self.client.get("/api/settings").text)
        with patch("engine.runner.check_provider", side_effect=RuntimeError("Provider says " + secret)):
            checked = self.client.post("/api/providers/comfy-cloud/check")
        self.assertFalse(checked.json()["available"])
        self.assertNotIn(secret, checked.text)
        invalid = self.client.patch("/api/settings", json={"comfy_url": f"https://user:{secret}@example.org"})
        self.assertEqual(invalid.status_code, 422)
        self.assertNotIn(secret, invalid.text)
        invalid = self.client.patch("/api/settings", json={"unknown_token": secret})
        self.assertEqual(invalid.status_code, 422)
        self.assertNotIn(secret, invalid.text)
        self.assertEqual(self.client.post("/api/providers/unknown/check").status_code, 404)

    def test_upload_dedup_frames_ranges_and_invalid_media(self):
        asset = self.upload_video()
        self.assertEqual(asset["kind"], "video")
        self.assertTrue(asset["has_audio"])
        self.assertEqual(asset["width"], 256)
        self.assertNotIn("path", asset)
        self.assertEqual(self.upload_video()["id"], asset["id"])
        self.assertEqual(self.client.get(asset["thumbnail_url"]).status_code, 200)
        frame = self.client.get(f"/api/assets/{asset['id']}/frame?time=0.5")
        self.assertEqual(frame.status_code, 200, frame.text[:200] if frame.status_code != 200 else "")
        self.assertTrue(frame.content.startswith(b"\x89PNG"))
        partial = self.client.get(asset["url"], headers={"Range": "bytes=0-31"})
        self.assertEqual(partial.status_code, 206)
        self.assertEqual(len(partial.content), 32)
        self.assertEqual(self.client.get(f"/api/assets/{asset['id']}/frame?time=99").status_code, 422)
        mask = self.upload_mask("../../mask.png")
        self.assertEqual(mask["name"], "mask.png")
        self.assertEqual(self.client.get(f"/api/assets/{mask['id']}/frame").headers["content-type"], "image/png")
        invalid = self.client.post("/api/assets", files={"file": ("x.png", b"<html>not an image</html>", "image/png")})
        self.assertEqual(invalid.status_code, 422)
        self.assertEqual(self.client.post("/api/assets", files={"file": ("empty.png", b"", "image/png")}).status_code, 422)
        with patch.dict(os.environ, {"OPENFRAME_MAX_UPLOAD_MB": "1"}):
            large = self.client.post("/api/assets", files={"file": ("large.bin", b"x" * (1024 * 1024 + 1))})
        self.assertEqual(large.status_code, 413)
        self.assertEqual(list((self.root / "uploads").glob("*")), [])

    def test_render_validation_and_defaults(self):
        for changes in ({"width": 257}, {"frames": 10}, {"frames": 249}, {"steps": 51},
                        {"model_id": "missing"}, {"provider": "missing"}, {"effect_id": "remove-object"},
                        {"mask_tracking_method": "imaginary"}, {"seed": 2**53}, {"comfy_api_key": "secret"}):
            response = self.client.post("/api/jobs", json=self.request(**changes))
            self.assertEqual(response.status_code, 422, (changes, response.text))
        response = self.client.post("/api/jobs", json={"model_id": "wan-vace", "prompt": "A mountain shot", "width": 256, "height": 256})
        self.assertEqual(response.status_code, 201, response.text)
        request = response.json()["request"]
        self.assertEqual(request["fps"], 16)
        self.assertEqual(request["frames"], 81)
        self.assertEqual(request["steps"], 20)
        self.assertTrue(0 <= request["seed"] < 2**32)
        self.wait(response.json()["id"])

    def test_source_duration_mask_requirements_and_tracking(self):
        source = self.upload_video()
        mask = self.upload_mask()
        request = self.request(model_id="ltx-2.3", effect_id="remove-object", source_asset_id=source["id"])
        self.assertEqual(self.client.post("/api/jobs", json=request).status_code, 422)
        request.update(mask_asset_id=mask["id"], frames=25)
        self.assertEqual(self.client.post("/api/jobs", json=request).status_code, 422)
        # A two-second 8fps source has 16 frames, not the 17 an LTX request would need.
        request.update(frames=17, fps=8)
        boundary = self.client.post("/api/jobs", json=request)
        self.assertEqual(boundary.status_code, 422, boundary.text)
        self.assertIn("only 2.00s remains", boundary.json()["detail"])
        request.update(frames=9, trim_start=1.8)
        self.assertEqual(self.client.post("/api/jobs", json=request).status_code, 422)
        request.update(trim_start=0, mask_tracking=False)
        response = self.client.post("/api/jobs", json=request)
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["request"]["mask_tracking_method"], "static")
        self.assertTrue(response.json()["warnings"])
        self.wait(response.json()["id"])

    def test_success_favorite_retry_exports_and_reference_protection(self):
        job = self.wait(self.submit()["id"])
        self.assertEqual(job["progress"], 1)
        self.assertEqual(job["outputs"][0]["role"], "result")
        self.assertEqual(self.client.patch(f"/api/jobs/{job['id']}", json={"favorite": True}).json()["favorite"], True)
        self.assertEqual(self.client.get(f"/api/jobs/{job['id']}/workflow").status_code, 200)
        self.assertEqual(self.client.get(f"/api/jobs/{job['id']}/workflow?format=ui").status_code, 200)
        output_id = job["outputs"][0]["id"]
        self.assertEqual(self.client.delete(f"/api/assets/{output_id}").status_code, 409)
        retry = self.client.post(f"/api/jobs/{job['id']}/retry")
        self.assertEqual(retry.status_code, 201, retry.text)
        self.assertNotEqual(retry.json()["id"], job["id"])
        self.assertEqual(retry.json()["request"]["seed"], job["request"]["seed"])
        self.wait(retry.json()["id"])
        self.assertEqual(self.client.delete(f"/api/jobs/{job['id']}").status_code, 200)
        self.assertEqual(self.client.delete(f"/api/jobs/{retry.json()['id']}").status_code, 200)
        self.assertEqual(self.client.delete(f"/api/assets/{output_id}").status_code, 200)

    def test_cancel_queued_and_running_and_explicit_failure(self):
        running = self.submit(prompt="block until cancelled")
        self.assertTrue(self.started.wait(3))
        pending = self.submit()
        self.assertEqual(self.client.delete(f"/api/jobs/{running['id']}").status_code, 409)
        self.assertEqual(self.client.post(f"/api/jobs/{running['id']}/retry").status_code, 409)
        self.assertEqual(self.client.post(f"/api/jobs/{pending['id']}/cancel").json()["status"], "cancelled")
        self.client.post(f"/api/jobs/{running['id']}/cancel")
        self.wait(running["id"], "cancelled")
        self.assertEqual(len(self.calls), 1)
        failed = self.wait(self.submit(prompt="fail explicitly")["id"], "failed")
        self.assertIn("Deliberate test engine error", failed["error"])
        self.assertFalse(failed["outputs"])

    def test_hybrid_bundle_distinguishes_local_recipe_from_cloud_execution(self):
        from engine.cloud import native_graph
        source, mask = self.upload_video(), self.upload_mask()
        public = self.wait(self.submit(model_id="ltx-2.3", effect_id="replace-object", source_asset_id=source["id"], mask_asset_id=mask["id"], mask_tracking=False)["id"])
        job = self.app.state.store.get("jobs", public["id"])
        request = dict(job["request"], job_id=job["id"])
        cloud_graph = native_graph(job["workflow"], request, {"source": "uploaded-cloud-source.mp4", "generation_mask": "uploaded-cloud-mask.mp4"})
        directory = self.root / "renders" / job["id"] / "cloud-input"
        directory.mkdir(exist_ok=True)
        (directory / "prepared-source.mp4").write_bytes(self.video.read_bytes())
        (directory / "prepared-mask.mp4").write_bytes(self.video.read_bytes())
        metadata = {"execution": "hosted-cloud-diffusion-local-media", "cloud_workflow": cloud_graph,
                    "prepared_inputs": {role: {"filename": f"prepared-{name}.mp4", "relative_path": f"cloud-input/prepared-{name}.mp4"}
                                        for role, name in (("source", "source"), ("generation_mask", "mask"))},
                    "processing": {"composite": "shared-custom-node-media-helper"}}
        self.app.state.store.update_job(job["id"], {"metadata": metadata})
        with patch("engine.workflows.build_workflow", side_effect=AssertionError("Stored recipes must not be rebuilt")):
            response = self.client.get(f"/api/jobs/{job['id']}/bundle?include_media=true")
        self.assertEqual(response.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            self.assertEqual(json.loads(archive.read("workflow_executed_api.json")), cloud_graph)
            self.assertEqual(json.loads(archive.read("workflow_api.json"))["source"]["class_type"], "OpenFrameVideoInput")
            portable_cloud = json.loads(archive.read("workflow_cloud_api.json"))
            for node in ("cloud_source_file", "cloud_mask_file"):
                self.assertIn("input/" + portable_cloud[node]["inputs"]["file"], archive.namelist())
            self.assertIn("custom_nodes/openframe/media.py", archive.namelist())
            self.assertIn("diffusion graph", json.loads(archive.read("manifest.json"))["graph_note"])
            self.assertIn("not the final composite", archive.read("README.txt").decode())

    def test_full_bundle_media_roundtrip_and_portable_graph(self):
        source = self.upload_video()
        mask = self.upload_mask()
        job = self.wait(self.submit(model_id="ltx-2.3", effect_id="remove-object", source_asset_id=source["id"], mask_asset_id=mask["id"])["id"])
        response = self.client.get(f"/api/jobs/{job['id']}/bundle?include_media=true")
        self.assertEqual(response.status_code, 200, response.text[:200] if response.status_code != 200 else "")
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            self.assertIsNone(archive.testzip())
            manifest = json.loads(archive.read("manifest.json"))
            graph = json.loads(archive.read("workflow_api.json"))
            for role, expected in (("source", self.video.read_bytes()), ("mask", self.mask)):
                entry = manifest["inputs"][role]
                self.assertEqual(archive.read(entry["archive_path"]), expected)
                field = "filename" if role == "source" else "mask_filename"
                self.assertEqual(graph["source"]["inputs"][field], entry["comfy_filename"])
            self.assertEqual(graph["save"]["inputs"]["source_filename"], manifest["inputs"]["source"]["comfy_filename"])
            original = json.loads(archive.read("workflow_executed_api.json"))
            self.assertEqual(original["source"]["inputs"]["filename"], "uploaded_source.mp4")
            ui = json.loads(archive.read("workflow_ui.json"))
            self.assertEqual(ui["nodes"][0]["widgets_values"][0], manifest["inputs"]["source"]["comfy_filename"])
            requirements = json.loads(archive.read("MODEL-REQUIREMENTS.json"))
            self.assertTrue(any(entry["category"] == "sam2" for entry in requirements["model_files"]))
            self.assertTrue(any(entry.get("tasks") == ["inpaint"] for entry in requirements["model_files"]))
            self.assertEqual(requirements["sam2_package"]["repository"], "https://github.com/facebookresearch/sam2.git")
            self.assertIn("SAM2_BUILD_CUDA=0", archive.read("README.txt").decode())
            self.assertIn("https://huggingface.co/Lightricks/LTX-2.3-22b-IC-LoRA-In-Outpainting", archive.read("README.txt").decode())
            self.assertIn("ffmpeg and ffprobe", archive.read("README.txt").decode())
            self.assertIn("custom_nodes/openframe/nodes.py", archive.namelist())
        light = self.client.get(f"/api/jobs/{job['id']}/bundle")
        with zipfile.ZipFile(io.BytesIO(light.content)) as archive:
            self.assertFalse(any(name.startswith("input/") for name in archive.namelist()))
        static = self.wait(self.submit(model_id="ltx-2.3", effect_id="remove-object", source_asset_id=source["id"], mask_asset_id=mask["id"], mask_tracking=False)["id"])
        static_bundle = self.client.get(f"/api/jobs/{static['id']}/bundle")
        with zipfile.ZipFile(io.BytesIO(static_bundle.content)) as archive:
            requirements = json.loads(archive.read("MODEL-REQUIREMENTS.json"))
            self.assertFalse(any(entry["category"] == "sam2" for entry in requirements["model_files"]))
            self.assertNotIn("sam2_package", requirements)
        generation = self.wait(self.submit(model_id="ltx-2.3")["id"])
        generation_bundle = self.client.get(f"/api/jobs/{generation['id']}/bundle")
        with zipfile.ZipFile(io.BytesIO(generation_bundle.content)) as archive:
            requirements = json.loads(archive.read("MODEL-REQUIREMENTS.json"))
            self.assertFalse(any(entry.get("tasks") for entry in requirements["model_files"]))
            self.assertFalse(any(entry["category"] == "sam2" for entry in requirements["model_files"]))
        self.assertFalse(list(self.root.rglob("*.zip")))

    def test_job_exports_preserve_executed_graph_after_template_changes(self):
        source = self.upload_video()
        mask = self.upload_mask()
        job = self.wait(self.submit(model_id="ltx-2.3", effect_id="remove-object",
                                    source_asset_id=source["id"], mask_asset_id=mask["id"])["id"])
        executed = self.app.state.store.get("jobs", job["id"])["workflow"]
        future_graph = {"future_template": {"class_type": "DifferentSampler", "inputs": {"steps": 99}}}
        with patch("engine.workflows.build_workflow", return_value=future_graph) as changed_template:
            direct = self.client.get(f"/api/jobs/{job['id']}/workflow")
            self.assertEqual(direct.status_code, 200)
            self.assertEqual(direct.json(), executed)
            for include_media in (False, True):
                response = self.client.get(f"/api/jobs/{job['id']}/bundle",
                                           params={"include_media": str(include_media).lower()})
                self.assertEqual(response.status_code, 200)
                with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
                    manifest = json.loads(archive.read("manifest.json"))
                    expected = copy.deepcopy(executed)
                    expected["source"]["inputs"]["filename"] = manifest["inputs"]["source"]["comfy_filename"]
                    expected["source"]["inputs"]["mask_filename"] = manifest["inputs"]["mask"]["comfy_filename"]
                    expected["save"]["inputs"]["source_filename"] = manifest["inputs"]["source"]["comfy_filename"]
                    self.assertEqual(json.loads(archive.read("workflow_api.json")), expected)
                    self.assertEqual(json.loads(archive.read("workflow_executed_api.json")), executed)
            changed_template.assert_not_called()
        self.assertEqual(self.app.state.store.get("jobs", job["id"])["workflow"], executed)

    def test_presets_origin_guard_and_missing_resources(self):
        preset = self.client.post("/api/presets", json={"name": "Repeatable preset", "request": self.request()})
        self.assertEqual(preset.status_code, 201, preset.text)
        self.assertIsNone(preset.json()["request"]["source_asset_id"])
        self.assertEqual(len(self.client.get("/api/presets").json()["items"]), 1)
        self.assertEqual(self.client.delete(f"/api/presets/{preset.json()['id']}").status_code, 200)
        hostile = self.client.post("/api/jobs", json=self.request(), headers={"Origin": "https://unrelated.example"})
        self.assertEqual(hostile.status_code, 403)
        for path in ("/api/assets/missing", "/api/jobs/missing", "/api/no-such-route"):
            self.assertEqual(self.client.get(path).status_code, 404)

    def test_engine_cannot_report_success_without_owned_nonempty_media(self):
        for result, expected in (
            ({"outputs": []}, "without any video"),
            ({"outputs": [{"path": str(self.video)}]}, "invalid output file"),
        ):
            with patch("engine.runner.run_job", return_value=result):
                job = self.wait(self.submit()["id"], "failed")
                self.assertIn(expected, job["error"])
                self.assertFalse(job["outputs"])
        self.client.patch("/api/settings", json={"comfy_api_key": "test-secret-in-error"})
        with patch("engine.runner.run_job", side_effect=RuntimeError("Rejected test-secret-in-error")):
            job = self.wait(self.submit()["id"], "failed")
        self.assertNotIn("test-secret-in-error", job["error"])
        self.assertIn("[redacted]", job["error"])

    def test_api_export_and_saved_settings_survive_restart(self):
        exported = self.client.post("/api/workflows/export", json=self.request(seed=321))
        self.assertEqual(exported.status_code, 200, exported.text)
        self.assertIn("attachment", exported.headers["content-disposition"])
        self.assertEqual(exported.json()["noise"]["inputs"]["noise_seed"], 321)
        invalid = self.client.post("/api/workflows/export", json=self.request(frames=10))
        self.assertEqual(invalid.status_code, 422)
        self.client.patch("/api/settings", json={"default_provider": "modal", "comfy_cloud_api_key": "persisted-test-secret"})
        job = self.wait(self.submit()["id"])
        self.client.patch(f"/api/jobs/{job['id']}", json={"favorite": True})
        self.client.__exit__(None, None, None)
        self.client = TestClient(create_app(self.root))
        self.client.__enter__()
        settings = self.client.get("/api/settings")
        self.assertEqual(settings.json()["default_provider"], "modal")
        self.assertTrue(settings.json()["has_comfy_cloud_api_key"])
        self.assertNotIn("persisted-test-secret", settings.text)
        self.assertTrue(self.client.get(f"/api/jobs/{job['id']}").json()["favorite"])

    def test_restart_recovers_running_without_resubmission_and_resumes_queue(self):
        self.client.__exit__(None, None, None)
        store = Store(self.root)
        timestamp = now()
        running_id, queued_id = uuid.uuid4().hex, uuid.uuid4().hex
        for ident, state in ((running_id, "running"), (queued_id, "queued")):
            store.insert("jobs", {"id": ident, "status": state, "created_at": timestamp, "updated_at": timestamp,
                                  "request": self.request(seed=42), "progress": 0, "stage": state,
                                  "outputs": [], "error": None, "favorite": False})
        self.client = TestClient(create_app(self.root))
        self.client.__enter__()
        interrupted = self.client.get(f"/api/jobs/{running_id}").json()
        self.assertEqual(interrupted["status"], "failed")
        self.assertIn("remote job may still be running", interrupted["error"])
        self.wait(queued_id)
        self.assertEqual(len(self.calls), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
