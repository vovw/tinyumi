import numpy as np
import pytest

from tinyumi.camera import check_calibration_camera
from tinyumi.cli import main
from tinyumi.config import load_calibration, require_complete, save_json


def test_calibration_is_bound_to_stream(calibration):
    check_calibration_camera(calibration, calibration['camera'])
    with pytest.raises(ValueError, match='serial'):
        check_calibration_camera(calibration, dict(calibration['camera'], serial='other'))
    with pytest.raises(ValueError, match='resolution'):
        check_calibration_camera(calibration, dict(calibration['camera'], intrinsics=dict(calibration['intrinsics'], width=1280)))
    with pytest.raises(ValueError, match='frame rate'):
        check_calibration_camera(calibration, dict(calibration['camera'], fps=60))


def test_record_refuses_uncalibrated_gripper(calibration, tmp_path, capsys):
    calibration['T_camera_tool'] = None
    p = tmp_path / 'calibration.json'
    save_json(p, calibration)
    assert main(['record', '--calibration', str(p), '--headless', '--seconds', '1']) == 1
    assert 'calibrate gripper' in capsys.readouterr().err


def test_cli_missing_display_is_clean_error(monkeypatch, capsys):
    monkeypatch.delenv('DISPLAY', raising=False)
    monkeypatch.delenv('WAYLAND_DISPLAY', raising=False)
    assert main(['preview', '--calibration', 'not-needed.json']) == 1
    assert 'No desktop display' in capsys.readouterr().err


def test_factory_inverse_model_loads(calibration, tmp_path):
    calibration['intrinsics']['model'] = 'inverse_brown_conrady'
    p = tmp_path / 'calibration.json'
    save_json(p, calibration)
    require_complete(load_calibration(p))
    calibration['jaw_axis_camera'] = [0, 0, 0]
    with pytest.raises(ValueError, match='jaw axis'):
        require_complete(calibration)


@pytest.mark.parametrize('seconds', ['nan', 'inf', '-1'])
def test_record_rejects_invalid_duration(calibration, tmp_path, capsys, seconds):
    p = tmp_path / 'calibration.json'
    save_json(p, calibration)
    assert main(['record', '--calibration', str(p), '--headless', '--seconds', seconds]) == 1
    assert '--seconds must be finite and nonnegative' in capsys.readouterr().err


def test_tip_sample_discards_previous_opening():
    from tinyumi.calibration import capture_tip_sample

    class Camera:
        stale = True

        def flush(self):
            self.stale = False

        def read(self):
            return self.stale, None, None

    class Tracker:
        def detect(self, stale):
            return stale

        def tip_poses(self, stale):
            pose = np.eye(4)
            pose[0, 3] = .01 if stale else .05
            return {'13': pose, '14': pose.copy()}

    tips = capture_tip_sample(Camera(), Tracker(), count=3)
    assert tips['14'][0, 3] == pytest.approx(.05)


def test_partial_episode_after_keyboard_interrupt(calibration, tmp_path, monkeypatch):
    from tinyumi import cli
    from tinyumi.config import load_json
    class Camera:
        metadata = calibration['camera']
        def __init__(self, *args): self.count = 0
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def flush(self): pass
        def read(self):
            self.count += 1
            if self.count == 3: raise KeyboardInterrupt
            stamp = dict(frame_number=self.count, timestamp_ms=self.count*1000/30, clock_domain='test')
            return np.zeros((480,640,3),np.uint8),np.zeros((480,640),np.uint16),dict(color=stamp,depth=stamp,host_monotonic_ns=self.count)
    monkeypatch.setattr(cli, 'Camera', Camera)
    p = tmp_path / 'calibration.json'
    save_json(p, calibration)
    out = tmp_path / 'episodes'
    assert main(['record','--calibration',str(p),'--headless','--seconds','10','--output',str(out)]) == 130
    m = load_json(next(out.glob('*/manifest.json')))
    assert m['status'] == 'incomplete' and m['frames'] == 2
