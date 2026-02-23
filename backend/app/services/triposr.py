"""TripoSR 3D model generation service.

Wraps the TripoSR TSR model to expose a simple async-friendly interface:
  image (PIL) -> GLB file path
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import rembg
import torch
import trimesh
import xatlas
from PIL import Image

if TYPE_CHECKING:
    from tsr.system import TSR

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Image preprocessing helpers (adapted from TripoSR run.py)
# ---------------------------------------------------------------------------


def _remove_background(
    image: Image.Image,
    session: rembg.sessions.BaseSession,
) -> Image.Image:
    """Remove background unless the image already has transparency."""
    if image.mode == "RGBA" and image.getextrema()[3][0] < 255:
        return image
    return rembg.remove(image, session=session)


def _resize_foreground(image: Image.Image, ratio: float) -> Image.Image:
    """Crop to the foreground bounding box, pad to square, then add margin."""
    arr = np.array(image)
    assert arr.shape[-1] == 4
    alpha = np.where(arr[..., 3] > 0)
    y1, y2, x1, x2 = alpha[0].min(), alpha[0].max(), alpha[1].min(), alpha[1].max()
    fg = arr[y1:y2, x1:x2]

    size = max(fg.shape[0], fg.shape[1])
    ph0, pw0 = (size - fg.shape[0]) // 2, (size - fg.shape[1]) // 2
    ph1, pw1 = size - fg.shape[0] - ph0, size - fg.shape[1] - pw0
    padded = np.pad(fg, ((ph0, ph1), (pw0, pw1), (0, 0)), mode="constant")

    new_size = int(padded.shape[0] / ratio)
    ph0, pw0 = (new_size - size) // 2, (new_size - size) // 2
    ph1, pw1 = new_size - size - ph0, new_size - size - pw0
    padded = np.pad(padded, ((ph0, ph1), (pw0, pw1), (0, 0)), mode="constant")
    return Image.fromarray(padded)


# ---------------------------------------------------------------------------
# Service class
# ---------------------------------------------------------------------------


class TripoSRService:
    """Manages TripoSR model lifecycle and provides generation methods."""

    def __init__(self) -> None:
        self._model: TSR | None = None
        self._rembg_session: rembg.sessions.BaseSession | None = None
        self._device: str = "cpu"

    # -- lifecycle ----------------------------------------------------------

    def load(
        self,
        model_id: str = "stabilityai/TripoSR",
        device: str = "cuda:0",
        chunk_size: int = 8192,
    ) -> None:
        from tsr.system import TSR

        if not torch.cuda.is_available() and device.startswith("cuda"):
            logger.warning("CUDA unavailable, falling back to CPU")
            device = "cpu"

        self._device = device
        logger.info("Loading TripoSR model %s on %s …", model_id, device)
        self._model = TSR.from_pretrained(
            model_id,
            config_name="config.yaml",
            weight_name="model.ckpt",
        )
        self._model.renderer.set_chunk_size(chunk_size)
        self._model.to(device)
        self._rembg_session = rembg.new_session()
        logger.info("TripoSR model ready")

    def is_ready(self) -> bool:
        return self._model is not None

    # -- public API ---------------------------------------------------------

    def generate_glb(
        self,
        image: Image.Image,
        output_path: Path,
        *,
        mc_resolution: int = 256,
        texture_resolution: int = 2048,
        foreground_ratio: float = 0.85,
    ) -> Path:
        """Run the full pipeline: preprocess -> infer -> mesh -> bake -> GLB.

        Returns the path to the exported .glb file.
        """
        assert self._model is not None, "Model not loaded. Call load() first."
        from tsr.bake_texture import bake_texture

        processed = self._preprocess(image, foreground_ratio)

        logger.info("Running TripoSR inference …")
        with torch.no_grad():
            scene_codes = self._model([processed], device=self._device)

        logger.info("Extracting mesh (resolution=%d) …", mc_resolution)
        meshes = self._model.extract_mesh(
            scene_codes,
            has_vertex_color=False,
            resolution=mc_resolution,
        )
        mesh = meshes[0]

        logger.info("Baking texture (resolution=%d) …", texture_resolution)
        bake_out = bake_texture(mesh, self._model, scene_codes[0], texture_resolution)

        glb_path = output_path.with_suffix(".glb")
        xatlas.export(
            str(glb_path),
            mesh.vertices[bake_out["vmapping"]],
            bake_out["indices"],
            bake_out["uvs"],
            mesh.vertex_normals[bake_out["vmapping"]],
        )

        # xatlas.export writes OBJ by default; we rebuild as GLB via trimesh
        # so the frontend can load a single self-contained file.
        texture_img = Image.fromarray(
            (bake_out["colors"] * 255.0).astype(np.uint8)
        ).transpose(Image.FLIP_TOP_BOTTOM)

        rebuilt = _build_glb(
            vertices=mesh.vertices[bake_out["vmapping"]],
            faces=bake_out["indices"],
            uvs=bake_out["uvs"],
            normals=mesh.vertex_normals[bake_out["vmapping"]],
            texture=texture_img,
        )
        glb_path = output_path.with_suffix(".glb")
        rebuilt.export(str(glb_path))
        logger.info("GLB saved to %s", glb_path)
        return glb_path

    # -- internal -----------------------------------------------------------

    def _preprocess(
        self, image: Image.Image, foreground_ratio: float
    ) -> Image.Image:
        assert self._rembg_session is not None
        image = _remove_background(image, self._rembg_session)
        image = _resize_foreground(image, foreground_ratio)
        arr = np.array(image).astype(np.float32) / 255.0
        arr = arr[:, :, :3] * arr[:, :, 3:4] + (1 - arr[:, :, 3:4]) * 0.5
        return Image.fromarray((arr * 255.0).astype(np.uint8))


# ---------------------------------------------------------------------------
# GLB construction helper
# ---------------------------------------------------------------------------


def _build_glb(
    vertices: np.ndarray,
    faces: np.ndarray,
    uvs: np.ndarray,
    normals: np.ndarray,
    texture: Image.Image,
) -> trimesh.Scene:
    """Build a trimesh Scene with a textured mesh suitable for GLB export."""
    import trimesh.visual

    material = trimesh.visual.material.PBRMaterial(
        baseColorTexture=texture,
        metallicFactor=0.0,
        roughnessFactor=1.0,
    )
    visual = trimesh.visual.TextureVisuals(uv=uvs, material=material)
    mesh = trimesh.Trimesh(
        vertices=vertices,
        faces=faces,
        vertex_normals=normals,
        visual=visual,
        process=False,
    )
    scene = trimesh.Scene(geometry={"car": mesh})
    return scene
