# Complete tinyumi rebuild

Open `tinyumi_full_rebuild_A1_PETG.3mf` in Bambu Studio. Two plates for one gripper;
Quest controller support excluded; print one separately if needed.

Plate 1: one combined Quest/rail-stop base, two jaw adapters with integral racks,
two L-brackets, two curved finger holders, one camera mount, four pinion fit
variants (install only one), and four rail stops (two A/two B).
Plate 2: one left and one right rigid fingertip prototype.

A1, 0.4 mm nozzle, Generic PETG, 0.2 mm layers, four walls, five top and bottom
layers, 30% gyroid infill, normal snug supports, three interface layers.
All objects start on Z=0 and have separated footprints. See manifest.json.
These are starting print settings, not mechanically validated settings.

## Inserts and assembly

Existing part holes have been retained; no supplier-specific resizing applied.
Check actual insert outside diameter AND length before printing the body.
The original build calls for M3-thread, nominal 4 mm OD, 5 mm-long inserts.
The 4.4 mm OD OnlyScrews option is not confirmed compatible with these holes.
Do not compensate every hole globally: that also changes bearing and screw fits.

Install inserts while each part is separate. Let them cool before fitting screws.
Check screw engagement and available hole depth before tightening; bottoming a
long screw can damage the insert pocket without clamping the joint.
Base rail-stop screws are M3x8 countersunk; the Quest support uses M3x10
countersunk. See [the fastener table](../../docs/fasteners.md) for other CAD starting sizes
and the unverified M4 × 12 fingertip trial suggestion.
Trial-fit the pinion variants and keep the smoothest one. Confirm free jaw
travel and stop contact before installing the controller.

## Prototype fingertip provenance and limits

The tips derive from the local I2RT Linear 4310 reference STLs, scaled from metres
to millimetres. A solid plane cut at original Z=-145.61 mm removes the merged
stock rack above the tip mounting face. Original tip geometry, including mounting
pockets, is retained. Unlike the earlier illustration cuts, these use manifold
solid trimming and export watertight positive-volume meshes.

This validates mesh closure only. Mounting fit, material grip, strength, insert
fit, and equivalence to purchased tips have not been physically validated.
The rigid PETG prototypes do not establish the compliance/friction of stock tips.
Check these on the bracket before treating them as finished replacements.
Source and MIT license: ../../hardware/reference/i2rt_linear_4310/source.json
and ../../hardware/reference/i2rt_linear_4310/LICENSE.

Regenerate the unsliced project with:
`uv run --with trimesh --with numpy --with manifold3d python bambu/full_rebuild/build.py`
Save from Bambu Studio after slicing to retain its native project metadata.

## D405 camera version

`tinyumi_full_rebuild_D405_A1_PETG.3mf` substitutes the one-piece RealSense D405
bracket for the fisheye camera mount. Other quantities are identical.
See ../../hardware/realsense_d405/README.md for camera screw limits and fitting.
Regenerate with `build.py --d405` using the same uv packages above.
