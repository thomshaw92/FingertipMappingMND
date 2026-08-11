import os
import sys
import subprocess
import pandas as pd
import warnings
import json
from pathlib import Path
from contextlib import contextmanager
import logging
import nibabel as nib
import nilearn

logger = logging.getLogger(__name__)


def _get_sidecar_json(path):
    path = Path(path)
    no_ext = path.parent / path.stem.replace('.nii', '')
    json_filename = no_ext.with_suffix('.json')

    return json_filename


class PathEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Path):
            return str(obj)
        return super().default(obj)
    

@contextmanager
def silent_print():
    """
    Context manager to temporarily suppress print output.
    
    Usage:
        with silent_print():
            print('This will not appear')
        print('This will appear')
    """
    old_stdout = sys.stdout
    sys.stdout = open(os.devnull, 'w')
    try:
        yield
    finally:
        sys.stdout.close()
        sys.stdout = old_stdout


@contextmanager
def optional_silent_print(verbose):
    """
    Context manager that suppresses print output only if verbose is False.
    
    Usage:
        with optional_silent_print(verbose=False):
            print('This will not appear')
    """
    if verbose:
        yield
    else:
        with silent_print():
            yield


def walk_bids_folders(base_path, sub_prefix='sub-', ses_prefix='ses-'):
    """
    Walk through folders but only include session folders.
    """
    # If prefix is None make sure that any string gets matched.
    if sub_prefix is None:
        raise ValueError('Argument `sub_prefix` cannot be None.')
    if ses_prefix is None:
        ses_prefix = ''

    for root, folders, files in os.walk(base_path):
        if sub_prefix in root and ses_prefix in root:
            parts = root.split('/')
            if ses_prefix and sub_prefix:
                sub = parts[-2]
                ses = parts[-1]
                # Make sure to skip any folders within subject/session
                # folders.
                if ses_prefix not in parts[-1] or sub_prefix not in parts[-2]:
                    continue
            else:
                sub = parts[-1]
                ses = None
                # Make sure to skip any folders within subject/session
                # folders.
                if sub_prefix not in parts[-1]:
                    continue
                
            yield sub, ses, (root, folders, files)


def load_image(img_path, load_img=True, load_meta=True, errors='raise'):
    img_path = Path(img_path)
    img = None
    meta = None

    try:
        if load_img:
            img = nib.load(img_path)

        if load_meta:
            json_filename = _get_sidecar_json(img_path)
            if not json_filename.exists():
                raise FileNotFoundError(f'JSON sidecar {json_filename} not found for {img_path}.')
            with open(json_filename, 'r') as json_sidecar:
                meta = json.load(json_sidecar)
    except Exception as err:
        if errors == 'raise':
            raise err
        elif errors == 'warn':
            logger.warning(f'Warning when loading {img_path}: {err}')
        else:
            logger.info(f'Error loading {img_path}: {err}')

    return img, meta


def load_contrasts_img(img_path, errors='raise', labels_key='volume_labels'):
    img, meta = load_image(img_path, errors=errors)
    # Skip label extraction and image slicing if meta or img is missing.
    if meta is None or img is None:
        return img, meta, {}

    if img.ndim < 4:
        raise ValueError(f'Expected 4D image for contrasts, but got {img.ndim}D image at {img_path}.')
    
    labels = meta[labels_key]
    
    img_dict = {}
    for lab_idx, lab in enumerate(labels):
        img_dict[lab] = img.slicer[..., lab_idx]

    return img, meta, img_dict


def save_image(img, img_path, meta=None):
    if meta is None:
        meta = {}

    json_filename = _get_sidecar_json(img_path)
    with open(json_filename, 'w') as json_sidecar:
        json.dump(meta, json_sidecar, indent=2, cls=PathEncoder)

    nib.save(img, img_path)


def save_figure(fig, fig_path, meta=None, save_empty_sidecar=False, interactive=False):
    if meta is None:
        meta = {}

    if interactive:
        fig.figure.write_html(fig_path)
    else:
        fig.savefig(fig_path)

    if save_empty_sidecar or meta:
        json_filename = _get_sidecar_json(fig_path)
        with open(json_filename, 'w') as json_sidecar:
            json.dump(meta, json_sidecar, indent=2, cls=PathEncoder)


def save_view(view, view_path, meta=None, save_empty_sidecar=False):
    if meta is None:
        meta = {}

    view.save_as_html(view_path)

    if save_empty_sidecar or meta:
        json_filename = _get_sidecar_json(view_path)
        with open(json_filename, 'w') as json_sidecar:
            json.dump(meta, json_sidecar, indent=2, cls=PathEncoder)


def save_surface(surf_img, path, meta=None):
    if meta is None:
        meta = {}

    path = Path(path)
    full_ext = "".join(path.suffixes)
    
    mesh_path = path.parent / f'{path.stem}_mesh{full_ext}'
    surf_img.mesh.to_filename(mesh_path)

    data_path = path.parent / f'{path.stem}_data{full_ext}'
    surf_img.data.to_filename(data_path)

    json_filename = _get_sidecar_json(path)
    with open(json_filename, 'w') as json_sidecar:
        json.dump(meta, json_sidecar, indent=2, cls=PathEncoder)


def load_surface(path):
    path = Path(path)
    full_ext = "".join(path.suffixes)

    mesh = {
        'left': path.parent / f'{path.stem}_mesh_hemi-L{full_ext}',
        'right': path.parent / f'{path.stem}_mesh_hemi-R{full_ext}'
    }

    data = {
        'left': path.parent / f'{path.stem}_data_hemi-L{full_ext}',
        'right': path.parent / f'{path.stem}_data_hemi-R{full_ext}'
    }

    surf_image = nilearn.surface.SurfaceImage(mesh=mesh, data=data)

    json_filename = _get_sidecar_json(path)
    if not json_filename.exists():
        logger.warning(f'JSON sidecar {json_filename} not found for {path}.')
        meta = {}
    else:
        with open(json_filename, 'r') as json_sidecar:
            meta = json.load(json_sidecar)

    return surf_image, meta


def convert_to_sec(t):
    h, m, s = t.split(':')
    dur = float(s) + (float(m)*60) + (float(h)*60*60)
    return dur


def convert_to_min(t):
    h, m, s = t.split(':')
    dur = (float(s)/60) + float(m) + (float(h)*60)
    return dur


def job_info(job_id, out_format='JobID,JobName,State'):
    result = subprocess.run(["sacct", "--user", os.environ.get('USER'), "-j", job_id, f"--format={out_format}", "-P"], capture_output=True, text=True)
    result = result.stdout.split('\n')
    result = [line.split('|') for line in result if line]
    
    job_data = pd.DataFrame(result[1:], columns=result[0])
    job_data['array_index'] = job_data['JobID'].apply(lambda x: x.split('_')[-1].split('.')[0])

    if 'elapsed' in job_data.columns.str.lower():
        # Make sure it is case-insensitive.
        elapsed_idx = job_data.columns.str.lower().get_loc('elapsed')
        col_name = job_data.columns[elapsed_idx]
        job_data[f'{col_name}_sec'] = job_data[col_name].apply(convert_to_sec)
        job_data[f'{col_name}_min'] = job_data[col_name].apply(convert_to_min)

    return job_data