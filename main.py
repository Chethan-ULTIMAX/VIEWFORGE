
"""VIEWFORGE local web application and API."""

from __future__ import annotations

import traceback
import tempfile
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from reconstruction import extract_silhouette, reconstruct_visual_hull


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = Path(tempfile.gettempdir()) / "viewforge_outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

MAX_UPLOAD_BYTES = 12 * 1024 * 1024
VIEW_NAMES = ("front", "back", "left", "right", "top", "bottom")

app = FastAPI(
    title="VIEWFORGE",
    description=(
        "AI-free 2D orthographic silhouette "
        "to 3D visual-hull reconstruction."
    ),
    version="0.1.0",
)


@app.get("/", include_in_schema=False)
async def homepage() -> FileResponse:
    return FileResponse(BASE_DIR / "index.html", media_type="text/html")


@app.get("/app.js", include_in_schema=False)
async def frontend_script() -> FileResponse:
    return FileResponse(BASE_DIR / "app.js", media_type="text/javascript")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "project": "VIEWFORGE"}


def _extract_all(images: dict[str, bytes]) -> dict:
    """Decode images and extract all six silhouettes."""
    return {
        view_name: extract_silhouette(image_bytes, view_name)
        for view_name, image_bytes in images.items()
    }


def _write_exports(mesh, run_id: str) -> dict[str, str]:
    """Export the reconstructed mesh in three interchange formats."""
    urls: dict[str, str] = {}

    for extension in ("glb", "obj", "stl"):
        filename = f"viewforge_{run_id}.{extension}"
        destination = OUTPUT_DIR / filename

        exported = mesh.export(file_type=extension)

        if isinstance(exported, str):
            destination.write_text(exported, encoding="utf-8")
        elif isinstance(exported, bytes):
            destination.write_bytes(exported)
        else:
            raise RuntimeError(
                f"The {extension.upper()} exporter returned an "
                "unsupported result."
            )

        urls[extension] = f"/downloads/{filename}"

    return urls


@app.post("/api/reconstruct")
async def reconstruct(
    front: Annotated[
        UploadFile, File(description="Front orthographic silhouette")
    ],
    back: Annotated[
        UploadFile, File(description="Back orthographic silhouette")
    ],
    left: Annotated[
        UploadFile, File(description="Left orthographic silhouette")
    ],
    right: Annotated[
        UploadFile, File(description="Right orthographic silhouette")
    ],
    top: Annotated[
        UploadFile, File(description="Top orthographic silhouette")
    ],
    bottom: Annotated[
        UploadFile, File(description="Bottom orthographic silhouette")
    ],
    resolution: Annotated[int, Form()] = 96,
) -> dict:
    """Reconstruct a visual hull from six uploaded silhouettes."""

    if not 48 <= resolution <= 128:
        raise HTTPException(
            status_code=400,
            detail="Resolution must be between 48 and 128.",
        )

    uploads = {
        "front": front,
        "back": back,
        "left": left,
        "right": right,
        "top": top,
        "bottom": bottom,
    }

    image_bytes: dict[str, bytes] = {}

    try:
        # Read and validate all six uploaded images.
        for view_name in VIEW_NAMES:
            upload = uploads[view_name]

            content = await upload.read(MAX_UPLOAD_BYTES + 1)

            if not content:
                raise HTTPException(
                    status_code=400,
                    detail=f"The {view_name} image is empty.",
                )

            if len(content) > MAX_UPLOAD_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail=(
                        f"The {view_name} image is larger than 12 MB. "
                        "Please use a smaller image."
                    ),
                )

            image_bytes[view_name] = content

        # Extract silhouettes.
        silhouettes = await run_in_threadpool(
            _extract_all,
            image_bytes,
        )

        # Reconstruct the 3D visual hull.
        mesh, statistics = await run_in_threadpool(
            reconstruct_visual_hull,
            silhouettes,
            resolution,
        )

        if mesh is None or mesh.is_empty or len(mesh.faces) == 0:
            raise ValueError(
                "Reconstruction produced an empty mesh. "
                "Check the six silhouettes."
            )

        # Export reconstructed model.
        run_id = uuid.uuid4().hex[:12]

        downloads = await run_in_threadpool(
            _write_exports,
            mesh,
            run_id,
        )

        return {
            "ok": True,
            "message": "The visual hull was reconstructed successfully.",
            "statistics": statistics,
            "downloads": downloads,
        }

    except HTTPException:
        raise

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        print("\n" + "=" * 65)
        print("[VIEWFORGE] RECONSTRUCTION FAILED")
        print("=" * 65)
        print(f"Error: {exc!r}")
        traceback.print_exc()
        print("=" * 65 + "\n")

        raise HTTPException(
            status_code=500,
            detail=(
                "Reconstruction failed. "
                "Check the server terminal for the full traceback."
            ),
        ) from exc

    finally:
        for upload in uploads.values():
            await upload.close()


@app.get("/downloads/{filename}", include_in_schema=False)
async def download_export(filename: str) -> FileResponse:
    """Serve only valid VIEWFORGE-generated model exports."""

    if (
        not filename.startswith("viewforge_")
        or Path(filename).name != filename
    ):
        raise HTTPException(
            status_code=404,
            detail="File not found.",
        )

    extension = Path(filename).suffix.lower()

    if extension not in {".glb", ".obj", ".stl"}:
        raise HTTPException(
            status_code=404,
            detail="File not found.",
        )

    file_path = OUTPUT_DIR / filename

    if not file_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="File not found.",
        )

    media_types = {
        ".glb": "model/gltf-binary",
        ".obj": "text/plain",
        ".stl": "model/stl",
    }

    return FileResponse(
        file_path,
        media_type=media_types[extension],
        filename=filename,
    )
