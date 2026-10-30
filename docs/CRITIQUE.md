# Quality review principles and retained limitations

A completed model job, correct file dimensions or low outside-mask error does not by itself prove an acceptable transformation. Review the entire selected interval against the source, including occlusion, identity, motion, shadows, boundary color, audio and exact export semantics.

Known failure categories remain explicit:

- Removal can leave ghosts or incorrect shadows even with an exact preservation mask. Include affected shadows/context in the edit region and review the generated fill.
- Replacement can preserve motion broadly while changing product geometry or identity. Edited-start-image and plate fitting improve particular cases, not arbitrary fidelity.
- Strong video restyling may alter people, props, gestures or background figures. Katana's optional EditVid source-motion approach passed a bounded full interval but still regenerates detail and uses non-commercial weights.
- Prompt-only lighting directions can fail. Dedicated lighting workflows improve control, but physical accuracy, fine texture and matte boundaries still require review.
- Character adapters may execute correctly without learning acceptable likeness. The reviewed trained-only result failed; reference assistance improved likeness while compromising framing/background/composition.
- Source preservation before encoding does not mean byte-identical pixels after lossy video compression. Audio priming/timestamps must be aligned before waveform comparisons.
- Short selected intervals do not validate the full reference clip. The UI rejects oversized source/model durations and discloses frame-lattice rounding.

See [current validation scope](VALIDATION.md) and [desktop acceptance](DESKTOP-VALIDATION.md). Rejected outputs are not promoted as successful showcases; original evaluation records remain preserved separately from the public source.
