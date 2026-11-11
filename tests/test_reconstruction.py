import numpy as np

from reconstruction import _voxel_surface_mesh


def test_voxel_surface_mesh_builds_closed_cube():
    """A solid voxel block must produce a valid closed surface mesh."""
    occupancy = np.ones((8, 8, 8), dtype=bool)
    spacing = (0.25, 0.25, 0.25)
    dimensions = (2.0, 2.0, 2.0)

    mesh = _voxel_surface_mesh(occupancy, spacing, dimensions)

    assert not mesh.is_empty
    assert len(mesh.faces) > 0
    assert mesh.is_watertight
    assert np.allclose(mesh.extents, dimensions)
    assert np.isclose(mesh.volume, 8.0)
