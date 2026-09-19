# Rebuilding tinyumi assets

Run from the repository root with Python 3.12 and `uv`. The checked-in CAD and
print projects can be used without running the generators. Dependencies below
are not locked; generated files may vary with tool versions.

```sh
uv run --python 3.12 --with cadquery --with trimesh --with matplotlib python pos-tracking/quest_mount/handumi_v1/build.py
uv run --python 3.12 --with cadquery --with trimesh --with matplotlib python hardware/rail_stops/build.py
uv run --python 3.12 --with cadquery --with trimesh --with matplotlib python hardware/realsense_d405/build.py
uv run --python 3.12 --with trimesh --with numpy --with manifold3d python bambu/full_rebuild/build.py
uv run --python 3.12 --with trimesh --with numpy --with manifold3d python bambu/full_rebuild/build.py --d405
```

The support generator uses the checked-in `output/models/` assembly illustration
for conservative clearance checks. Its simplified rails, camera and tip hardware
are documented in the adjacent source manifest; it is not supplier assembly CAD.
The full-project generator uses the checked-in rail-stop 3MF for printer settings.
Open the resulting projects in Bambu Studio, inspect supports and slice before
printing. Regeneration produces unsliced projects.

Generators assert mesh/CAD properties and write local manifests or validation
reports. These checks establish geometry, not physical fit, print strength,
tracking accuracy or real screw engagement. Source licenses and provenance are
in each relevant `source/` or `hardware/reference/` folder.

Legacy upstream part names and illustration paths remain stable to preserve
CAD references. Newly packaged full projects use the `tinyumi_full_rebuild` name.
