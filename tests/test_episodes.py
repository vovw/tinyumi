import json
import threading

import cv2
import numpy as np
import pytest

from tinyumi.config import load_json, save_json
from tinyumi.episodes import EpisodeWriter, read_frames, validate_episode
from tinyumi.export import export_umi


def change_row(path, mutator):
    rows = read_frames(path)
    mutator(rows)
    (path / 'frames.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows))


def test_lossless_recording_and_export(episode_factory, tmp_path):
    paths = [episode_factory(), episode_factory()]
    assert all(validate_episode(p)['accepted'] for p in paths)
    depth = cv2.imread(str(paths[0] / 'depth/000000.png'), cv2.IMREAD_UNCHANGED)
    assert depth.dtype == np.uint16 and np.all(depth == 300)
    out = tmp_path / 'dataset.zarr.zip'
    report = export_umi(paths, out)
    assert report['frames'] == 40
    import zarr
    with zarr.ZipStore(str(out), mode='r') as store:
        group = zarr.open_group(store, mode='r')
        assert group['data/camera0_rgb'].shape == (40, 224, 224, 3)
        assert group['data/robot0_gripper_width'].shape == (40, 1)
        np.testing.assert_array_equal(group['meta/episode_ends'][:], [20, 40])
        np.testing.assert_array_equal(group['data/camera0_rgb'][0, 0, 0], [127, 0, 0])
        assert group['data/robot0_eef_pos'][19, 0] == pytest.approx(.019)
        assert group['data/robot0_demo_end_pose'][0, 0] == pytest.approx(.019)
    with pytest.raises(FileExistsError):
        export_umi(paths, out)


@pytest.mark.parametrize('fault, expected', [
    ('pose', 'missing_pose'), ('width', 'missing_aperture'), ('number', 'color_frame_loss_or_duplicate'),
    ('timestamp', 'color_timestamp_gap'), ('sync', 'rgb_depth_not_synchronized'),
    ('domain', 'color_clock_invalid'), ('nan', 'malformed_pose')])
def test_invalid_frames_rejected(episode_factory, tmp_path, fault, expected):
    path = episode_factory()
    def mutate(rows):
        r = rows[3]
        if fault == 'pose': r['tracking']['pose_valid'] = False
        if fault == 'width': r['tracking']['aperture_valid'] = False
        if fault == 'number': r['color']['frame_number'] += 1
        if fault == 'timestamp': r['color']['timestamp_ms'] += 10
        if fault == 'sync': r['depth']['timestamp_ms'] += 20
        if fault == 'domain': r['color']['clock_domain'] = 'system_time'
        if fault == 'nan': r['tracking']['tcp_pose'][0] = float('nan')
    change_row(path, mutate)
    report = validate_episode(path)
    assert expected in report['failures']
    with pytest.raises(ValueError):
        export_umi([path], tmp_path / 'bad.zip')


def test_incomplete_and_corrupt_images(episode_factory):
    path = episode_factory()
    (path / 'rgb/000000.png').unlink()
    assert not validate_episode(path)['accepted']
    m = load_json(path / 'manifest.json')
    m['status'] = 'incomplete'
    save_json(path / 'manifest.json', m)
    assert 'episode_not_complete' in validate_episode(path)['failures']


@pytest.mark.parametrize('fps', [0, -30, None])
def test_invalid_frame_rate_rejected(episode_factory, fps):
    path = episode_factory()
    manifest = load_json(path / 'manifest.json')
    manifest['camera']['fps'] = fps
    save_json(path / 'manifest.json', manifest)
    report = validate_episode(path)
    assert not report['accepted']
    assert report['failures'][0].startswith('corrupt_episode:')


def test_writer_error_marks_incomplete(tmp_path, calibration, monkeypatch):
    monkeypatch.setattr(cv2, 'imwrite', lambda *a: False)
    writer = EpisodeWriter(tmp_path, calibration, calibration['camera'])
    writer.submit(np.zeros((10, 10, 3), np.uint8), np.zeros((10, 10), np.uint16), {})
    path = writer.finish()
    m = load_json(path / 'manifest.json')
    assert m['status'] == 'incomplete'
    assert any('PNG writer failed' in s for s in m['failures'])


def test_overflow_marks_incomplete(tmp_path, calibration, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    real_write = cv2.imwrite
    def slow_write(*args):
        entered.set()
        release.wait(timeout=5)
        return real_write(*args)
    monkeypatch.setattr(cv2, 'imwrite', slow_write)
    writer = EpisodeWriter(tmp_path, calibration, calibration['camera'], queue_size=1)
    rgb, depth = np.zeros((10, 10, 3), np.uint8), np.zeros((10, 10), np.uint16)
    writer.submit(rgb, depth, {})
    assert entered.wait(timeout=5)
    writer.submit(rgb, depth, {})
    try:
        with pytest.raises(RuntimeError, match='overflow'):
            writer.submit(rgb, depth, {})
    finally:
        release.set()
        path = writer.finish()
    assert load_json(path / 'manifest.json')['status'] == 'incomplete'
