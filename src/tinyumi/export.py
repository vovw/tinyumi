"""Original UMI replay-buffer schema, without GoPro-specific preprocessing."""

import tempfile
from pathlib import Path

import cv2
import numpy as np

from .config import load_json
from .episodes import read_frames, validate_episode

UMI_REVISION = 'd095ba9590df789df5189eea5ee7e431689038a6'


def export_umi(episodes, output):
    import zarr
    from numcodecs import Blosc

    output = Path(output)
    if output.exists():
        raise FileExistsError(output)
    reports = [validate_episode(p) for p in episodes]
    rejected = [r for r in reports if not r['accepted']]
    if rejected:
        raise ValueError(f'Export refused; invalid episodes: {rejected}')
    if not episodes:
        raise ValueError('No episodes supplied')
    manifests = [load_json(Path(p) / 'manifest.json') for p in episodes]
    if any(m['camera']['fps'] != 30 for m in manifests):
        raise ValueError('UMI v1 export requires 30 Hz; no implicit resampling')
    if len({m['calibration_sha256'] for m in manifests}) != 1:
        raise ValueError('Use one calibration per export; combine datasets explicitly after frame reconciliation')
    if any(r['frames'] < 16 for r in reports):
        raise ValueError('UMI action horizon requires at least 16 frames per episode')
    output.parent.mkdir(parents=True, exist_ok=True)
    # Disk-backed staging bounds memory, and ZipStore receives every key exactly once.
    with tempfile.TemporaryDirectory(prefix='tinyumi-export-', dir=output.parent) as staging:
        root = zarr.open_group(str(Path(staging) / 'data.zarr'), mode='w')
        data, meta = root.create_group('data'), root.create_group('meta')
        ends = np.cumsum([r['frames'] for r in reports])
        total = int(ends[-1])
        meta.array('episode_ends', ends.astype(np.int64), compressor=None)
        root.attrs.update(umi_revision=UMI_REVISION, fps=30, image_transform='center_square_crop_resize_224',
                          source_episodes=[str(p) for p in episodes], calibration_sha256=manifests[0]['calibration_sha256'])
        codec = Blosc(cname='zstd', clevel=3, shuffle=Blosc.BITSHUFFLE)
        arrays = {}
        for key, dim in [('eef_pos', 3), ('eef_rot_axis_angle', 3), ('gripper_width', 1),
                         ('demo_start_pose', 6), ('demo_end_pose', 6)]:
            arrays[key] = data.create_dataset('robot0_' + key, shape=(total, dim), chunks=(min(total, 1024), dim), dtype='f4', compressor=codec)
        images = data.create_dataset('camera0_rgb', shape=(total, 224, 224, 3), chunks=(1, 224, 224, 3), dtype='u1', compressor=codec)
        start = 0
        for episode in episodes:
            rows = read_frames(episode)
            n = len(rows)
            poses = np.asarray([r['tracking']['tcp_pose'] for r in rows], np.float32)
            arrays['eef_pos'][start:start+n] = poses[:, :3]
            arrays['eef_rot_axis_angle'][start:start+n] = poses[:, 3:]
            arrays['gripper_width'][start:start+n] = np.array([r['tracking']['aperture_m'] for r in rows])[:, None]
            arrays['demo_start_pose'][start:start+n] = np.repeat(poses[:1], n, axis=0)
            arrays['demo_end_pose'][start:start+n] = np.repeat(poses[-1:], n, axis=0)
            for j in range(n):
                bgr = cv2.imread(str(Path(episode) / 'rgb' / f'{j:06d}.png'))
                h, w = bgr.shape[:2]
                side = min(h, w)
                crop = bgr[(h-side)//2:(h+side)//2, (w-side)//2:(w+side)//2]
                images[start+j] = cv2.cvtColor(cv2.resize(crop, (224, 224), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2RGB)
            start += n
        archive = Path(staging) / 'dataset.zarr.zip'
        with zarr.ZipStore(str(archive), mode='w') as store:
            zarr.copy_store(root.store, store)
        archive.replace(output)
    return dict(output=str(output), episodes=len(episodes), frames=total, umi_revision=UMI_REVISION)
