"""Interactive measurements; calibration never substitutes nominal CAD offsets."""

import copy
import time

import cv2
import numpy as np
from scipy.spatial.transform import Rotation

from .camera import Camera, check_calibration_camera
from .config import load_calibration, load_json, save_json
from .geometry import fit_aperture
from .markers import DICTIONARY, Tracker


def initialize(args):
    if not np.isfinite(args.tip_mm) or args.tip_mm <= 0:
        raise ValueError('Measured tip marker size must be positive')
    board = load_json(args.board)
    if board['dictionary'] != 'DICT_4X4_50':
        raise ValueError('Unsupported board dictionary')
    settings = dict(exposure_us=args.exposure_us, gain=args.gain)
    with Camera(args.serial, args.width, args.height, args.fps, settings) as camera:
        c = dict(schema_version=1, dictionary='DICT_4X4_50', serial=camera.metadata['serial'],
                 camera=camera.metadata, intrinsics=camera.metadata['intrinsics'], board=board,
                 tip_size_m=args.tip_mm / 1000, max_reprojection_px=1.5,
                 T_camera_tool=None, aperture=None, jaw_axis_camera=None,
                 intrinsics_source='factory', created_unix_s=time.time(), camera_settings=settings)
    save_json(args.output, c)
    print(f'Saved factory calibration to {args.output}; gripper calibration still required.')


def capture_tip_sample(camera, tracker, count=30):
    # Frames buffered while the operator adjusted the jaws belong to the old opening.
    camera.flush()
    samples = []
    for _ in range(count * 5):
        rgb, _, _ = camera.read()
        tags = tracker.detect(rgb)
        tips = tracker.tip_poses(tags)
        if len(tips) == 2:
            samples.append(tips)
        if len(samples) == count:
            break
    if len(samples) < count:
        raise ValueError('Cannot see both tip tags reliably. Run preview and fix visibility/focus/light.')
    result = {}
    for key in ('13', '14'):
        positions = np.array([s[key][:3, 3] for s in samples])
        rotations = Rotation.from_matrix([s[key][:3, :3] for s in samples])
        mean_r = rotations.mean()
        spread = np.max((mean_r.inv() * rotations).magnitude())
        if np.max(np.linalg.norm(positions - np.median(positions, axis=0), axis=1)) > .002 or spread > np.deg2rad(3):
            raise ValueError('Tip pose unstable (>2 mm or >3 degrees); improve marker view and hold still')
        result[key] = np.eye(4)
        result[key][:3, 3] = np.median(positions, axis=0)
        result[key][:3, :3] = mean_r.as_matrix()
    return result


def solve_gripper(samples, offsets, forward):
    """Offsets are measured marker-centre -> contact-centre vectors in marker axes."""
    if len(samples) < 5:
        raise ValueError('Need at least five measured openings')
    widths = np.array([s['width_m'] for s in samples])
    if len(np.unique(widths)) < 5 or np.ptp(widths) < .01:
        raise ValueError('Use distinct openings spanning >=10 mm')
    vectors = np.array([s['tips']['14'][:3, 3] - s['tips']['13'][:3, 3] for s in samples])
    # Jaw motion identifies the axis even when stickers have different Y/Z offsets.
    axis = np.polyfit(widths, vectors, 1)[0]
    if not np.isfinite(axis).all() or np.linalg.norm(axis) < .1:
        raise ValueError('Cannot recover the jaw travel axis')
    axis /= np.linalg.norm(axis)
    aperture = fit_aperture(vectors @ axis, [s['width_m'] for s in samples])
    origins, forwards = [], []
    for s in samples:
        tips = s['tips']
        contacts = [tips[k][:3, 3] + tips[k][:3, :3] @ offsets[k] for k in ('13', '14')]
        if np.linalg.norm((contacts[1] - contacts[0]) - s['width_m'] * axis) > .003:
            raise ValueError('Measured contact offsets disagree with jaw opening by >3 mm')
        origins.append(np.mean(contacts, axis=0))
        forwards.append(tips['13'][:3, :3] @ forward)
    origin = np.mean(origins, axis=0)
    if np.max(np.linalg.norm(np.asarray(origins) - origin, axis=1)) > .003:
        raise ValueError('Tool midpoint shifts >3 mm across openings; check offsets, tag poses and mechanism')
    z = np.mean(forwards, axis=0)
    z -= axis * np.dot(z, axis)
    if np.linalg.norm(z) < .1:
        raise ValueError('Tool forward must not be parallel to the jaw axis')
    z /= np.linalg.norm(z)
    y = np.cross(z, axis)
    mat = np.eye(4)
    mat[:3, :3] = np.column_stack([axis, y, z])
    mat[:3, 3] = origin
    return dict(aperture=aperture, jaw_axis_camera=axis.tolist(), T_camera_tool=mat.tolist())


