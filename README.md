# VIEWFORGE

**Six orthographic views in. One approximate 3D model out.**

VIEWFORGE is an AI-free 2D-to-3D reconstruction experiment. It uses OpenCV to extract silhouettes, mathematical visual-hull carving to estimate the object's volume, and Marching Cubes to create a mesh.

## What it does

1. Accepts front, back, left, right, top and bottom images.
2. Extracts a foreground silhouette from each image.
3. Estimates the object's relative width, depth and height from the six silhouettes.
4. Intersects the six silhouette volumes on a voxel grid.
5. Generates a mesh and displays it in an interactive Three.js viewer.
6. Exports the result as GLB, OBJ or STL.

## Run locally

Python 3.10 or newer is recommended.

```bash
python -m venv .venv
```

**Windows PowerShell:**

```powershell
.venv\Scripts\Activate.ps1
```

**Windows Command Prompt:**

```cmd
.venv\Scripts\activate
```

Install dependencies and start the server:

```bash
python -m pip install -r requirements.txt
python -m uvicorn main:app --reload
```

Open **http://127.0.0.1:8000** in your browser. The interactive viewer loads Three.js from jsDelivr, so an internet connection is required for the 3D viewer library.

## Input image guidelines

For the best first results:

- Use six **orthographic** views of the same object, not perspective photographs.
- Keep the object centred and show its complete outline in every view.
- Use a plain, contrasting background or a transparent PNG.
- Use a solid silhouette where possible; avoid shadows, labels, borders and other objects.
- Keep the view directions consistent: front/back, left/right, top/bottom.

Use **Load demo object** in the interface to test the complete pipeline with six generated ellipse silhouettes before preparing your own images.

## Important limitation

VIEWFORGE currently creates a **visual hull**. A visual hull is the outer volume consistent with the supplied silhouettes. It cannot recover hidden concavities, internal geometry, fine surface details, materials or textures that are not visible in the six outlines. Results are approximate and depend on clean, correctly oriented orthographic silhouettes. It is not a general-purpose converter for arbitrary six photographs or engineering drawings.

## Technology

- Python, FastAPI and Uvicorn
- OpenCV and NumPy
- scikit-image (Marching Cubes)
- Trimesh
- Three.js

## Project status

**Early prototype — under development.**

---

*VIEWFORGE — From six perspectives to one 3D reality.*
