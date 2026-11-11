"""Silhouette extraction and six-view visual-hull reconstruction.

Coordinate convention used by VIEWFORGE:
- X runs left-to-right in the FRONT view.
- Y runs left-to-right in the LEFT view.
- Z is vertical.
- Opposite views are mirrored as described in _carve_visual_hull().

The algorithm reconstructs the intersection of six silhouette-extruded volumes.
It produces a visual hull, not hidden concavities, internal structure or texture.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
import trimesh



@dataclass
class Silhouette:
    """A binary silhouette and its tight image-space bounding rectangle."""

    mask: np.ndarray
    bbox: tuple[int, int, int, int]  # x, y, width, height
    image_width: int
    image_height: int
    foreground_pixels: int


def extract_silhouette(image_bytes: bytes, view_name: str) -> Silhouette:
    """Decode an image and separate its foreground silhouette from its background.

    Best results come from a solid, dark object on a plain light background,
    a solid light object on a plain dark background, or a transparent PNG.
    """
    encoded = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(encoded, cv2.IMREAD_UNCHANGED)
    if image is None:
        raise ValueError(f"Could not read the {view_name} image. Use PNG, JPG or WEBP.")

    height, width = image.shape[:2]
    if width < 32 or height < 32:
        raise ValueError(f"The {view_name} image is too small. Use an image at least 32 × 32 pixels.")
    if width * height > 20_000_000:
        raise ValueError(f"The {view_name} image is too large. Resize it to 20 megapixels or less.")

    # Downscale oversized images to keep local processing responsive.
    longest_side = max(width, height)
    if longest_side > 1800:
        scale = 1800.0 / longest_side
        new_size = (max(32, round(width * scale)), max(32, round(height * scale)))
        image = cv2.resize(image, new_size, interpolation=cv2.INTER_AREA)
        height, width = image.shape[:2]

    if image.ndim == 2:
        gray = image
        alpha = None
    elif image.shape[2] == 4:
        gray = cv2.cvtColor(image[:, :, :3], cv2.COLOR_BGR2GRAY)
        alpha = image[:, :, 3]
    else:
        gray = cv2.cvtColor(image[:, :, :3], cv2.COLOR_BGR2GRAY)
        alpha = None

    # A transparent border is the strongest indicator of a transparent PNG.
    if alpha is not None:
        border = max(2, min(height, width) // 40)
        alpha_border = np.concatenate(
            (
                alpha[:border, :].ravel(),
                alpha[-border:, :].ravel(),
                alpha[:, :border].ravel(),
                alpha[:, -border:].ravel(),
            )
        )
        if float(np.median(alpha_border)) < 245:
            foreground = (alpha > 12).astype(np.uint8) * 255
        else:
            foreground = _threshold_against_border(gray)
    else:
        foreground = _threshold_against_border(gray)

    # Close tiny breaks in outlines, then remove isolated speckles.
    close_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    open_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    foreground = cv2.morphologyEx(foreground, cv2.MORPH_CLOSE, close_kernel)
    foreground = cv2.morphologyEx(foreground, cv2.MORPH_OPEN, open_kernel)

    count, labels, component_stats, _ = cv2.connectedComponentsWithStats(
        foreground, connectivity=8
    )
    if count <= 1:
        raise ValueError(
            f"No object silhouette was detected in the {view_name} image. "
            "Use a clearer foreground/background contrast."
        )

    largest_area = int(component_stats[1:, cv2.CC_STAT_AREA].max())
    minimum_component_area = max(12, int(largest_area * 0.008))
    cleaned = np.zeros_like(foreground)
    for component_id in range(1, count):
        area = int(component_stats[component_id, cv2.CC_STAT_AREA])
        if area >= minimum_component_area:
            cleaned[labels == component_id] = 255

    # Fill closed outline drawings into solid silhouettes. Visual-hull carving
    # needs the projected object area, not just the outline stroke.
    contours, _ = cv2.findContours(
        cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    filled = np.zeros_like(cleaned)
    if contours:
        cv2.drawContours(filled, contours, -1, 255, thickness=cv2.FILLED)

    points = cv2.findNonZero(filled)
    if points is None:
        raise ValueError(f"No usable silhouette remains in the {view_name} image.")

    x, y, box_width, box_height = cv2.boundingRect(points)
    if box_width < 8 or box_height < 8:
        raise ValueError(f"The detected {view_name} silhouette is too narrow or too small.")

    mask = filled > 0
    return Silhouette(
        mask=mask,
        bbox=(int(x), int(y), int(box_width), int(box_height)),
        image_width=int(width),
        image_height=int(height),
        foreground_pixels=int(np.count_nonzero(mask)),
    )


def _threshold_against_border(gray: np.ndarray) -> np.ndarray:
    """Segment pixels that differ from the median colour of the image border."""
    height, width = gray.shape
    border_size = max(2, min(height, width) // 40)
    border_pixels = np.concatenate(
        (
            gray[:border_size, :].ravel(),
            gray[-border_size:, :].ravel(),
            gray[:, :border_size].ravel(),
            gray[:, -border_size:].ravel(),
        )
    )
    background_level = float(np.median(border_pixels))
    difference = cv2.convertScaleAbs(gray.astype(np.float32) - background_level)
    otsu_threshold, _ = cv2.threshold(
        difference, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU
    )
    threshold = max(18, int(otsu_threshold))
    return (difference > threshold).astype(np.uint8) * 255


def _estimate_dimensions(silhouettes: dict[str, Silhouette]) -> tuple[float, float, float]:
    """Estimate relative X/Y/Z extents from the six silhouette bounding boxes."""
    ratios: dict[str, float] = {}
    for name, silhouette in silhouettes.items():
        _, _, box_width, box_height = silhouette.bbox
        ratios[name] = box_width / max(1.0, float(box_height))

    # Solve the overdetermined log-ratio system:
    # front/back = X/Z, left/right = Y/Z, top/bottom = X/Y.
    matrix = np.array(
        [
            [1.0, 0.0, -1.0],
            [1.0, 0.0, -1.0],
            [0.0, 1.0, -1.0],
            [0.0, 1.0, -1.0],
            [1.0, -1.0, 0.0],
            [1.0, -1.0, 0.0],
            [1.0, 1.0, 1.0],  # fixes the arbitrary global scale
        ],
        dtype=np.float64,
    )
    values = np.array(
        [
            np.log(ratios["front"]),
            np.log(ratios["back"]),
            np.log(ratios["left"]),
            np.log(ratios["right"]),
            np.log(ratios["top"]),
            np.log(ratios["bottom"]),
            0.0,
        ],
        dtype=np.float64,
    )
    log_dimensions, *_ = np.linalg.lstsq(matrix, values, rcond=None)
    dimensions = np.exp(log_dimensions)
    dimensions /= float(np.max(dimensions))

    x_size, y_size, z_size = (float(value) for value in dimensions)
    if min(x_size, y_size, z_size) < 0.08:
        raise ValueError(
            "The six view proportions are extremely inconsistent. Check that each image "
            "shows the same object in a true orthographic view."
        )
    return x_size, y_size, z_size


def _sample_mask(
    silhouette: Silhouette,
    horizontal_fraction: np.ndarray,
    vertical_fraction: np.ndarray,
) -> np.ndarray:
    """Sample a silhouette at broadcastable normalized projection coordinates."""
    x0, y0, box_width, box_height = silhouette.bbox
    px = np.rint(x0 + np.clip(horizontal_fraction, 0.0, 1.0) * (box_width - 1))
    py = np.rint(y0 + np.clip(vertical_fraction, 0.0, 1.0) * (box_height - 1))
    px = np.clip(px.astype(np.int32), 0, silhouette.image_width - 1)
    py = np.clip(py.astype(np.int32), 0, silhouette.image_height - 1)
    return silhouette.mask[py, px]


def _carve_visual_hull(
    silhouettes: dict[str, Silhouette],
    resolution: int,
    dimensions: tuple[float, float, float],
) -> tuple[np.ndarray, tuple[float, float, float]]:
    """Intersect the six projected silhouette volumes on a 3D voxel grid."""
    x_size, y_size, z_size = dimensions
    longest = max(dimensions)

    nx = max(24, round(resolution * x_size / longest))
    ny = max(24, round(resolution * y_size / longest))
    nz = max(24, round(resolution * z_size / longest))
    dx, dy, dz = x_size / nx, y_size / ny, z_size / nz

    # Voxel-centre coordinates, normalized to [0, 1] along each axis.
    x_fraction = ((np.arange(nx, dtype=np.float32) + 0.5) / nx)[None, None, :]
    y_fraction = ((np.arange(ny, dtype=np.float32) + 0.5) / ny)[None, :, None]
    z_fraction_from_top = (
        (1.0 - (np.arange(nz, dtype=np.float32) + 0.5) / nz)[:, None, None]
    )

    occupied = np.ones((nz, ny, nx), dtype=bool)

    # Opposite views reverse the horizontal screen direction. Top is viewed
    # from +Z; bottom is viewed from -Z, so its horizontal direction is reversed.
    occupied &= _sample_mask(silhouettes["front"], x_fraction, z_fraction_from_top)
    occupied &= _sample_mask(silhouettes["back"], 1.0 - x_fraction, z_fraction_from_top)
    occupied &= _sample_mask(silhouettes["left"], y_fraction, z_fraction_from_top)
    occupied &= _sample_mask(silhouettes["right"], 1.0 - y_fraction, z_fraction_from_top)
    occupied &= _sample_mask(silhouettes["top"], x_fraction, 1.0 - y_fraction)
    occupied &= _sample_mask(silhouettes["bottom"], 1.0 - x_fraction, y_fraction)

    return occupied, (dx, dy, dz)


def _voxel_surface_mesh(
    occupancy: np.ndarray,
    spacing: tuple[float, float, float],
    dimensions: tuple[float, float, float],
) -> trimesh.Trimesh:
    """Create a surface mesh from exposed voxel faces without scikit-image."""

    dx, dy, dz = spacing
    x_size, y_size, z_size = dimensions

    vertices_parts = []
    faces_parts = []
    vertex_offset = 0

    # Occupancy array axes are Z, Y, X.
    for array_axis in range(3):
        xyz_axis = 2 - array_axis
        other_axes = [axis for axis in range(3) if axis != xyz_axis]

        for direction in (-1, 1):
            neighbor = np.zeros_like(occupancy)

            destination = [slice(None)] * 3
            source = [slice(None)] * 3

            if direction == -1:
                destination[array_axis] = slice(1, None)
                source[array_axis] = slice(None, -1)
            else:
                destination[array_axis] = slice(None, -1)
                source[array_axis] = slice(1, None)

            neighbor[tuple(destination)] = occupancy[tuple(source)]
            exposed = occupancy & ~neighbor

            indices = np.argwhere(exposed)
            if len(indices) == 0:
                continue

            # Convert Z,Y,X voxel indices into X,Y,Z coordinates.
            xyz_indices = indices[:, [2, 1, 0]].astype(np.float64)

            voxel_spacing = np.array([dx, dy, dz])
            object_dimensions = np.array([x_size, y_size, z_size])

            lower = (
                xyz_indices * voxel_spacing
                - object_dimensions / 2.0
            )

            # Move the face to the correct side of its voxel.
            if direction > 0:
                lower[:, xyz_axis] += voxel_spacing[xyz_axis]

            first = np.zeros(3)
            second = np.zeros(3)

            first[other_axes[0]] = voxel_spacing[other_axes[0]]
            second[other_axes[1]] = voxel_spacing[other_axes[1]]

            q0 = lower
            q1 = lower + first
            q2 = lower + first + second
            q3 = lower + second

            quads = np.stack((q0, q1, q2, q3), axis=1)
            vertices = quads.reshape(-1, 3)

            face_count = len(indices)
            base = (
                np.arange(face_count, dtype=np.int64)[:, None] * 4
                + vertex_offset
            )

            faces = np.concatenate(
                (
                    base[:, [0, 1, 2]],
                    base[:, [0, 2, 3]],
                ),
                axis=0,
            )

            vertices_parts.append(vertices)
            faces_parts.append(faces)
            vertex_offset += len(vertices)

    if not vertices_parts:
        raise ValueError("No exposed voxel surfaces were found.")

    mesh = trimesh.Trimesh(
        vertices=np.vstack(vertices_parts),
        faces=np.vstack(faces_parts),
        process=True,
    )

    mesh.fix_normals()
    return mesh


def reconstruct_visual_hull(
    silhouettes: dict[str, Silhouette], resolution: int = 96
) -> tuple[trimesh.Trimesh, dict]:
    """Build a watertight mesh from six orthographic binary silhouettes."""
    required = {"front", "back", "left", "right", "top", "bottom"}
    missing = required.difference(silhouettes)
    if missing:
        raise ValueError(f"Missing view(s): {', '.join(sorted(missing))}.")

    dimensions = _estimate_dimensions(silhouettes)
    occupancy, spacing = _carve_visual_hull(silhouettes, resolution, dimensions)
    occupied_voxels = int(np.count_nonzero(occupancy))
    if occupied_voxels < 24:
        raise ValueError(
            "The six silhouettes do not overlap to form a usable 3D volume. "
            "Check view orientation, alignment and image backgrounds."
        )


    mesh = _voxel_surface_mesh(
        occupancy,
        spacing,
        dimensions,
    )

    if mesh.is_empty or len(mesh.faces) == 0:
        raise ValueError(
            "The reconstructed mesh is empty. Check the six input silhouettes."
        )

    mesh.remove_unreferenced_vertices()
    mesh.fix_normals()

    extents = [round(float(value), 4) for value in mesh.extents]
    statistics = {
        "vertices": int(len(mesh.vertices)),
        "faces": int(len(mesh.faces)),
        "occupied_voxels": occupied_voxels,
        "grid": [int(occupancy.shape[2]), int(occupancy.shape[1]), int(occupancy.shape[0])],
        "dimensions": extents,
        "watertight": bool(mesh.is_watertight),
        "volume": round(float(mesh.volume), 5) if mesh.is_watertight else None,
    }
    return mesh, statistics
