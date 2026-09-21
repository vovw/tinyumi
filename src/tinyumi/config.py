import hashlib
import json
from pathlib import Path

import numpy as np

from .geometry import check_transform


def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    temporary.replace(path)


def load_json(path):
    return json.loads(Path(path).read_text())


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def load_calibration(path):
    c = load_json(path)
    if c.get('schema_version') != 1:
        raise ValueError('Unsupported calibration schema')
    if c.get('dictionary') != 'DICT_4X4_50':
        raise ValueError('Expected DICT_4X4_50')
    if c.get('T_camera_tool') is not None:
        check_transform(c['T_camera_tool'])
    i = c['intrinsics']
    if min(i['fx'], i['fy'], i['width'], i['height']) <= 0:
        raise ValueError('Invalid camera intrinsics')
    if not np.isfinite([i['fx'], i['fy'], i['ppx'], i['ppy'], *i['coeffs']]).all():
        raise ValueError('Nonfinite camera intrinsics')
    if i['model'] not in ('none', 'brown_conrady', 'inverse_brown_conrady'):
        raise ValueError('Unsupported OpenCV distortion model; refine with ChArUco')
    if len(i['coeffs']) != 5:
        raise ValueError('Expected five Brown-Conrady distortion coefficients')
    if not 0 < c['tip_size_m'] < .1:
        raise ValueError('Invalid tip marker size (metres)')
    corners = c['board']['corners_m']
    if not corners or any(not 20 <= int(key) <= 31 or np.shape(value) != (4, 3)
                          or not np.isfinite(value).all() for key, value in corners.items()):
        raise ValueError('Invalid workspace board geometry')
    return c


def require_complete(c):
    if not all(c.get(k) is not None for k in ('T_camera_tool', 'aperture', 'jaw_axis_camera')):
        raise ValueError('Run calibrate gripper before recording')
    axis = np.asarray(c['jaw_axis_camera'], float)
    if axis.shape != (3,) or not np.isfinite(axis).all() or not np.isclose(np.linalg.norm(axis), 1):
        raise ValueError('Invalid calibrated jaw axis')
    a = c['aperture']
    if not np.isfinite(list(a.values())).all() or not 0 <= a['min_m'] < a['max_m'] or not .5 <= a['slope'] <= 1.5:
        raise ValueError('Invalid aperture calibration')
