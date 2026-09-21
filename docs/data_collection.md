# Collecting D405 tabletop demonstrations

This is a single-gripper pipeline for the D405 mount. It records lossless RGB,
native depth, ArUco observations, tool pose and measured gripper opening. The
workspace board must remain stationary and visible. It does not run SLAM.

## Install and check the camera

From the repository root on Ubuntu 22.04:

```bash
uv sync --locked --extra export --extra test
uv run tinyumi doctor
```

`uv.lock` pins the environment. The default profile is RGB8 + Z16 at 640×480,
30 Hz. `doctor` enumerates available profiles and reports SDK/firmware/USB versions.
USB/udev initialization errors mean the process cannot access USB; they do not
prove the camera is disconnected. Run on the physical host with normal RealSense
udev rules and USB access, not an isolated container without device passthrough.
Do not make all USB devices world-writable.

## Print and install markers

```bash
uv run tinyumi make-board data/boards
```

Open `data/boards/workspace.svg` in a browser or vector application and print on
A4 at **100% / actual size**. Disable fit/shrink scaling; measure the 100 mm ruler
and a 30 mm black marker edge. SVG page size is explicitly 210×297 mm. Mount the
sheet flat on a rigid board. Twelve markers, IDs 20–31, occupy a 150×110 mm area.
Keep at least two separated markers visible; more is better. Do not rearrange
them or move the board during a session.

For the jaws use the existing
[9 mm ID13/14 marker sheet](../pos-tracking/markers/tip_markers_9mm_ID13_14.pdf).
Measure each black outer edge at 9 mm, excluding the white margin. Attach one
per tip, fully flat, with full-face adhesive. Check both tags over the entire
opening range. All collection markers are **ArUco DICT_4X4_50**, not AprilTags.
The existing ball tracker is not used by this pipeline.

The separate `charuco.svg` is a 7×5-square intrinsics target (25 mm squares,
18 mm markers). Its IDs overlap tip IDs: **remove it before gripper calibration
and collection**. Never have duplicate physical IDs in the camera view.

## Calibrate this physical unit

Read factory calibration and attach the measured board definition:

```bash
uv run tinyumi calibrate init --board data/boards/board.json \
  --output data/calibration/factory.json
uv run tinyumi preview --calibration data/calibration/factory.json
```

Preview works before gripper calibration, but pose and opening will say MISSING.
Check ID13, ID14 and several board IDs are detected during a rehearsal. Adjust
lighting, camera/board placement or tag mounting if needed. A D405 image does not
have the original fisheye's field of view. Avoid blurred/underexposed markers.
`calibrate init` optionally accepts `--exposure-us` and `--gain` to lock exposure
and gain. Device-supported ranges are checked, settings are applied after stream
start and saved/reapplied in later sessions. Choose a short exposure that freezes
your actual movement and provide enough steady light; validate image sharpness,
not just option readback. Omission retains the device's current exposure mode.
Actual exposure/gain metadata are saved per frame when provided by the SDK.
If the tabletop board cannot stay in view, this pose source is unsuitable for
that task; additional tracking hardware is needed.

Factory inverse Brown–Conrady intrinsics use RealSense SDK deprojection before
OpenCV pose solving. They are never passed to OpenCV as forward-distortion
coefficients. For validation/refinement, print and measure the ChArUco target:

```bash
uv run tinyumi calibrate charuco --calibration data/calibration/factory.json \
  --output data/calibration/intrinsics.json
```

SPACE captures a board view; `q` solves after at least 15 views. Cover the image
corners and centre at varied tilts/distances, holding still for each exposure.
At least ten corners per view are needed. RMS must be ≤1 px; low RMS alone is
not a substitute for diverse views or a correctly scaled target. Observations
and factory intrinsics are preserved. Changing intrinsics invalidates gripper
calibration and requires repeating it.

