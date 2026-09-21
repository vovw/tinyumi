import cv2
import numpy as np
import pytest

from tinyumi.calibration import solve_gripper
from tinyumi.geometry import fit_aperture, inverse, pose6, transform
from tinyumi.markers import DICTIONARY, Tracker, make_board


def test_transforms_and_metric_scale():
    t = transform([.2, -.3, .4], [.1, .2, .3])
    np.testing.assert_allclose(inverse(t) @ t, np.eye(4), atol=1e-12)
    np.testing.assert_allclose(pose6(t), [.1, .2, .3, .2, -.3, .4])
    with pytest.raises(ValueError):
        inverse(np.zeros((4, 4)))


def test_detection_and_occlusion(calibration):
    rgb = np.full((480, 640, 3), 255, np.uint8)
    for i, x in [(13, 40), (14, 220)]:
        m = cv2.aruco.generateImageMarker(DICTIONARY, i, 120)
        rgb[80:200, x:x+120] = m[:, :, None]
    tracker = Tracker(calibration)
    assert set(tracker.detect(rgb)) == {'13', '14'}
    result = tracker.process(np.full_like(rgb, 255))
    assert result['tcp_pose'] is None and result['aperture_m'] is None


def test_board_pose_and_outliers(calibration):
    tracker = Tracker(calibration)
    obj = np.concatenate(list(tracker.board.values()))
    r, t = np.array([.3, -.15, .05]), np.array([-.06, -.04, .35])
    pix = cv2.projectPoints(obj, r, t, tracker.k, tracker.d)[0].reshape(-1, 2)
    pose, err = tracker.solve(obj, pix)
    assert err < 1e-5
    np.testing.assert_allclose(pose, transform(r, t), atol=1e-5)
    pix[0] += 25
    assert tracker.solve(obj, pix)[0] is None


def test_ambiguous_planar_pose_rejected(calibration):
    tracker = Tracker(calibration)
    obj = np.array([[-.03, -.03, 0], [.03, -.03, 0], [.03, .03, 0], [-.03, .03, 0]])
    pix = cv2.projectPoints(obj, np.zeros(3), np.array([0., 0., .4]), tracker.k, tracker.d)[0].reshape(-1, 2)
    assert tracker.solve(obj, pix)[0] is None


def test_aperture_and_gripper_calibration():
    widths = np.linspace(0, .08, 5)
    a = fit_aperture(widths + .01, widths)
    assert a['slope'] == pytest.approx(1)
    assert a['intercept_m'] == pytest.approx(-.01)
    samples = []
    for width in widths:
        tips = {k: transform([0, 0, 0], [s * (width+.01)/2, 0, .15]) for k, s in [('13', -1), ('14', 1)]}
        samples.append(dict(width_m=width, tips=tips))
    c = solve_gripper(samples, {'13': np.array([.005, 0, 0]), '14': np.array([-.005, 0, 0])}, np.array([0, 1, 0]))
    np.testing.assert_allclose(np.array(c['T_camera_tool'])[:3, 3], [0, 0, .15])
    assert np.linalg.det(np.array(c['T_camera_tool'])[:3, :3]) == pytest.approx(1)
    with pytest.raises(ValueError):
        fit_aperture([0, 1], [0, 1])
    with pytest.raises(ValueError):
        fit_aperture(widths+.01, widths * 3)


def test_make_board(tmp_path):
    make_board(tmp_path / 'boards')
    svg = (tmp_path / 'boards/workspace.svg').read_text()
    assert 'width="210mm"' in svg and 'height="297mm"' in svg
    assert (tmp_path / 'boards/charuco.svg').exists()
    import xml.etree.ElementTree as ET
    page = np.full((2970, 2100, 3), 255, np.uint8)
    root = ET.fromstring(svg)
    for rect in root.findall('{http://www.w3.org/2000/svg}g/{http://www.w3.org/2000/svg}rect'):
        x, y, w, h = [round(float(rect.attrib[k])*10) for k in ('x', 'y', 'width', 'height')]
        page[y:y+h, x:x+w] = 0
    detector = cv2.aruco.ArucoDetector(DICTIONARY)
    _, ids, _ = detector.detectMarkers(page)
    assert set(ids.ravel()) == set(range(20, 32))


def test_inverse_brown_roundtrip_and_pose(calibration):
    from tinyumi.geometry import project_camera_points
    calibration['intrinsics'].update(model='inverse_brown_conrady', coeffs=[-.054, .0625, -.000084, .000289, -.0212])
    tracker = Tracker(calibration)
    obj = np.concatenate(list(tracker.board.values()))
    known = transform([.3, -.15, .05], [-.06, -.04, .35])
    points = obj @ known[:3, :3].T + known[:3, 3]
    pixels = project_camera_points(points, calibration['intrinsics'])
    recovered, rms = tracker.solve(obj, pixels)
    assert rms < .01
    np.testing.assert_allclose(recovered, known, atol=1e-4)


def test_jaw_axis_uses_motion_not_sticker_alignment():
    samples = []
    offsets = {'13': np.array([.005, -.003, .002]), '14': np.array([-.005, .004, -.002])}
    for width in np.linspace(0, .08, 5):
        tips = {key: transform([0, 0, 0], np.array([sign*width/2, 0, .15]) - offsets[key])
                for key, sign in [('13', -1), ('14', 1)]}
        samples.append(dict(width_m=width, tips=tips))
    result = solve_gripper(samples, offsets, np.array([0, 1, 0]))
    np.testing.assert_allclose(result['jaw_axis_camera'], [1, 0, 0], atol=1e-12)
    with pytest.raises(ValueError, match='offsets'):
        solve_gripper(samples, {k: np.zeros(3) for k in offsets}, np.array([0, 1, 0]))
