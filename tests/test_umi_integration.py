"""Optional test against an unmodified pinned UMI checkout and its dependencies.

UMI_SOURCE=/path/to/umi python -m pytest tests/test_umi_integration.py -q
Run in an environment containing tinyumi[export,test], CPU torch, imagecodecs,
threadpoolctl, tqdm, filelock and dill. Capture does not need these extras.
"""

import os
from pathlib import Path
import subprocess
import sys

import pytest

from tinyumi.export import UMI_REVISION, export_umi


@pytest.mark.skipif(not os.environ.get('UMI_SOURCE'), reason='Set UMI_SOURCE to test the upstream loader')
def test_actual_umi_training_batch(episode_factory, tmp_path):
    source = Path(os.environ['UMI_SOURCE']).resolve()
    revision = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    assert revision == UMI_REVISION
    sys.path.insert(0, str(source))
    from diffusion_policy.dataset.umi_dataset import UmiDataset
    from torch.utils.data import DataLoader
    output = tmp_path / 'umi.zarr.zip'
    export_umi([episode_factory(n=24), episode_factory(n=24)], output)
    shape = {'obs': {}, 'action': dict(shape=[10], horizon=16, latency_steps=0, down_sample_steps=1, rotation_rep='rotation_6d')}
    for key, dims, kind in [('camera0_rgb', [3, 224, 224], 'rgb'), ('robot0_eef_pos', [3], 'low_dim'),
                            ('robot0_eef_rot_axis_angle', [6], 'low_dim'), ('robot0_gripper_width', [1], 'low_dim')]:
        shape['obs'][key] = dict(shape=dims, type=kind, horizon=2, latency_steps=0, down_sample_steps=1)
    dataset = UmiDataset(shape_meta=shape, dataset_path=str(output),
                         pose_repr=dict(obs_pose_repr='relative', action_pose_repr='relative'), val_ratio=0.)
    assert len(dataset) > 0
    batch = next(iter(DataLoader(dataset, batch_size=2, num_workers=0)))
    assert tuple(batch['obs']['camera0_rgb'].shape) == (2, 2, 3, 224, 224)
    assert tuple(batch['action'].shape) == (2, 16, 10)
