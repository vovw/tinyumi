# tinyumi changes

## 2026-09-19 — initial tinyumi fork

Based on Yosub Shin’s YAM-UMI at `2862fe2`; original history and MIT notice retained.

- Adopted the **tinyumi** name and rewrote the entrypoint around the current
  build. Preserved original rationale and reported measurements in `DESIGN.md`.
- Added HandUMI-derived left/right controller supports with shortened angled
  mounting tabs, a revised base pad, pinned source CAD and Apache-2.0 license.
- Added four printed rail end stops, A/B print layouts, and a combined base
  accepting both the stops and Quest support.
- Added a one-piece D405 mount, rear-hole fit gauge, schematic camera envelope,
  assembly preview and geometric validation report.
- Added rigid left/right fingertip prototypes trimmed from pinned I2RT meshes,
  with source hashes and MIT attribution. Grip and mounting fit remain untested.
- Packaged fisheye and D405 Bambu A1 PETG projects, two plates each, with
  generators and object manifests. Quest supports are printed separately.
- Documented screw quantities, insert locations and assembly order. Corrected
  the pinion insert location and jaw-bracket placement. M4 × 12 tip screws are
  explicitly an unverified trial suggestion, not a confirmed hardware spec.
- Included assembly illustrations and geometric checks; excluded scratch work
  and superseded generated PDF guides from publication.

The original mechanism and tracking documentation remain available. New hardware
has not been physically validated; no Quest capture integration or D405 calibration
is claimed. Original settled-hold tracking measurements apply only to the
upstream marker-based setup.
