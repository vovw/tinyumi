# tinyumi assembly

This guide follows the CAD assembly. The new mounts, stops and printed tips
still need physical fit verification. Use the [fastener table](fasteners.md)
for screw sizes, quantities and confidence; it supersedes the original blanket
advice to pick unspecified screws from an assortment.

## 1. Choose and print parts

Use one of the [two-plate projects](../bambu/full_rebuild/README.md), selecting
D405 or original fisheye camera. These contain the combined Quest/rail-stop base,
two adapters with integral racks, two L-brackets, two finger holders, four
pinion fit variants, four stops and two prototype tips. Install only one pinion.
The [Quest support](../pos-tracking/quest_mount/handumi_v1/README.md) is separate:
print the appropriate left or right support if needed. Original YAM Linear 4310
tips may replace the rigid prototypes.

## 2. Install inserts

Install M3 inserts in the locations listed in the [insert table](fasteners.md#heat-set-insert-locations)
while parts are separate. Keep them square and allow them to cool.
The axle insert belongs in the **base**, not in the pinion’s bearing recess.
The larger tip and holder holes are clearance holes, not M3 insert pockets.

## 3. Rails and end stops

Mount two 100 mm MGN9 rails with one MGN9C carriage each. Align them so each
carriage travels freely. Keep carriages restrained until stops are installed.
Use the [four printed stops](../hardware/rail_stops/README.md), two A and two B
on matching diagonals, with M3 × 8 countersunk screws in the combined base’s
side-facing inserts. The original unmodified base cannot accept these stops.
Gently verify that each carriage contacts its stop before leaving the rail;
clone carriage dimensions may differ. If retaining original rubber caps instead,
trim only enough to clear the adapters while still retaining the carriages.

## 4. Adapters and pinion

Bolt one adapter to each carriage, with both integral racks facing the central
pinion. Stack two MR63ZZ bearings (3 × 6 × 2.5 mm each) in the pinion. Mount the
axle through the bearings into the base insert. Check the complete head/bearing
stack: the screw must retain the axle without clamping the rotating gear.

Trial-fit the four pinion variants and use the smoothest one. Moving either jaw
should move the other symmetrically without binding, tooth skipping or excessive
wobble. Verify axle retention as well as free rotation.

## 5. L-brackets, finger holders and tips

Attach each L-bracket to its adapter using the two outer mounting positions.
Attach each curved finger holder at its smaller centre mounting hole. Trial-fit
the tips and holder together before final tightening: one lower joint is shared.
There are two tip screws per side. **M4 × 12 is only a suggested trial size**;
confirm the receiving thread and both clamped stacks as explained in the
[fingertip guidance](fasteners.md#fingertip-joint-measure-before-tightening).

Thread one hook-and-loop strap through each holder, two straps per gripper.
Check hand clearance through the entire jaw stroke.

## 6. Camera

For D405, follow the [mount guide](../hardware/realsense_d405/README.md): two
M3 × 8 socket-head screws through the rear pad, and two M3 × 8 countersunk screws
into the base. Camera screw entry must not exceed 4 mm. Test the supplied fit
gauge first. Check the actual cable plug and bend clearance.

For the original fisheye, use its camera mount on the base’s camera-side
underside interface. The jaw L-brackets belong on the adapters, not at this
camera joint. Set and lock the lens focus before calibrating intrinsics.

The D405 mount has a new pose. Calibrate the selected camera and its transform
to the gripper; do not reuse fisheye calibration for D405.

## 7. Markers and pose source

Print [tip markers](../pos-tracking/markers/tip_markers_9mm_ID13_14.pdf) at 100%
scale, one 9 mm marker per tip. Seat them flat with full-face tape and verify
visibility across the aperture. The original fisheye placement was 25 mm from
the gripper base; check visibility again with D405.

If using Quest, attach the support with two M3 × 10 countersunk screws in the
revised underside pad. Verify real controller fit, retention, tracking surfaces,
buttons and hand clearance. Calibrate controller-to-tool pose and synchronize
pose with camera data; this repository does not supply a completed Quest capture
pipeline. The [marker-ball tracker](../pos-tracking/README.md) remains an
alternative with its own assembly and calibration procedure.

## 8. Final fit check

Confirm inserts do not rotate, joints clamp before screws bottom, rails remain
parallel, stops retain both carriages, and the axle is retained while the pinion
spins freely. Sweep the jaws with straps, camera cable and optional controller
in place. Check fingertip fastening, marker visibility and camera view before
using the gripper to collect data. Record measured screw lengths and any fit
changes for the next revision.
