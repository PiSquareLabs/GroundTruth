"""Cloudinary upload, delivery URLs and named transformations (every URL built here is logged)."""
from __future__ import annotations

import os
from urllib.parse import urlparse

import cloudinary
import cloudinary.uploader
import cloudinary.utils

from gt import config, db

# Named transformation presets. The raw strings are what gets logged for traceability.
PRESETS = {
    "thumb": "c_fill,g_auto,w_400,h_300/q_auto/f_auto",
    "display": "c_limit,w_1200/q_auto/f_auto",
    "compare": "c_fill,g_auto,w_1000,h_750/q_auto/f_auto",
    "report": "c_fill,g_auto,w_640,h_480/q_auto/f_jpg",
}
FACE_BLUR = "e_blur_faces:800"

_configured = False


def _configure() -> None:
    global _configured
    if _configured or not config.cloudinary_ready():
        return
    os.environ["CLOUDINARY_URL"] = config.CLOUDINARY_URL
    cloudinary.reset_config()
    _configured = True


def cloud_name() -> str | None:
    if config.cloudinary_ready():
        return urlparse(config.CLOUDINARY_URL).hostname
    return db.get_meta("cloud_name")


def transformation_for(preset: str, blur_faces: bool = False) -> str:
    t = PRESETS[preset]
    return f"{FACE_BLUR}/{t}" if blur_faces else t


def url_for(a: dict, preset: str = "display", blur_faces: bool = False, log: bool = True) -> str | None:
    """Delivery URL for an asset row. Falls back to the local seed file if not on Cloudinary."""
    cn = cloud_name()
    if a.get("public_id") and cn:
        t = transformation_for(preset, blur_faces)
        url, _ = cloudinary.utils.cloudinary_url(a["public_id"], raw_transformation=t, cloud_name=cn, secure=True)
        if log:
            db.log_transform(a["id"], preset + ("+face_blur" if blur_faces else ""), t, url)
        return url
    return a.get("local_path") or a.get("url")


def original_url(a: dict) -> str | None:
    return a.get("url") or a.get("local_path")


def upload(file, public_id: str, project_id: str) -> dict:
    """Upload an original to Cloudinary (no incoming transformation, so the original stays intact)."""
    _configure()
    if not _configured:
        raise RuntimeError("Cloudinary is not configured (set CLOUDINARY_URL).")
    return cloudinary.uploader.upload(
        file,
        public_id=public_id,
        folder=f"{config.CLOUDINARY_FOLDER}/{project_id}",
        overwrite=False,
        unique_filename=False,
        resource_type="image",
        context={"project": project_id},
    )
