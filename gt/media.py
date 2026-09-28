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
    "compare": "c_fill,g_auto,w_1000,h_750/q_auto/f_jpg",  # slider fetches server-side
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


def _text_param(text: str) -> str:
    """Cloudinary l_text escaping: URL-encode, then double-escape commas and slashes."""
    from urllib.parse import quote

    return quote(text, safe="").replace("%2C", "%252C").replace("%2F", "%252F")


def campaign_card(before: dict, after: dict, headline: str, footer: str, blur_faces: bool = False) -> tuple[str, str] | None:
    """Shareable 1200x630 card: before | after side by side with text overlays. Returns (url, transformation)."""
    cn = cloud_name()
    if not (cn and before.get("public_id") and after.get("public_id")):
        return None
    blur = f"{FACE_BLUR}/" if blur_faces else ""
    layer_id = after["public_id"].replace("/", ":")
    t = (
        f"{blur}c_fill,g_auto,w_600,h_630/c_pad,w_1200,h_630,g_west,b_black/"
        f"l_{layer_id}/{'e_blur_faces:800/' if blur_faces else ''}c_fill,g_auto,w_600,h_630/fl_layer_apply,g_east/"
        f"l_text:Arial_44_bold:{_text_param(headline)},co_white,b_rgb:2E7D32/fl_layer_apply,g_north,y_24/"
        f"l_text:Arial_24:{_text_param(footer)},co_white,b_rgb:00000099/fl_layer_apply,g_south,y_20/"
        f"l_text:Arial_26_bold:BEFORE,co_white,b_rgb:00000099/fl_layer_apply,g_south_west,x_20,y_70/"
        f"l_text:Arial_26_bold:AFTER,co_white,b_rgb:00000099/fl_layer_apply,g_south_east,x_20,y_70/"
        f"q_auto/f_jpg"
    )
    url, _ = cloudinary.utils.cloudinary_url(before["public_id"], raw_transformation=t, cloud_name=cn, secure=True)
    db.log_transform(before["id"], "campaign_card", t, url)
    db.log_transform(after["id"], "campaign_card (layer)", t, url)
    return url, t
