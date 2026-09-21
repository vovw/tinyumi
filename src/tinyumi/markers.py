"""ArUco detection, physical print assets, and independently solved frame poses."""

from pathlib import Path

import cv2
import numpy as np

from .config import save_json
from .geometry import camera_matrix, inverse, pose6, transform, undistorted_pixels

DICTIONARY = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)


def board_geometry():
    return {str(20 + row * 4 + col):
            [[col * .04, row * .04, 0], [col * .04 + .03, row * .04, 0],
             [col * .04 + .03, row * .04 + .03, 0], [col * .04, row * .04 + .03, 0]]
            for row in range(3) for col in range(4)}


def make_board(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    objects = board_geometry()
    pieces = ['<svg xmlns="http://www.w3.org/2000/svg" width="210mm" height="297mm" viewBox="0 0 210 297">',
              '<rect width="210" height="297" fill="white"/>',
              '<g fill="black" shape-rendering="crispEdges">']
    for marker_id, corners in objects.items():
        cells = cv2.aruco.generateImageMarker(DICTIONARY, int(marker_id), 6)
        x, y = 30 + corners[0][0] * 1000, 40 + corners[0][1] * 1000
        for row, col in np.argwhere(cells == 0):
            pieces.append(f'<rect x="{x+col*5:g}" y="{y+row*5:g}" width="5" height="5"/>')
    pieces += ['</g><g font-family="sans-serif" font-size="4">',
               '<text x="20" y="20">tinyumi DICT_4X4_50 | IDs 20-31 | 30 mm markers</text>',
               '<text x="20" y="175">Print at 100%. Measure black marker edge = 30 mm.</text>',
               '<text x="20" y="185">World origin: top-left black corner of ID20.</text>',
               '<text x="20" y="195">+X right, +Y down page, +Z into board.</text>',
               '<text x="20" y="235">Check ruler below measures exactly 100 mm.</text></g>',
               '<path d="M30 240v5 M30 242h100 M130 240v5" stroke="black" stroke-width="0.3"/>', '</svg>']
    (output / 'workspace.svg').write_text('\n'.join(pieces))
    save_json(output / 'board.json', dict(schema_version=1, dictionary='DICT_4X4_50',
                                        marker_size_m=.03, corners_m=objects))
    # Physical SVG sizing avoids PDF/printer DPI assumptions.
    charuco = cv2.aruco.CharucoBoard((7, 5), .025, .018, DICTIONARY)
    img = charuco.generateImage((1400, 1000), marginSize=0, borderBits=1)
    import base64
    encoded = base64.b64encode(cv2.imencode('.png', img)[1]).decode()
    (output / 'charuco.svg').write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="210mm" height="297mm" viewBox="0 0 210 297">'
        '<rect width="210" height="297" fill="white"/>'
        f'<image x="17.5" y="30" width="175" height="125" href="data:image/png;base64,{encoded}"/>'
        '<text x="17.5" y="175" font-size="4">ChArUco 7x5 | squares 25 mm | markers 18 mm</text></svg>')


class Tracker:
    def __init__(self, calibration, board=None):
        self.c = calibration
        params = cv2.aruco.DetectorParameters()
        params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
        self.detector = cv2.aruco.ArucoDetector(DICTIONARY, params)
        self.k = camera_matrix(calibration['intrinsics'])
        self.d = np.asarray(calibration['intrinsics']['coeffs'], float)
        self.board = (board or calibration.get('board', {})).get('corners_m', {})

    def detect(self, rgb):
        corners, ids, _ = self.detector.detectMarkers(cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY))
        if ids is None:
            return {}
        # Duplicate physical IDs cannot be disambiguated safely.
        unique, counts = np.unique(ids, return_counts=True)
        good = set(unique[counts == 1])
        return {str(int(i)): p.reshape(4, 2).tolist() for p, i in zip(corners, ids.ravel()) if i in good}

    def solve(self, objects, pixels, min_gap=.1):
        objects, pixels = np.asarray(objects, np.float64), np.asarray(pixels, np.float64)
        distortion = self.d
        if self.c['intrinsics']['model'] == 'inverse_brown_conrady':
            pixels = undistorted_pixels(pixels, self.c['intrinsics'])
            distortion = np.zeros(5)
        result = cv2.solvePnPGeneric(objects, pixels, self.k, distortion, flags=cv2.SOLVEPNP_IPPE)
        candidates = []
        for r, t in zip(result[1], result[2]):
            mat = transform(r, t)
            if np.any((objects @ mat[:3, :3].T + mat[:3, 3])[:, 2] <= 0):
                continue
            projected = cv2.projectPoints(objects, r, t, self.k, distortion)[0].reshape(-1, 2)
            rms = float(np.sqrt(np.mean(np.sum((projected - pixels) ** 2, axis=1))))
            if np.isfinite(rms):
                candidates.append((rms, mat))
        candidates.sort(key=lambda x: x[0])
        if not candidates:
            return None, None
        rms, mat = candidates[0]
        if rms > self.c.get('max_reprojection_px', 1.5):
            return None, rms
        # Fail closed for planar two-solution ambiguity rather than relying on history.
        if len(candidates) > 1 and candidates[1][0] - rms < min_gap:
            return None, rms
        return mat, rms

    def tip_poses(self, tags):
        s = self.c.get('tip_size_m', .009) / 2
        obj = [[-s, -s, 0], [s, -s, 0], [s, s, 0], [-s, s, 0]]
        result = {}
        for key in ('13', '14'):
            if key in tags:
                # Centres remain useful near fronto-parallel; tool calibration checks spread.
                t, _ = self.solve(obj, tags[key], min_gap=0)
                if t is not None:
                    result[key] = t
        return result

    def process(self, rgb):
        tags = self.detect(rgb)
        obj, pix = [], []
        visible = sorted(set(tags) & set(self.board))
        for key in visible:
            obj.extend(self.board[key])
            pix.extend(tags[key])
        board_pose, error = (self.solve(obj, pix) if len(visible) >= 2 else (None, None))
        tips = self.tip_poses(tags)
        width = None
        if len(tips) == 2 and self.c.get('aperture') is not None:
            a = self.c['aperture']
            sep = float((tips['14'][:3, 3] - tips['13'][:3, 3]) @ self.c['jaw_axis_camera'])
            candidate = a['slope'] * sep + a['intercept_m']
            if a['min_m'] - .002 <= candidate <= a['max_m'] + .002:
                width = float(np.clip(candidate, a['min_m'], a['max_m']))
        tool_pose = None
        if board_pose is not None and self.c.get('T_camera_tool') is not None:
            tool_pose = pose6(inverse(board_pose) @ np.asarray(self.c['T_camera_tool'])).tolist()
        return dict(tags=tags, board_ids=visible, reprojection_px=error,
                    tcp_pose=tool_pose, aperture_m=width,
                    pose_valid=tool_pose is not None, aperture_valid=width is not None)
