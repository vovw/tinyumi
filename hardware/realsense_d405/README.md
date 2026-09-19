# RealSense D405 replacement mount

A one-piece PETG bracket replacing the original fisheye mount on one tinyumi.
It fits the existing camera insert pair on the underside of plate_v6, including
the combined Quest + rail-stop plate. No new holes in the gripper base are required.

- `d405_mount_print.stl`: oriented printable part; supports required.
- `d405_mount_assembly.step` / `.stl`: part in the base's assembly coordinates.
- `d405_rear_fit_gauge.stl`: small 5 mm-thick test piece for the D405 rear screw pair.
- `d405_on_base.glb` / `d405_mount_preview.png`: schematic camera envelope on the base.
- `D405_ENVELOPE_NOT_FOR_PRINT.step`: nominal body envelope, not supplier CAD.
- Updated full print project: `../../bambu/full_rebuild/tinyumi_full_rebuild_D405_A1_PETG.3mf`.

## Screws and installation

1. Check the rear-hole gauge against the camera before printing the long bracket.
2. Attach the camera to the bracket with **two M3x8 socket-head screws** through
   the 5 mm pad: nominal penetration is 3 mm. The camera's maximum M3 insertion
   is **4 mm**. Measure the printed pad and actual screw protrusion; do not force
   a screw that bottoms out. No heat-set inserts are needed at this joint.
3. Attach the foot under the base's camera-side end with **two M3x8, 90-degree
   countersunk screws**, entering the existing base inserts. The foot is 5 mm
   thick at the screw axis, giving about 3 mm engagement. Base inserts retain
   their existing specification; supplier-specific hole resizing is not applied.
4. Both lenses face the tips. The stereo baseline runs along jaw travel.
   Rear access and both cable sides are open; check the actual Micro-B plug and
   cable bend before tightening. Tie the cable to the arm with slack at the plug.
5. Sweep the jaws and try the hand straps before use. Check camera view across
   the complete aperture range.

## Geometry and print setup

The base pair is at X=±20.285398 mm, Y=29 mm in the existing plate frame.
The camera rear pair is horizontal, 20 mm apart, on a 42x16x5 mm back pad.
Most of the camera back and all side faces remain exposed.

Camera rear centre: (0,100,0) mm; view direction (0,-0.707107,0.707107).
The 45-degree angle aims toward the nominal fingertip region near (0,0,100).
This is a chosen design pose, not a preserved fisheye extrinsic or measured
optical centre. The 42x42x23 mm body envelope does not include the side protrusion
or a cable plug. Neither side is enclosed by the bracket.

Print STL bounds: 54x86x30.657 mm. Full project uses A1/0.4 mm, PETG, 0.2 mm
layers, four walls, 30% gyroid, normal snug supports. Remove supports from screw
holes and both mounting faces before assembly. Physical fit/strength untested.

CAD checks: single valid solid, watertight mesh, zero nominal base/body overlap,
and a 33.9 mm Y gap from camera envelope to a conservative moving-jaw band.
Hand/strap/cable geometry is not included. These are geometric checks, not load
or full-motion certification.

## Camera integration

This is a mechanical change only. The D405 is a close-range stereo camera, not
the original fisheye. Capture integration, camera calibration, marker visibility,
and camera-to-gripper extrinsics need checking with the D405 before collecting
usable data. Existing fisheye calibration must not be reused.

## Dimensional source

RealSense D400 Series Datasheet, October 2025, Figure 10-13, printed page 146:
https://realsenseai.com/wp-content/uploads/2025/09/Intel-RealSense-D400-Series-Datasheet-October-2025.pdf
Rear M3 pair: 20 mm pitch; maximum insertion 4 mm; body 42x42x23 mm.
Original bracket design in this folder; camera envelope is schematic.
