# tinyumi :3

A hand-worn, 3D-printable UMI-style gripper for experiments with the I2RT YAM
linear gripper. Forked from [Yosub Shin’s YAM-UMI](https://github.com/YosubShin/yam-umi).

**tinyumi adds Quest controller supports, printed rail stops, a RealSense D405
mount, rigid prototype fingertips, and two-plate Bambu print projects.** The
original rack-and-pinion jaws, finger holders and YAM interface remain the basis
of the build.

These additions are **fit prototypes**. CAD and mesh checks are recorded, but
physical fit, strength, full hand/cable clearance and tracking performance are
not yet established. End-to-end data collection is not implemented here. The
D405 has a new camera pose; it does not inherit the original fisheye calibration
or the original camera-to-robot matching claim.

## Print and assemble

1. Choose a [full print project](bambu/full_rebuild/README.md):
   - [D405 version](bambu/full_rebuild/tinyumi_full_rebuild_D405_A1_PETG.3mf).
   - [Original fisheye version](bambu/full_rebuild/tinyumi_full_rebuild_A1_PETG.3mf).
2. Print **one** suitable [left or right Quest support](pos-tracking/quest_mount/handumi_v1/README.md)
   separately if using a controller. It is not included in either full project.
3. Follow the [assembly guide](docs/assembly.md) and [fastener table](docs/fasteners.md).
   Check the actual tip threads before buying or fitting tip screws.
4. Verify free jaw travel, end-stop retention and camera/hand clearance, then
   calibrate the chosen camera and pose source.

The full projects target Bambu A1, 0.4 mm nozzle and PETG. Plate 1 holds the
mechanism with four alternative pinions (install one); plate 2 holds two rigid
prototype tips. Original YAM tips can be used instead of the printed prototypes.
Settings are starting points; inspect supports and slice in Bambu Studio.

## What changed

| Addition | Files and details |
| --- | --- |
| Quest controller support | [Left/right HandUMI-derived supports and revised base](pos-tracking/quest_mount/handumi_v1/README.md) |
| Rail retention | [Four end stops and combined Quest/stop base](hardware/rail_stops/README.md) |
| D405 camera option | [One-piece mount, fit gauge and camera screw limits](hardware/realsense_d405/README.md) |
| Printable fingertips | [I2RT-derived rigid prototypes and print manifests](bambu/full_rebuild/README.md) |
| Assembly documentation | [Build order](docs/assembly.md), [screws and inserts](docs/fasteners.md), [change history](CHANGELOG.md) |

The [original BOM](bom/README.md) lists the baseline rails, bearings, straps and
shop supplies. Add hardware from the fastener table for the chosen options;
upstream prices are historical, not a current tinyumi cost estimate.

## Sources and rebuilding

Original CAD is in `hardware/STEP/` and `hardware/STL/`. Each new hardware folder
includes its generator and validation report. See [rebuilding](docs/rebuilding.md)
for commands and limitations. Legacy CAD and illustration filenames are retained
where they identify an upstream part or are consumed by generators.

The [original design notes](DESIGN.md) preserve the fisheye rationale and upstream
measurements. The [marker-based tracker documentation](pos-tracking/README.md)
remains available; its measurements do not validate the Quest alternative.
The earlier [Quest concept](pos-tracking/quest_mount/README.md) is superseded by
the HandUMI-derived supports.

## License and attribution

Original YAM-UMI design by **Yosub Shin**, under the retained [MIT license](LICENSE).
HandUMI-derived supports are Apache-2.0; I2RT reference meshes and derived tips
include their MIT attribution. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)
and the bundled source licenses. tinyumi is not affiliated with or endorsed by
I2RT, HandUMI, or the original UMI authors.
