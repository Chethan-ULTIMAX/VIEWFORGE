# VIEWFORGE

**Six orthographic silhouettes in. One approximate 3D model out.**

VIEWFORGE is a local, AI-free 2D-to-3D reconstruction prototype. It estimates an object's outer shape from six orthographic silhouette images—front, back, left, right, top and bottom—using computer vision and voxel-based visual-hull reconstruction.

> **What it can do:** reconstruct an approximate outer volume from six aligned silhouettes.
>
> **What it cannot do:** recover hidden concavities, internal geometry, materials or surface textures that are not present in the silhouettes.

## Highlights

- Six-view image upload with previews and drag-and-drop support.
- Foreground silhouette extraction with OpenCV.
- Six-direction visual-hull carving on a 3D voxel grid.
- Surface mesh generation directly from exposed voxel faces (no scikit-image dependency).
- Interactive 3D inspection with Three.js and orbit controls.
- GLB, OBJ and STL exports.
- Local Python/FastAPI processing—no generative AI or paid reconstruction API.
- Built-in ellipsoid demo so the pipeline can be tried without preparing input images.

## How reconstruction works

1. **Upload:** provide front, back, left, right, top and bottom images of the same object.
2. **Segment:** VIEWFORGE extracts a binary foreground silhouette from each image.
3. **Estimate scale:** the six silhouette bounding boxes provide relative X, Y and Z dimensions.
4. **Carve:** a 3D voxel grid is tested against all six projected silhouettes. Voxels outside any silhouette are discarded.
5. **Mesh:** exposed voxel faces are assembled into a triangle mesh.
6. **Inspect and export:** view the result in the browser and download it as GLB, OBJ or STL.

This is a *visual hull* method. Its result is the intersection of six silhouette-extruded volumes, so it is an approximation rather than an exact scan.

## Tech stack

| Area | Technology |
|---|---|
| API and local server | Python, FastAPI, Uvicorn |
| Image processing | OpenCV |
| Numerical operations | NumPy |
| Mesh construction and export | Trimesh |
| 3D viewer | Three.js |
| Interface | HTML, CSS, JavaScript |

## Requirements

- Windows, macOS or Linux
- Python 3.10+
- A modern browser with WebGL support
- Internet access when loading the Three.js module and Google Fonts from their CDNs

## Quick start

Clone the repository:

```bash
git clone https://github.com/Chethan-ULTIMAX/VIEWFORGE.git
cd VIEWFORGE
```

Create a virtual environment and install the dependencies.

**Windows PowerShell**

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

**macOS / Linux**

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Start the server.

**Windows PowerShell**

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --reload
```

**macOS / Linux**

```bash
.venv/bin/python -m uvicorn main:app --reload
```

Open **http://127.0.0.1:8000** in your browser.

Interactive API documentation is available at **http://127.0.0.1:8000/docs**, and the health endpoint is **http://127.0.0.1:8000/health**.

## Using the app

1. Open the application in your browser.
2. Choose **Load demo object** to try the built-in ellipsoid, or upload all six views.
3. Select a voxel resolution. Higher values require more processing time and memory.
4. Select **Reconstruct 3D model**.
5. Orbit and zoom around the result in the 3D viewer.
6. Export the model as GLB, OBJ or STL.

The API accepts PNG, JPEG and WEBP uploads. Each image is limited to 12 MB; images above 20 megapixels are rejected, and larger image dimensions are downscaled before processing.

## Preparing input images

For the most useful results:

- Use all six views of the same object.
- Use orthographic views, or images with as little perspective distortion as possible.
- Keep the object fully visible and centred in every image.
- Use a plain, contrasting background.
- Keep the object's orientation consistent between views.
- Avoid cast shadows, reflections, clutter and disconnected foreground objects.
- Ensure opposite views use consistent framing and scale.

Silhouette extraction is automatic and works best when the object is clearly separated from the image border/background. Inspect the previews before starting reconstruction.

## Project layout

```text
VIEWFORGE/
├── main.py             # FastAPI app, upload validation and model downloads
├── reconstruction.py   # Segmentation, voxel carving and surface mesh
├── index.html          # Application interface and styling
├── app.js              # Upload flow, API calls and Three.js viewer
├── requirements.txt    # Python dependencies
├── .gitignore
└── README.md
```

## Current limitations

- **Silhouette ambiguity:** different 3D objects can share the same six silhouettes.
- **Concavities:** recesses and hidden concave regions cannot be inferred reliably from silhouettes alone.
- **No appearance reconstruction:** the pipeline produces geometry, not recovered materials or textures.
- **Alignment matters:** inconsistent scale, orientation or centring between views can distort or eliminate the reconstructed volume.
- **Resolution trade-off:** higher voxel resolution increases memory use and processing time.
- **Prototype status:** this is an experimental reconstruction pipeline; results should be inspected before use in production workflows.

## Development status

VIEWFORGE is under active development. Current work is focused on correctness of the six-view geometry, reliable mesh generation, clearer validation and a better reconstruction workflow.

## License

No license has been declared yet. Until a license is added to this repository, do not assume that the code is available for unrestricted reuse.

---

**VIEWFORGE** · Computer vision × computational geometry × 3D reconstruction


## Tests

Run the automated regression tests from the project root with:

```bash
python -m pip install pytest
python -m pytest -q
```

GitHub Actions runs this test suite on pushes to `main` and pull requests targeting `main`.
