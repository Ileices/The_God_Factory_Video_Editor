"""Runtime capability scanner for optional media and system libraries."""

from __future__ import annotations

from importlib import import_module
from importlib.metadata import PackageNotFoundError, version


_LIBRARY_PACKAGES = [
    "PySide6",
    "opencv-python",
    "Pillow",
    "psutil",
    "scenedetect",
    "numpy",
]


def _pkg_version(package_name: str) -> str:
    try:
        return version(package_name)
    except PackageNotFoundError:
        return "not-installed"
    except Exception:
        return "unknown"


def runtime_library_capabilities() -> dict:
    caps: dict = {
        "packages": {pkg: _pkg_version(pkg) for pkg in _LIBRARY_PACKAGES},
        "features": {},
    }

    # OpenCV CUDA capability check when available.
    try:
        cv2 = import_module("cv2")
        has_cuda = bool(getattr(cv2, "cuda", None))
        caps["features"]["opencv_cuda"] = bool(has_cuda)
    except Exception:
        caps["features"]["opencv_cuda"] = False

    # Pillow text rendering capability (useful for captions).
    try:
        pil_imagefont = import_module("PIL.ImageFont")
        caps["features"]["pillow_truetype"] = hasattr(pil_imagefont, "truetype")
    except Exception:
        caps["features"]["pillow_truetype"] = False

    return caps


def runtime_library_summary_text() -> str:
    caps = runtime_library_capabilities()
    lines = ["Runtime Library Capability Scan", "", "Packages:"]
    for pkg, ver in caps["packages"].items():
        lines.append(f"- {pkg}: {ver}")

    lines.append("")
    lines.append("Feature Flags:")
    for feat, val in caps["features"].items():
        lines.append(f"- {feat}: {val}")

    return "\n".join(lines)
