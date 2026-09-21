"""Append-only lossless frame files with atomic episode completion metadata."""

import json
import queue
import threading
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import cv2
import numpy as np

from .config import fingerprint, load_json, save_json


class EpisodeWriter:
    def __init__(self, root, calibration, camera, task='', queue_size=60):
        name = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '_' + uuid4().hex[:8]
        self.path = Path(root) / name
        self.path.mkdir(parents=True, exist_ok=False)
        (self.path / 'rgb').mkdir()
        (self.path / 'depth').mkdir()
        self.manifest = dict(schema_version=1, status='incomplete', created_utc=name,
                             task=task, calibration_sha256=fingerprint(calibration), camera=camera,
                             frames=0, failures=[])
        save_json(self.path / 'calibration.json', calibration)
        save_json(self.path / 'manifest.json', self.manifest)
        self.queue = queue.Queue(maxsize=queue_size)
        self.error = None
        self.count = 0
        self.closed = False
        self.thread = threading.Thread(target=self._write, daemon=True)
        self.thread.start()

    def _write(self):
        try:
            with (self.path / 'frames.jsonl').open('w') as f:
                while True:
                    item = self.queue.get()
                    if item is None:
                        return
                    rgb, depth, metadata = item
                    index = self.count
                    for folder, image in (('rgb', cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)), ('depth', depth)):
                        if not cv2.imwrite(str(self.path / folder / f'{index:06d}.png'), image,
                                           [cv2.IMWRITE_PNG_COMPRESSION, 1]):
                            raise OSError('PNG writer failed')
                    f.write(json.dumps(dict(index=index, **metadata), allow_nan=False) + '\n')
                    f.flush()
                    self.count += 1
        except Exception as exc:
            self.error = f'{type(exc).__name__}: {exc}'

    def submit(self, rgb, depth, metadata):
        if self.closed:
            raise RuntimeError('Episode is closed')
        if self.error:
            raise RuntimeError(self.error)
        try:
            self.queue.put_nowait((rgb.copy(), depth.copy(), metadata))
        except queue.Full:
            self.manifest['failures'].append('writer_queue_overflow')
            raise RuntimeError('Recording writer queue overflow; episode invalidated')

    def finish(self, status='complete', reason=None):
        if self.closed:
            return self.path
        if reason:
            self.manifest['failures'].append(reason)
        while self.thread.is_alive():
            try:
                self.queue.put(None, timeout=.1)
                break
            except queue.Full:
                continue
        self.thread.join()
        if self.error:
            self.manifest['failures'].append(self.error)
        if self.count == 0:
            self.manifest['failures'].append('empty_episode')
        self.manifest.update(frames=self.count, status=(status if not self.manifest['failures'] else 'incomplete'))
        save_json(self.path / 'manifest.json', self.manifest)
        self.closed = True
        return self.path


def read_frames(path):
    with (Path(path) / 'frames.jsonl').open() as f:
        return [json.loads(line) for line in f]


def validate_episode(path, check_images=True):
    path = Path(path)
    failures = []
    try:
        m = load_json(path / 'manifest.json')
        c = load_json(path / 'calibration.json')
        rows = read_frames(path)
        if m['status'] != 'complete':
            failures.append('episode_not_complete')
        failures.extend(m.get('failures', []))
        if fingerprint(c) != m['calibration_sha256']:
            failures.append('calibration_hash_mismatch')
        if not rows or len(rows) != m['frames']:
            failures.append('frame_count_mismatch_or_empty')
        if any(r['index'] != i for i, r in enumerate(rows)):
            failures.append('frame_index_gap')
        fps = m['camera']['fps']
        if not np.isfinite(fps) or fps <= 0:
            raise ValueError('Camera frame rate must be finite and positive')
        interval = 1000 / fps
        for stream in ('color', 'depth'):
            domains = {r[stream]['clock_domain'] for r in rows}
            nums = np.array([r[stream]['frame_number'] for r in rows])
            times = np.array([r[stream]['timestamp_ms'] for r in rows])
            if len(domains) != 1 or not np.isfinite(times).all():
                failures.append(f'{stream}_clock_invalid')
            if np.any(np.diff(nums) != 1):
                failures.append(f'{stream}_frame_loss_or_duplicate')
            if np.any(np.abs(np.diff(times) - interval) > interval * .2):
                failures.append(f'{stream}_timestamp_gap')
        if any(r['color']['clock_domain'] != r['depth']['clock_domain'] or
               abs(r['color']['timestamp_ms'] - r['depth']['timestamp_ms']) > interval / 2 for r in rows):
            failures.append('rgb_depth_not_synchronized')
        if np.any(np.diff([r['host_monotonic_ns'] for r in rows]) <= 0):
            failures.append('host_clock_not_monotonic')
        pose_count = sum(bool(r['tracking']['pose_valid']) for r in rows)
        width_count = sum(bool(r['tracking']['aperture_valid']) for r in rows)
        if pose_count != len(rows):
            failures.append('missing_pose')
        if width_count != len(rows):
            failures.append('missing_aperture')
        for r in rows:
            t = r['tracking']
            if t['pose_valid'] and (np.shape(t['tcp_pose']) != (6,) or not np.isfinite(t['tcp_pose']).all()):
                failures.append('malformed_pose')
            if t['aperture_valid'] and (t['aperture_m'] is None or not np.isfinite(t['aperture_m']) or t['aperture_m'] < 0):
                failures.append('malformed_aperture')
        if check_images:
            for folder, intr, dtype, channels in (
                ('rgb', m['camera']['intrinsics'], np.uint8, 3),
                ('depth', m['camera']['depth_intrinsics'], np.uint16, None)):
                expected = (intr['height'], intr['width']) + ((channels,) if channels else ())
                for i in range(len(rows)):
                    image = cv2.imread(str(path / folder / f'{i:06d}.png'), cv2.IMREAD_UNCHANGED)
                    if image is None or image.shape != expected or image.dtype != dtype:
                        failures.append(f'{folder}_image_invalid_{i}')
        errors = [r['tracking']['reprojection_px'] for r in rows if r['tracking']['reprojection_px'] is not None]
        return dict(path=str(path), accepted=not failures, frames=len(rows),
                    pose_fraction=pose_count / max(len(rows), 1), aperture_fraction=width_count / max(len(rows), 1),
                    max_reprojection_px=max(errors, default=None),
                    marker_frames={str(i): sum(str(i) in r['tracking']['tags'] for r in rows) for i in range(50)
                                   if any(str(i) in r['tracking']['tags'] for r in rows)},
                    failures=sorted(set(failures)))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return dict(path=str(path), accepted=False, failures=[f'corrupt_episode: {exc}'])