def gripper(args):
    c = load_calibration(args.calibration)
    measurements = load_json(args.measurements)
    offsets = {k: np.asarray(measurements['contact_offsets_marker_mm'][k], float) / 1000 for k in ('13', '14')}
    forward = np.asarray(measurements['tool_forward_marker13'], float)
    if any(v.shape != (3,) or not np.isfinite(v).all() for v in [*offsets.values(), forward]):
        raise ValueError('Offsets and forward must be finite 3-vectors')
    if not np.isclose(np.linalg.norm(forward), 1):
        raise ValueError('tool_forward_marker13 must be a unit vector')
    tracker = Tracker(c)
    samples = []
    with Camera(c['serial'], c['intrinsics']['width'], c['intrinsics']['height'], c['camera']['fps'], c.get('camera_settings')) as camera:
        check_calibration_camera(c, camera.metadata)
        print('Capture at least five different openings, including both endpoints. Blank finishes.')
        while True:
            text = input('Hold jaws still; enter measured inner-tip opening in mm: ').strip()
            if not text:
                break
            width = float(text) / 1000
            if not np.isfinite(width) or width < 0:
                raise ValueError('Opening must be finite and nonnegative')
            samples.append(dict(width_m=width, tips=capture_tip_sample(camera, tracker)))
            print(f'Captured opening {width * 1000:g} mm')
    c.update(solve_gripper(samples, offsets, forward))
    c['gripper_measurements'] = measurements
    c['gripper_samples'] = [dict(width_m=s['width_m'], tips={k: v.tolist() for k, v in s['tips'].items()}) for s in samples]
    save_json(args.output, c)
    print(f'Saved gripper calibration to {args.output}')


def charuco(args):
    c = load_calibration(args.calibration)
    board = cv2.aruco.CharucoBoard((7, 5), .025, .018, DICTIONARY)
    detector = cv2.aruco.CharucoDetector(board)
    all_corners, all_ids = [], []
    with Camera(c['serial'], c['intrinsics']['width'], c['intrinsics']['height'], c['camera']['fps'], c.get('camera_settings')) as camera:
        check_calibration_camera(c, camera.metadata)
        print('Move/tilt board across the image. SPACE saves a view; q solves (at least 15 views).')
        try:
            while True:
                rgb, _, _ = camera.read()
                corners, ids, _, _ = detector.detectBoard(cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY))
                display = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
                if ids is not None:
                    cv2.aruco.drawDetectedCornersCharuco(display, corners, ids)
                cv2.putText(display, f'Views: {len(all_ids)} | SPACE capture | q solve', (10, 25), 0, .6, (0, 255, 0), 1)
                cv2.imshow('tinyumi calibration', display)
                key = cv2.waitKey(1) & 255
                if key == ord('q'):
                    break
                if key == 32 and ids is not None and len(ids) >= 10:
                    all_corners.append(corners.copy())
                    all_ids.append(ids.copy())
        finally:
            cv2.destroyAllWindows()
    if len(all_ids) < 15:
        raise ValueError('Need at least 15 diverse views with >=10 corners each')
    shape = (c['intrinsics']['width'], c['intrinsics']['height'])
    rms, k, d, _, _ = cv2.aruco.calibrateCameraCharuco(all_corners, all_ids, board, shape, None, None)
    if not np.isfinite(rms) or rms > 1:
        raise ValueError(f'Calibration RMS {rms:.3f}px exceeds 1px; improve views')
    c['factory_intrinsics'] = copy.deepcopy(c.get('factory_intrinsics', c['intrinsics']))
    c['intrinsics'].update(fx=float(k[0, 0]), fy=float(k[1, 1]), ppx=float(k[0, 2]), ppy=float(k[1, 2]),
                           coeffs=d.ravel().tolist(), model='brown_conrady')
    c.update(intrinsics_source='charuco', charuco_rms_px=float(rms), T_camera_tool=None, aperture=None, jaw_axis_camera=None)
    c['charuco_observations'] = [dict(corners=p.reshape(-1, 2).tolist(), ids=i.ravel().tolist()) for p, i in zip(all_corners, all_ids)]
    save_json(args.output, c)
    print(f'Saved intrinsics ({rms:.3f}px RMS). Repeat gripper calibration with these intrinsics.')
