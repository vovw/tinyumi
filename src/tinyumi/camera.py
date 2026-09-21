"""RealSense access is lazy so offline tools work without USB or the SDK."""

import importlib.metadata
import platform
import time

import numpy as np


def intrinsics(profile):
    i = profile.as_video_stream_profile().get_intrinsics()
    return dict(width=i.width, height=i.height, fx=i.fx, fy=i.fy,
                ppx=i.ppx, ppy=i.ppy, model=str(i.model).split('.')[-1], coeffs=list(i.coeffs))


def doctor():
    report = dict(platform=platform.platform(), devices=[], status='unavailable')
    for package in ('pyrealsense2', 'opencv-contrib-python', 'numpy'):
        try:
            report[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            report[package] = 'not installed'
    try:
        import pyrealsense2 as rs
        context = rs.context()
        for d in context.query_devices():
            device = {}
            for label in ('name', 'serial_number', 'firmware_version', 'usb_type_descriptor'):
                key = getattr(rs.camera_info, label)
                device[label] = d.get_info(key) if d.supports(key) else None
            device['profiles'] = [str(p) for s in d.query_sensors() for p in s.get_stream_profiles()]
            report['devices'].append(device)
        report['status'] = 'ready' if report['devices'] else 'no_devices_visible'
    except (ImportError, RuntimeError) as exc:
        report['error'] = str(exc)
    return report


class Camera:
    def __init__(self, serial=None, width=640, height=480, fps=30, settings=None):
        self.serial, self.width, self.height, self.fps = serial, width, height, fps
        self.settings = settings or {}

    def __enter__(self):
        import pyrealsense2 as rs
        self.rs = rs
        self.context = rs.context()
        devices = [d for d in self.context.query_devices()
                   if 'D405' in d.get_info(rs.camera_info.name)]
        if self.serial:
            devices = [d for d in devices if d.get_info(rs.camera_info.serial_number) == self.serial]
        if len(devices) != 1:
            raise RuntimeError(f'Expected one D405, found {len(devices)}; run doctor or use --serial')
        self.pipeline = rs.pipeline(self.context)
        self.frames = rs.frame_queue(16, True)
        config = rs.config()
        config.enable_device(devices[0].get_info(rs.camera_info.serial_number))
        config.enable_stream(rs.stream.color, self.width, self.height, rs.format.rgb8, self.fps)
        config.enable_stream(rs.stream.depth, self.width, self.height, rs.format.z16, self.fps)
        try:
            profile = self.pipeline.start(config, self.frames)
            # Apply after streaming starts; D405 color and depth share the stereo sensor.
            sensor = profile.get_device().first_depth_sensor()
            if self.settings.get('exposure_us') is not None:
                exposure = float(self.settings['exposure_us'])
                allowed = sensor.get_option_range(rs.option.exposure)
                if not np.isfinite(exposure) or not allowed.min <= exposure <= allowed.max:
                    raise ValueError(f'Exposure must be within {allowed.min}..{allowed.max} microseconds')
                sensor.set_option(rs.option.enable_auto_exposure, 0)
                sensor.set_option(rs.option.exposure, exposure)
            if self.settings.get('gain') is not None:
                gain = float(self.settings['gain'])
                allowed = sensor.get_option_range(rs.option.gain)
                if not np.isfinite(gain) or not allowed.min <= gain <= allowed.max:
                    raise ValueError(f'Gain must be within {allowed.min}..{allowed.max}')
                sensor.set_option(rs.option.gain, gain)
            color, depth = profile.get_stream(rs.stream.color), profile.get_stream(rs.stream.depth)
            ext = depth.get_extrinsics_to(color)
            self.metadata = dict(
                serial=profile.get_device().get_info(rs.camera_info.serial_number),
                firmware=profile.get_device().get_info(rs.camera_info.firmware_version),
                fps=self.fps, intrinsics=intrinsics(color), depth_intrinsics=intrinsics(depth),
                depth_scale_m=profile.get_device().first_depth_sensor().get_depth_scale(),
                depth_to_color=dict(rotation_column_major=list(ext.rotation), translation_m=list(ext.translation)),
                sdk_version=importlib.metadata.version('pyrealsense2'), depth_aligned=False)
            # Exposure settles before a user can begin an episode.
            for _ in range(15):
                self.frames.wait_for_frame(5000)
            self.metadata['sensor_options'] = []
            for sensor in profile.get_device().query_sensors():
                options = {}
                for key in (rs.option.exposure, rs.option.gain, rs.option.enable_auto_exposure):
                    if sensor.supports(key):
                        options[str(key)] = sensor.get_option(key)
                self.metadata['sensor_options'].append(dict(name=sensor.get_info(rs.camera_info.name), options=options))
            return self
        except Exception:
            try:
                self.pipeline.stop()
            except RuntimeError:
                pass
            raise

    def read(self):
        frames = self.frames.wait_for_frame(5000).as_frameset()
        host = time.monotonic_ns()
        color, depth = frames.get_color_frame(), frames.get_depth_frame()
        if not color or not depth:
            raise RuntimeError('Missing color or depth frame')
        stamps = {}
        for name, frame in (('color', color), ('depth', depth)):
            stamps[name] = dict(frame_number=frame.get_frame_number(), timestamp_ms=frame.get_timestamp(),
                                clock_domain=str(frame.get_frame_timestamp_domain()))
            for label in ('actual_exposure', 'gain_level'):
                field = getattr(self.rs.frame_metadata_value, label)
                if frame.supports_frame_metadata(field):
                    stamps[name][label] = frame.get_frame_metadata(field)
        metadata = dict(host_monotonic_ns=host, **stamps)
        return np.asanyarray(color.get_data()).copy(), np.asanyarray(depth.get_data()).copy(), metadata

    def flush(self):
        """Discard preview/idle backlog before establishing a new episode boundary."""
        while self.frames.poll_for_frame():
            pass

    def __exit__(self, *args):
        self.pipeline.stop()


def check_calibration_camera(calibration, metadata):
    if calibration['serial'] != metadata['serial']:
        raise ValueError('Calibration belongs to a different camera serial')
    ci, mi = calibration['intrinsics'], metadata['intrinsics']
    if (ci['width'], ci['height']) != (mi['width'], mi['height']):
        raise ValueError('Calibration resolution does not match the active color stream')
    if calibration['camera']['fps'] != metadata['fps']:
        raise ValueError('Calibration frame rate does not match the active stream')
