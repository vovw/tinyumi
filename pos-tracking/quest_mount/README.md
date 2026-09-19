# Quest Touch Plus mount — concept v0

**Superseded:** use the [actual HandUMI support adaptation](handumi_v1/README.md).
The tall-cradle files below are retained as an earlier design study.

Design study for tinyumi with Quest 3 / 3S and Touch Plus controllers. This is a
prototype concept, not a fit-verified production part. Controller contact shape,
tracking visibility, fastener access and full hand/jaw clearance need physical
verification. No Quest tracking integration has been installed or measured here.

## Deliverables

- `quest_mount_concept.png`: annotated CAD concept view.
- `quest_mount_CONCEPT.step`: editable solid for fitting in CAD.
- `quest_mount_CONCEPT.stl`: prototype mesh; not a release-ready print.
- `build_concept.py`: parametric source and reproducible rendering/export.
- `concept_validation.json`: geometric checks and explicitly unverified items.
- `controller_ENVELOPE_NOT_FOR_FIT.stl`: simplified visual placeholder only.

The initial flange pitch is 40.57 mm, taken from the circular edge centers at
x = ±20.285, y = 29 mm in `hardware/STEP/plate_v6.step`. These are 4 mm diameter
features; the concept uses M3 clearance holes for an insert-based attachment.
This is an interface candidate, not proof of available mounting real estate:
the camera already uses this region. Resolve the installed camera fastener
stack, access, actual thread and full surrounding clearances before fitting.
The exported part is in its own local frame, not a verified assembly transform.

Nominal concept dimensions: 56 x 24 x 6 mm flange, 62 mm controller-axis offset,
4 mm saddle wall, 48 mm saddle height and two 10 mm retention bands. The
38 x 34 mm inner ellipse is a provisional contact envelope, not a measured
Touch Plus cross-section. It must be refitted before tightening onto a controller.
The displayed bands are illustrative purchased straps; the controller envelope
and bands are excluded from the printable mount STL.

For a first fit coupon, section just the saddle in CAD and check it against the
controller before printing the bridge. PETG is a reasonable prototype material;
use multiple walls and orient the bridge to avoid a weak layer-peel load path.
Print settings and strength are not validated. Measure the final fastener stack
before choosing screw lengths, and add a loose controller safety tether.

## Recommendation

Prototype Quest as an alternative pose source. It can remove the external pose
camera, marker-ball calibration and ball stalk from portable collection. Keep
the YAM wrist camera and aperture markers: a controller measures its own pose,
not the opening of the mechanical jaws. The wrist camera USB cable remains.

The current repo reports 0.46 mm RMS within settled holds, not moving TCP
accuracy, and unresolved 14% scale / 9 degree direction discrepancies against
robot FK. Quest is not a demonstrated accuracy upgrade. Its benefit is likely
collection convenience; dynamic accuracy, occlusion, drift and reacquisition
need an apples-to-apples comparison. The tracker solver itself was not found in
this checkout, so this comparison uses its hardware and published measurements.

## Mechanical layout

Borrow HandUMI's controller-over-the-hand arrangement, while keeping this
project's YAM camera-to-jaw geometry. Use a rigid load path:

    stationary gripper plate -> short braced bridge -> controller cradle

Do not use the moving finger holders or a skin-mounted wrist strap as the pose
reference. Do not put a controller on the existing 80 mm, 8 x 8 mm marker stalk
without a separate stiffness/load assessment. A wrist strap can be a loose
safety tether, but must not change the controller-to-gripper transform.

The proposed concept has a two-screw mounting flange, a short boxed/gusseted
bridge and an open cradle. A hard locating surface and two separated retention
bands resist sliding and rotation. Thin replaceable pads protect the controller;
soft padding must not become the structural reference. Final pads and locating
surfaces must match a measured controller section. The opening is deliberately
parametric rather than claiming a scan-derived Touch Plus fit.

