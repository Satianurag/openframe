"""Global post-render brightness; not physical light power or EV exposure.

Brightness operation adapted from ReLight.apply_color_correction:
https://github.com/EnragedAntelope/comfyui-relight/blob/
79a182d51ededb7b2008097e2691046ac4d30fd6/relight.py#L432

MIT License
Copyright (c) 2025 EnragedAntelope

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
import torch


class OpenFrameImageBrightness:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "image": ("IMAGE",),
            "brightness": ("FLOAT", {"default": 0, "min": -100, "max": 100, "step": 1}),
        }}

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "adjust"
    CATEGORY = "OpenFrame/Image"
    DESCRIPTION = "Post-render encoded-RGB brightness adjustment. Preserves shadow geometry and alpha; high gains can clip. Not physical light power or EV exposure."

    def adjust(self, image, brightness):
        if not -100 <= brightness <= 100:
            raise ValueError("Post-render brightness must be between -100 and 100 percent")
        rgb = image[..., :3].float()
        # Preserve the released operation's 0.1-percent identity threshold.
        gain = 1 + brightness / 100 if abs(brightness) > .1 else 1
        adjusted = (rgb * gain).clamp(0, 1)
        if image.shape[-1] == 4:
            adjusted = torch.cat((adjusted, image[..., 3:4]), dim=-1)
        return {"result": (adjusted,), "ui": {"openframe_image_brightness": [{
            "adjustment_percent": brightness, "encoded_rgb_gain": gain,
            "method": "encoded-rgb-multiply-clamp", "alpha_preserved": True,
            "source_revision": "79a182d51ededb7b2008097e2691046ac4d30fd6",
        }]}}
