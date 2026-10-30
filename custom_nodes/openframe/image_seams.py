"""Outside-only colour continuity for a rectangular outpaint canvas.

A smooth harmonic RGB offset is fitted to the source boundary. It changes
low-frequency colour in generated pixels, not their positions or texture.
The source rectangle is never edited. This cannot repair generated geometry.
"""
import cv2
import numpy as np


def harmonize_outpaint(generated, source, protected, source_alpha=None, check_cancelled=None):
    height, width = generated.shape[:2]
    if source.shape != generated.shape or protected.shape != (height, width):
        raise ValueError("Outpaint colour continuity requires matching original and generated canvases.")
    if height > 4096 or width > 4096:
        raise ValueError("Outpaint colour continuity is bounded to 4096 pixels per side.")
    keep = protected >= 0.5
    rows, cols = np.flatnonzero(keep.any(axis=1)), np.flatnonzero(keep.any(axis=0))
    if not len(rows):
        raise ValueError("Outpaint colour continuity requires the original image rectangle.")
    top, bottom, left, right = int(rows.min()), int(rows.max()) + 1, int(cols.min()), int(cols.max()) + 1
    if np.count_nonzero(keep) != (bottom - top) * (right - left) or np.any((protected != 0) & (protected != 1)):
        raise ValueError("Outpaint colour continuity requires a binary rectangular preservation mask.")
    alpha = np.ones((height, width), np.float32) if source_alpha is None else np.clip(source_alpha, 0, 1)
    if alpha.shape != (height, width):
        raise ValueError("Original opacity must match the outpaint canvas.")
    edges = {}
    # First-order continuation of the original normal gradient; smoothing is
    # applied only to this offset, never to either image. Invisible original RGB
    # must not impose a colour on the newly generated surroundings.
    if left:
        edges['left'] = (2 * source[top:bottom, left] - source[top:bottom, min(left + 1, right - 1)] - generated[top:bottom, left - 1]) * alpha[top:bottom, left, None]
    if right < width:
        edges['right'] = (2 * source[top:bottom, right - 1] - source[top:bottom, max(left, right - 2)] - generated[top:bottom, right]) * alpha[top:bottom, right - 1, None]
    if top:
        edges['top'] = (2 * source[top, left:right] - source[min(top + 1, bottom - 1), left:right] - generated[top - 1, left:right]) * alpha[top, left:right, None]
    if bottom < height:
        edges['bottom'] = (2 * source[bottom - 1, left:right] - source[max(top, bottom - 2), left:right] - generated[bottom, left:right]) * alpha[bottom - 1, left:right, None]
    edges = {key: cv2.GaussianBlur(value[:, None, :], (1, 0), sigmaX=0, sigmaY=4)[:, 0] for key, value in edges.items()}
    sizes = [(width, height)]
    while max(sizes[-1]) > 32:
        w, h = sizes[-1]
        sizes.append((max(2, (w + 1) // 2), max(2, (h + 1) // 2)))
    kernel = np.array([[0, .25, 0], [.25, 0, .25], [0, .25, 0]], np.float32)
    result = generated.copy()
    max_offset, squared_offset, iterations = 0., 0., 0
    for channel in range(3):
        field = None
        for level, (w, h) in enumerate(reversed(sizes)):
            if check_cancelled:
                check_cancelled()
            x0, x1 = round(left * w / width), round(right * w / width)
            y0, y1 = round(top * h / height), round(bottom * h / height)
            x0, y0 = min(x0, w - 1), min(y0, h - 1)
            x1, y1 = max(x0 + 1, x1), max(y0 + 1, y1)
            field = np.zeros((h, w), np.float32) if field is None else cv2.resize(field, (w, h), interpolation=cv2.INTER_LINEAR)
            fixed = np.zeros((h, w), bool)
            values = np.zeros((h, w), np.float32)
            fixed[y0:y1, x0:x1] = True
            # Zero offset at the far edge of each added region. When an original
            # touches a canvas edge, BORDER_REPLICATE supplies a Neumann edge.
            if left: fixed[:, 0] = True
            if right < width: fixed[:, -1] = True
            if top: fixed[0] = True
            if bottom < height: fixed[-1] = True
            for side, residual in edges.items():
                vertical = side in {'left', 'right'}
                count = y1 - y0 if vertical else x1 - x0
                line = cv2.resize(residual[:, channel, None], (1, count), interpolation=cv2.INTER_AREA).ravel()
                if side == 'left' and x0:
                    fixed[y0:y1, x0 - 1], values[y0:y1, x0 - 1] = True, line
                elif side == 'right' and x1 < w:
                    fixed[y0:y1, x1], values[y0:y1, x1] = True, line
                elif side == 'top' and y0:
                    fixed[y0 - 1, x0:x1], values[y0 - 1, x0:x1] = True, line
                elif side == 'bottom' and y1 < h:
                    fixed[y1, x0:x1], values[y1, x0:x1] = True, line
            np.copyto(field, values, where=fixed)
            buffer = np.empty_like(field)
            tolerance = max(1e-8, float(np.max(np.abs(values))) * 1e-4)
            # A fixed multiresolution budget keeps work linear in pixel count;
            # low frequencies settle on coarse grids before fine boundary detail.
            limit = 512 if level == 0 else 96 if max(w, h) <= 256 else 48
            for step in range(limit):
                cv2.filter2D(field, -1, kernel, dst=buffer, borderType=cv2.BORDER_REPLICATE)
                np.copyto(buffer, values, where=fixed)
                iterations += 1
                converged = step % 16 == 15 and cv2.norm(buffer, field, cv2.NORM_INF) < tolerance
                field, buffer = buffer, field
                if step % 16 == 15 and check_cancelled:
                    check_cancelled()
                if converged:
                    break
        max_offset = max(max_offset, float(np.max(np.abs(field))))
        squared_offset += float(np.sum(np.square(field), dtype=np.float64))
        result[..., channel] = np.clip(result[..., channel] + field, 0, 1)
    np.copyto(result, source, where=keep[..., None])
    return result, {'method': 'outside-harmonic-rgb-v1', 'original_bounds': {'left': left, 'top': top, 'right': right, 'bottom': bottom},
                    'boundary_offset_sigma_px': 4, 'solver': 'bounded coarse-to-fine Jacobi', 'solver_iterations': iterations,
                    'max_abs_rgb_offset': max_offset, 'rms_rgb_offset': (squared_offset / max(1, 3 * np.count_nonzero(~keep))) ** .5,
                    'original_pixels_modified': 0, 'geometry_repaired': False, 'transparent_boundary_weight': 'source opacity'}