Keep the controller face, upper perimeter, lower tracking region, buttons and
trigger clear. The controller bottom remains open. Verify IR visibility with
the real controller and headset, including both hands crossing, palm-down
grasps, reaching into shelves and looking away. Mounting the controller on a
gripper differs from its normal held-in-hand use and must be validated as such.

Use the shortest bridge that clears the actual hand and wrist-camera image.
Start with a fixed mount; change its geometry between trials rather than using
an unlocked ball joint. Every change to controller seating or mount geometry
requires a new controller-to-TCP calibration. Left and right controller contact
surfaces should be fitted separately rather than assuming perfect mirroring.

## Pose integration

[HandUMI Quest App](https://github.com/murobotics-ai/handumi-quest-app) already
streams controller and headset telemetry. Its
[protocol](https://github.com/murobotics-ai/handumi-quest-app/blob/main/protocol.md)
documents newline-delimited JSON over TCP port 65432, tracked/valid flags,
runtime timestamps and UDP clock synchronization on port 42000. Its presence
does not by itself make the tinyumi recording pipeline complete.

There is also a local `vr-teleop-kit` project with a Quest WebXR pose transport.
Its clutching, gain scaling and IK outputs are for teleoperation. For physical
demonstration recording, take raw metric poses before those modifications.
Record the exact pose reference used (grip versus aim, runtime convention),
source time, reception time, tracking state and coordinate-frame convention.

With T_A_B mapping coordinates from B into A:

    T_world_tcp(t) = T_world_controller(t) * T_controller_tcp

Calibrate both translation and rotation of T_controller_tcp with a rigid
fixture and multiple orientations. Pivot calibration alone finds an offset;
it does not determine the complete orientation alignment. If deployment needs
the robot base frame, additionally calibrate T_robot_world. Verify handedness,
quaternion order, metres and axis conversion with known translations/rotations.
Do not multiply by the HMD pose again if the app already sends world poses.

Synchronize Quest source time with wrist video and aperture timestamps. TCP
arrival time is not acquisition time. Record/reject stale and invalid poses;
never silently carry a frozen pose through a tracking outage. Split or reject
episodes after recentering/relocalization discontinuities until the world frame
is re-established. Quest still uses internal tracking/SLAM; it removes the need
to implement an offline wrist-camera pose solver, not every calibration step.

## Before choosing it over the ball

1. Fit the cradle to the actual Touch Plus controller. Confirm no button preload,
   bottom obstruction or controller slip, and full aperture/hand/camera clearance.
2. Attach both trackers temporarily to the same rigid body, keeping both visible.
   Measure their fixed extrinsic and time offset; compare at the same TCP.
3. Record static holds, repeated fixture returns, measured straight motions,
   fast wrist rotations, occlusions and ten-minute trajectories. Include removal
   and reinsertion of the controller to measure mount repeatability.
4. Compare valid-frame fraction, outage duration, recovery jumps, lag, relative
   trajectory agreement and start/end drift. Use an independent measured fixture
   or calibrated reference for absolute error: disagreement alone cannot tell
   which tracker is right, especially with the existing unresolved FK comparison.
5. Choose acceptance limits from the intended manipulation task before comparing.
   Keep the ball as a debug/reference option until Quest passes those limits.

Mount stiffness matters: 1 degree of angular motion over a 150 mm lever arm
produces about 2.6 mm of apparent TCP displacement. Those are illustrative
values, not measured dimensions or errors for this build.

## Sources and scope

- [HandUMI hardware](https://github.com/murobotics-ai/handumi-hw): controller
  supports and wrist-mounted VR tracking. Local reference inspected at ef0c784.
  Arrangement inspiration only; no upstream CAD is copied into this concept.
- [HandUMI software](https://github.com/murobotics-ai/handumi-sw): Quest support
  and physical controller-to-TCP calibration metadata.
- [Current tracker](../README.md) and [tinyumi](../../README.md): existing
  mechanism, marker geometry, measured settled-hold statistics and limitations.

Upstream pages inspected 2026-09-12. This work adds a design study alongside the
existing tracker; it does not claim the Quest replacement has been validated.
