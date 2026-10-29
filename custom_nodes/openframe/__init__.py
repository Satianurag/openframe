"""Original OpenFrame utility nodes. Model inference stays in native ComfyUI nodes."""
__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]


def __getattr__(name):
    # The hosted-provider adapter imports media helpers without installing
    # ComfyUI/Torch locally. ComfyUI requests these mappings when loading nodes.
    if name in __all__:
        from .nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS
        globals().update(NODE_CLASS_MAPPINGS=NODE_CLASS_MAPPINGS,
                         NODE_DISPLAY_NAME_MAPPINGS=NODE_DISPLAY_NAME_MAPPINGS)
        return globals()[name]
    raise AttributeError(name)
