"""Minimal eligibility probe: no weights, no application dependencies."""
import os
import modal
app = modal.App("openframe-gpu-availability")
@app.function(image=modal.Image.debian_slim(), gpu=os.environ.get("OPENFRAME_PROBE_GPU", "T4"), timeout=60, scaledown_window=2)
def device():
    import subprocess
    return subprocess.check_output(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"], text=True).strip()
@app.local_entrypoint()
def main():
    print(device.remote())