Copy `configs/gripper_measurements.example.json` to your data directory and
replace every null with actual measurements. Each offset is the vector from a
tag centre to the corresponding inner contact-face centre, in that tag's axes:
printed right = +X, printed down = +Y, into the tag = +Z. Measure in millimetres.
Also specify the unit vector pointing from palm toward fingertips in ID13's
marker frame. This fixes the tool orientation independently of the camera mount.

```bash
uv run tinyumi calibrate gripper --calibration data/calibration/intrinsics.json \
  --measurements data/gripper_measurements.json \
  --output data/calibration/ready.json
```

Follow the terminal prompts. At each opening hold the jaws still and enter the
measured distance between the inner contact faces in mm. Capture at least five
distinct widths spanning ≥10 mm, including closed and maximum open. Blank input
finishes. Each sample requires 30 valid two-tag observations. Unstable samples,
aperture fit errors >2 mm, or midpoint shifts >3 mm are rejected. Save calibration
to a new filename; existing files are never overwritten by the CLI.

Camera/TCP geometry is measured, not taken from CAD. Metres are used internally.
`T_a_b` maps coordinates in b into a. Tool origin is the midpoint of the contact
faces; +X runs from ID13 to ID14, +Z runs toward the fingertips, +Y completes the
right-handed frame. World origin is ID20's top-left black corner, +X is printed
right, +Y printed down, +Z into the board. Pose composition is
`T_world_tool = inverse(T_camera_world) @ T_camera_tool`. Orient the board
deliberately; this is not automatically the robot-base frame.

## Record and inspect

```bash
uv run tinyumi record --calibration data/calibration/ready.json \
  --output data/episodes --task "pick and place"
```

- `r`: start a new episode; `s`: finish it and print validation results.
- `d`: mark the active episode discarded (files retained).
- `q`, Ctrl-C, camera errors or writer failure: preserve an active episode as
  incomplete. Finish with `s` first if you want to keep it for export.

For a bounded headless recording, add `--headless --seconds 30`. It starts
immediately after camera warmup and completes when the timer expires. Headless
preview is also supported for a timed processing check. Graphical commands need
a desktop display.

Each uniquely named episode stores:

| File | Contents |
| --- | --- |
| `manifest.json` | Completion status, task, stream metadata, frame count, failures |
| `calibration.json` | Full calibration snapshot, hash bound to the manifest |
| `rgb/*.png` | Lossless original RGB image content |
| `depth/*.png` | Native uint16 depth; multiply by saved `depth_scale_m` |
| `frames.jsonl` | Frame numbers, device timestamps/domains, host monotonic time, raw tag corners, quality and derived labels |

Depth stays in its native camera coordinates; it is **not aligned to color**.
Saved intrinsics and depth-to-color extrinsics support later alignment. Raw
frames and timestamps are preserved when tracking is missing. A bounded SDK
queue holds up to 16 frame pairs to absorb scheduling jitter; episode start
discards any preview backlog. Host timestamps record dequeue time and are not
a substitute for device capture timestamps. Writer queues
are bounded to 60 frames; overflow invalidates the episode. Disk errors and
abrupt interruption never produce a completed manifest.

```bash
uv run tinyumi validate data/episodes/EPISODE
uv run tinyumi replay data/episodes/EPISODE
```

Validation reads images and checks frame continuity, clock stability, RGB/depth
timestamp separation, calibration integrity, pose and aperture availability.
No tracking-gap interpolation or held-last-pose is used. Pose needs at least two
workspace tags and ≤1.5 px RMS error, with separation between the planar pose
candidates. Reprojection RMS for inverse Brown calibration is in undistorted
pixel coordinates. Very front-facing/ambiguous views may be rejected: tilt the
view or reposition the board. Image-space confidence is not an absolute accuracy
certificate.

Before a dataset session: check closed/half/open widths against calipers (target
≤2 mm), a measured 100 mm motion (target ≤5 mm), and known rotations (target
≤3°). Cover the tags deliberately and verify MISSING appears. Record/replay a
ten-minute trial, then ten short demonstrations. These are physical acceptance
checks to perform with the assembled rig, not claimed results of software tests.

