import argparse
import json
import os
import sys
import time
from pathlib import Path

import cv2
import numpy as np

from . import calibration
from .camera import Camera, check_calibration_camera, doctor
from .config import load_calibration, require_complete
from .episodes import EpisodeWriter, read_frames, validate_episode
from .geometry import project_camera_points
from .markers import Tracker, make_board


def show(rgb, depth, tracking, label, tracker=None, fps=None):
    display = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    for key, corners in tracking['tags'].items():
        points = np.asarray(corners, np.int32)
        cv2.polylines(display, [points], True, (0, 255, 0), 1)
        cv2.putText(display, key, tuple(points[0]), 0, .5, (0, 255, 0), 1)
    if tracker is not None and tracking['pose_valid']:
        # Fixed camera->tool frame shows TCP orientation in the wrist image.
        mat = np.asarray(tracker.c['T_camera_tool'])
        axes = np.array([[0, 0, 0], [.025, 0, 0], [0, .025, 0], [0, 0, .025]])
        points = axes @ mat[:3, :3].T + mat[:3, 3]
        if np.all(points[:, 2] > 0):
            pixels = project_camera_points(points, tracker.c['intrinsics']).round().astype(int)
            for end, color in zip(pixels[1:], [(0, 0, 255), (0, 255, 0), (255, 0, 0)]):
                cv2.line(display, tuple(pixels[0]), tuple(end), color, 2)
    width = tracking['aperture_m']
    line = f"pose={'OK' if tracking['pose_valid'] else 'MISSING'} opening={width*1000:.1f}mm" if width is not None else f"pose={'OK' if tracking['pose_valid'] else 'MISSING'} opening=MISSING"
    for i, text in enumerate([label, line, f'board tags={len(tracking["board_ids"])} fps={fps:.1f}' if fps else '']):
        cv2.putText(display, text, (8, 22+i*22), 0, .5, (0, 255, 255), 1)
    depth_view = cv2.applyColorMap(cv2.convertScaleAbs(depth, alpha=.03), cv2.COLORMAP_TURBO)
    cv2.imshow('tinyumi RGB | raw depth (not aligned)', np.hstack([display, depth_view]))
    return cv2.waitKey(1) & 255


def capture(args):
    cv2.setNumThreads(1)
    c = load_calibration(args.calibration)
    recording = args.command == 'record'
    if recording:
        require_complete(c)
    if not np.isfinite(args.seconds) or args.seconds < 0:
        raise ValueError('--seconds must be finite and nonnegative')
    if args.headless and args.seconds <= 0:
        raise ValueError('--headless requires --seconds > 0')
    tracker = Tracker(c)
    writer = None
    try:
        with Camera(c['serial'], c['intrinsics']['width'], c['intrinsics']['height'], c['camera']['fps'], c.get('camera_settings')) as camera:
            check_calibration_camera(c, camera.metadata)
            if args.headless and recording:
                writer = EpisodeWriter(args.output, c, camera.metadata, args.task)
                camera.flush()
            started = last = time.monotonic()
            while True:
                rgb, depth, metadata = camera.read()
                tracking = tracker.process(rgb)
                now = time.monotonic()
                fps = 1 / max(now-last, 1e-6)
                last = now
                if writer:
                    writer.submit(rgb, depth, dict(**metadata, tracking=tracking))
                key = -1 if args.headless else show(rgb, depth, tracking,
                    ('RECORDING' if writer else 'PREVIEW') + ' | r start | s stop | d discard | q quit', tracker, fps)
                if key == ord('r') and recording and writer is None:
                    writer = EpisodeWriter(args.output, c, camera.metadata, args.task)
                    camera.flush()
                    print(f'Recording {writer.path}')
                if key in (ord('s'), ord('d')) and writer:
                    path = writer.finish('discarded' if key == ord('d') else 'complete')
                    writer = None
                    print(json.dumps(validate_episode(path), indent=2))
                if key == ord('q'):
                    break
                if args.seconds > 0 and now - started >= args.seconds:
                    if writer:
                        path = writer.finish()
                        writer = None
                        print(json.dumps(validate_episode(path), indent=2))
                    break
    finally:
        if writer:
            path = writer.finish('incomplete', 'capture_interrupted_before_stop')
            print(f'Preserved incomplete recording: {path}')
        if not args.headless:
            cv2.destroyAllWindows()


