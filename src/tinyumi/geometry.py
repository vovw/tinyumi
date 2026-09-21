"""T_a_b maps points in frame b into frame a. All distances are metres."""

import numpy as np
from scipy.spatial.transform import Rotation


def transform(rvec, tvec):
    result = np.eye(4)
    result[:3, :3] = Rotation.from_rotvec(np.asarray(rvec).reshape(3)).as_matrix()
    result[:3, 3] = np.asarray(tvec).reshape(3)
    return result


def check_transform(value):
    value = np.asarray(value, dtype=float)
    if value.shape != (4, 4) or not np.isfinite(value).all():
        raise ValueError("Expected a finite 4x4 rigid transform")
    r = value[:3, :3]
    if not (np.allclose(value[3], [0, 0, 0, 1]) and
            np.allclose(r.T @ r, np.eye(3), atol=1e-5) and
            np.isclose(np.linalg.det(r), 1, atol=1e-5)):
        raise ValueError("Transform must be right-handed and orthonormal")
    return value


def inverse(value):
    value = check_transform(value)
    result = np.eye(4)
    result[:3, :3] = value[:3, :3].T
    result[:3, 3] = -result[:3, :3] @ value[:3, 3]
    return result


def pose6(value):
    value = check_transform(value)
    return np.r_[value[:3, 3], Rotation.from_matrix(value[:3, :3]).as_rotvec()]


def camera_matrix(intrinsics):
    return np.array([[intrinsics['fx'], 0, intrinsics['ppx']],
                     [0, intrinsics['fy'], intrinsics['ppy']], [0, 0, 1.]], float)


def realsense_intrinsics(i):
    import pyrealsense2 as rs
    result = rs.intrinsics()
    for key in ('width', 'height', 'fx', 'fy', 'ppx', 'ppy', 'coeffs'):
        setattr(result, key, i[key])
    result.model = getattr(rs.distortion, i['model'])
    return result


def undistorted_pixels(pixels, intrinsics):
    """Use SDK deprojection for its inverse model, never OpenCV forward coefficients."""
    import pyrealsense2 as rs
    i = realsense_intrinsics(intrinsics)
    rays = np.array([rs.rs2_deproject_pixel_to_point(i, list(map(float, p)), 1.) for p in pixels])
    return rays[:, :2] * [i.fx, i.fy] + [i.ppx, i.ppy]


def project_camera_points(points, intrinsics):
    """Projection for overlays, numerically inverting SDK deprojection if necessary."""
    import cv2
    k = camera_matrix(intrinsics)
    points = np.asarray(points)
    if intrinsics['model'] != 'inverse_brown_conrady':
        return cv2.projectPoints(points, np.zeros(3), np.zeros(3), k,
                                 np.asarray(intrinsics['coeffs']))[0].reshape(-1, 2)
    from scipy.optimize import least_squares
    target = points[:, :2] / points[:, 2:] * [k[0, 0], k[1, 1]] + k[:2, 2]
    def residual(flat):
        return (undistorted_pixels(flat.reshape(-1, 2), intrinsics) - target).ravel()
    return least_squares(residual, target.ravel(), diff_step=1e-3).x.reshape(-1, 2)


def fit_aperture(separations, widths):
    x, y = np.asarray(separations, float), np.asarray(widths, float)
    if (len(x) < 5 or x.shape != y.shape or not np.isfinite([x, y]).all()
            or len(np.unique(y)) < 5 or np.ptp(x) < .01 or np.any(y < 0)):
        raise ValueError("Use at least five distinct measured openings spanning >=10 mm")
    slope, intercept = np.polyfit(x, y, 1)
    residual = slope * x + intercept - y
    if not .5 <= slope <= 1.5 or np.max(np.abs(residual)) > .002:
        raise ValueError("Aperture calibration failed: scale or >2 mm residual")
    return dict(slope=float(slope), intercept_m=float(intercept),
                min_m=float(y.min()), max_m=float(y.max()),
                max_error_m=float(np.abs(residual).max()))