## Export to original UMI

```bash
uv run tinyumi export-umi data/episodes/EPISODE1 data/episodes/EPISODE2 \
  --output data/dataset.zarr.zip
```

Export fails if any selected episode is incomplete, discarded, corrupt, has a
tracking gap/frame loss, is shorter than 16 frames, or is not 30 Hz. All episodes
must use the same calibration snapshot. Nothing is silently interpolated,
resampled or skipped. RGB uses an aspect-preserving centre square crop followed
by 224×224 resizing. No original GoPro/fisheye masks or mirror processing are
applied; markers remain visible. Retain the board setup for matching training
and deployment observations or deliberately design later image preprocessing.
Depth remains available in source recordings; original UMI RGB training does
not consume it.

The export uses Zarr v2, standard lossless Blosc compression and
`meta/episode_ends`. It supplies `camera0_rgb`, `robot0_eef_pos`,
`robot0_eef_rot_axis_angle`, `robot0_gripper_width` and repeated episode start/end
poses. Rotations are axis-angle radians, distances metres. Upstream generates
relative action targets from these trajectories.

Compatibility target:
[original UMI revision d095ba9](https://github.com/real-stanford/universal_manipulation_interface/tree/d095ba9590df789df5189eea5ee7e431689038a6).
In that checkout/environment, train with:

```bash
python train.py --config-name=train_diffusion_unet_timm_umi_workspace \
  task.dataset_path=/absolute/path/to/data/dataset.zarr.zip \
  task.dataset_frequeny=30 task.obs_down_sample_steps=1 \
  task.camera_obs_latency=0 task.robot_obs_latency=0 task.gripper_obs_latency=0
```

`dataset_frequeny` intentionally matches upstream's spelling. The complete
override reference is `configs/umi_d405.yaml`. Pose/aperture labels are derived
from the same RGB frame, hence no relative GoPro latency correction. This does
not estimate robot execution latency. Deployment still needs a matching camera
view, tool/robot calibration and timing measurements. Existing GoPro-trained
checkpoints are not validated for D405 imagery.

## Developer checks

```bash
uv run --extra export --extra test pytest -q
```

The optional `tests/test_umi_integration.py` loads an exported synthetic dataset
through the actual pinned `UmiDataset` and assembles a training batch. Set
`UMI_SOURCE` to that checkout and run it in an environment with the dependencies
listed in the test's module docstring. It does not require a GPU or camera.

### PR verification (2026-09-21)

The offline suite passes 31 tests; the optional upstream UMI integration test
is skipped without `UMI_SOURCE` and its dependencies. Regression checks include
discarding buffered frames before a new jaw measurement and rejecting invalid
recording durations and episode frame rates. Hardware acceptance checks above
remain required before collecting usable demonstrations.

### Previously reported implementation checks (2026-09-19)

The following results were recorded during initial implementation. They were
not rerun during PR preparation, and raw diagnostic artifacts are not included
in this repository.

- 25 tests passed, including an actual upstream UMI training batch at the pinned
  revision. The regular capture environment runs 24 tests and skips that optional
  integration test unless its dependencies and checkout are supplied.
- The connected D405 (firmware 5.15.1.55, USB 3.2) streamed RGB8/Z16 at
  640×480/30 Hz. A buffered 30-second lossless diagnostic recording saved 900
  consecutive frame pairs with zero color/depth frame gaps and maximum pair
  timestamp difference of 0.308 ms.
- The first unbuffered trial exposed one dropped pair; the bounded SDK queue
  addresses scheduling jitter, and validation continues to reject frame loss.
- No fingertip tags were attached during these checks. Marker visibility,
  gripper calibration, absolute tracking accuracy, the ten-minute physical trial
  and real demonstration collection remain to be completed on the assembled rig.
