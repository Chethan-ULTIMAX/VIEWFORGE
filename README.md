
# VIEWFORGE

**Reconstruct 3D models from 2D views.**

VIEWFORGE is an open-source project that transforms six orthographic images of an object into a 3D model using computer vision and mathematical geometry — without generative AI.

## How It Works

1. Upload six views: Front, Back, Left, Right, Top and Bottom.
2. Extract object silhouettes from the images.
3. Align the views in a shared 3D coordinate system.
4. Reconstruct the object's volume using Visual Hull and voxel carving.
5. Generate a 3D mesh using Marching Cubes.

## Planned Features

- Six-view image upload and alignment.
- Automatic silhouette extraction.
- Voxel-based 3D reconstruction.
- Interactive 3D model visualization.
- Cross-section and measurement tools.
- Export models in GLB, OBJ and STL formats.

## Tech Stack

| Component | Technology |
|---|---|
| Backend | Python, FastAPI |
| Computer Vision | OpenCV |
| Computation | NumPy |
| Reconstruction | scikit-image |
| 3D Mesh | Trimesh |
| Visualization | Three.js |

## Project Goal

Build a completely AI-free, mathematical 2D-to-3D reconstruction system that makes 3D model generation accessible through simple images.

## Status

**Under Development** 🚧

---

*VIEWFORGE — From six perspectives to one 3D reality.*