def replay(args):
    rows = read_frames(args.episode)
    c = load_calibration(Path(args.episode) / 'calibration.json')
    tracker = Tracker(c)
    try:
        for row in rows:
            name = f'{row["index"]:06d}.png'
            bgr = cv2.imread(str(Path(args.episode) / 'rgb' / name))
            depth = cv2.imread(str(Path(args.episode) / 'depth' / name), cv2.IMREAD_UNCHANGED)
            if bgr is None or depth is None:
                raise ValueError(f'Missing frame {name}')
            if show(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB), depth, row['tracking'], f'Frame {row["index"]}', tracker) == ord('q'):
                break
            time.sleep(1 / c['camera']['fps'])
    finally:
        cv2.destroyAllWindows()


def main(argv=None):
    parser = argparse.ArgumentParser(description='D405 tabletop demonstration capture')
    subs = parser.add_subparsers(dest='command', required=True)
    subs.add_parser('doctor', help='Report USB access, devices and stream profiles')
    board = subs.add_parser('make-board', help='Create physical-size workspace/ChArUco SVGs')
    board.add_argument('output')
    cal = subs.add_parser('calibrate')
    cals = cal.add_subparsers(dest='calibration_command', required=True)
    init = cals.add_parser('init', help='Read factory intrinsics and bind workspace board')
    init.add_argument('--board', required=True)
    init.add_argument('--output', required=True)
    init.add_argument('--serial')
    init.add_argument('--width', type=int, default=640)
    init.add_argument('--height', type=int, default=480)
    init.add_argument('--fps', type=int, default=30)
    init.add_argument('--tip-mm', type=float, default=9)
    init.add_argument('--exposure-us', type=float, help='Manual stereo-sensor exposure; saved and reapplied each session')
    init.add_argument('--gain', type=float, help='Stereo-sensor gain; use with manual exposure')
    init.set_defaults(handler=calibration.initialize)
    for name, handler in [('charuco', calibration.charuco), ('gripper', calibration.gripper)]:
        p = cals.add_parser(name)
        p.add_argument('--calibration', required=True)
        p.add_argument('--output', required=True)
        p.set_defaults(handler=handler)
        if name == 'gripper':
            p.add_argument('--measurements', required=True)
    for name in ('preview', 'record'):
        p = subs.add_parser(name)
        p.add_argument('--calibration', required=True)
        p.add_argument('--headless', action='store_true')
        p.add_argument('--seconds', type=float, default=0)
        if name == 'record':
            p.add_argument('--output', default='data/episodes')
            p.add_argument('--task', default='')
    p = subs.add_parser('validate')
    p.add_argument('episodes', nargs='+')
    p = subs.add_parser('replay')
    p.add_argument('episode')
    p = subs.add_parser('export-umi')
    p.add_argument('episodes', nargs='+')
    p.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    try:
        # OpenCV GUI can abort the interpreter, bypassing finally, without a display.
        needs_gui = (args.command in ('preview', 'record') and not args.headless) or args.command == 'replay' or (
            args.command == 'calibrate' and args.calibration_command == 'charuco')
        if needs_gui and not (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')):
            raise ValueError('No desktop display. Use --headless --seconds N or run from a desktop terminal.')
        if args.command == 'doctor':
            result = doctor()
            print(json.dumps(result, indent=2))
            return 0 if result['status'] == 'ready' else 1
        if args.command == 'make-board':
            make_board(args.output)
        elif args.command == 'calibrate':
            if Path(args.output).exists():
                raise FileExistsError('Choose a new calibration output path; existing calibration is preserved')
            args.handler(args)
        elif args.command in ('preview', 'record'):
            capture(args)
        elif args.command == 'replay':
            replay(args)
        elif args.command == 'validate':
            results = [validate_episode(p) for p in args.episodes]
            print(json.dumps(results, indent=2))
            return 0 if all(r['accepted'] for r in results) else 1
        elif args.command == 'export-umi':
            from .export import export_umi
            print(json.dumps(export_umi(args.episodes, args.output), indent=2))
        return 0
    except (ValueError, RuntimeError, OSError, ImportError, KeyError, cv2.error) as exc:
        print(f'tinyumi: {exc}', file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print('Stopped; active recording preserved as incomplete.', file=sys.stderr)
        return 130


if __name__ == '__main__':
    raise SystemExit(main())
