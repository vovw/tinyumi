import numpy as np
import pytest

from tinyumi.episodes import EpisodeWriter
from tinyumi.markers import board_geometry


@pytest.fixture
def calibration():
    intr = dict(width=640, height=480, fx=600., fy=600., ppx=320., ppy=240.,
                model='brown_conrady', coeffs=[0.] * 5)
    camera = dict(serial='synthetic', fps=30, intrinsics=intr, depth_intrinsics=intr,
                  depth_scale_m=.001, depth_aligned=False)
    return dict(schema_version=1, dictionary='DICT_4X4_50', serial='synthetic', camera=camera,
                intrinsics=intr, tip_size_m=.009, board=dict(corners_m=board_geometry()),
                T_camera_tool=np.eye(4).tolist(), jaw_axis_camera=[1, 0, 0],
                aperture=dict(slope=1., intercept_m=-.01, min_m=0., max_m=.1), max_reprojection_px=1.5)


@pytest.fixture
def episode_factory(tmp_path, calibration):
    def create(n=20, **kwargs):
        writer = EpisodeWriter(tmp_path, calibration, calibration['camera'], **kwargs)
        for i in range(n):
            stamp = dict(frame_number=i+1, timestamp_ms=i * 1000 / 30, clock_domain='hardware_clock')
            tracking = dict(tags={}, board_ids=['20', '21'], reprojection_px=.1,
                            tcp_pose=[i * .001, 0., .1, 0., 0., 0.], aperture_m=.03,
                            pose_valid=True, aperture_valid=True)
            rgb = np.zeros((480, 640, 3), np.uint8)
            rgb[:, :, 0] = 127  # Detect accidental RGB/BGR reversal in exporter.
            writer.submit(rgb, np.full((480, 640), 300, np.uint16),
                          dict(color=stamp, depth=stamp, host_monotonic_ns=(i+1)*33333333, tracking=tracking))
        return writer.finish()
    return create
