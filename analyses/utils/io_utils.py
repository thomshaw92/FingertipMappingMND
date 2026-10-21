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
import nilearn.surface
import gzip
import shutil
import numpy as np

logger = logging.getLogger(__name__)


def _split_extension(path):
    """
    Split a file name into its base name and full extension.

    Unlike ``Path.stem``/``Path.suffix``, everything from the first dot
    of the file name counts as the extension, so compound extensions are
    kept together, e.g. ``test.surf.gii`` -> ``('test', '.surf.gii')``
    and ``img.nii.gz`` -> ``('img', '.nii.gz')``. File names must
    therefore not contain dots other than in the extension.

    Parameters
    ----------
    path : path-like
        Path to the file.

    Returns
    -------
    base : str
        File name without the extension (and without the parent folder).
    extension : str
        Full extension including the leading dot, ``''`` if none.
    """
    name = Path(path).name
    extension = ''.join(Path(name).suffixes)
    return name[:len(name) - len(extension)], extension


def _get_sidecar_json(path):
    """
    Return the path of the JSON sidecar belonging to ``path``.

    The sidecar sits next to the file and shares its name up to the
    first extension, e.g. ``img.nii.gz`` -> ``img.json`` and
    ``surf.func.gii`` -> ``surf.json``.

    Parameters
    ----------
    path : path-like
        Path to the data file.

    Returns
    -------
    Path
        Path to the JSON sidecar.
    """
    path = Path(path)
    no_ext = path.parent / path.stem.replace('.nii', '')
    json_filename = no_ext.with_suffix('.json')

    return json_filename


class PathEncoder(json.JSONEncoder):
    """
    JSON encoder that writes ``pathlib.Path`` objects as strings.
    """
    def default(self, obj):
        if isinstance(obj, Path):
            return str(obj)
        return super().default(obj)


def load_sidecar(path, errors='raise'):
    """
    Load the JSON sidecar of ``path``.

    Parameters
    ----------
    path : path-like
        Path to the data file (not to the sidecar itself).
    errors : {'raise', 'warn', 'ignore'}, optional
        What to do if the sidecar does not exist: raise a
        ``FileNotFoundError``, log a warning, or do nothing. Default is
        ``'raise'``.

    Returns
    -------
    dict or None
        Sidecar contents, or ``None`` if it does not exist and
        ``errors`` is not ``'raise'``.
    """
    json_filename = _get_sidecar_json(path)
    if not json_filename.exists():
        msg = f'JSON sidecar {json_filename} not found for {path}.'
        if errors == 'raise':
            raise FileNotFoundError(msg)
        elif errors == 'warn':
            logger.warning(msg)
        return None
    with open(json_filename, 'r') as json_sidecar:
        return json.load(json_sidecar)


def save_sidecar(path, meta):
    """
    Save ``meta`` as the JSON sidecar of ``path``.

    Parameters
    ----------
    path : path-like
        Path to the data file (not to the sidecar itself).
    meta : dict
        Sidecar contents. ``Path`` objects are written as strings.
    """
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(_get_sidecar_json(path), 'w') as json_sidecar:
        json.dump(meta, json_sidecar, indent=2, cls=PathEncoder)


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
    Context manager that suppresses print output only if verbose is
    False.

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
    Walk a BIDS-like tree and yield only subject (and session) folders.

    Parameters
    ----------
    base_path : path-like
        Root folder to walk.
    sub_prefix : str, optional
        Prefix of subject folders. Default is ``'sub-'``.
    ses_prefix : str or None, optional
        Prefix of session folders. If ``None`` or empty, subject folders
        are yielded instead of session folders and ``ses`` is ``None``.
        Default is ``'ses-'``.

    Yields
    ------
    sub : str
        Subject folder name.
    ses : str or None
        Session folder name, or ``None`` if sessions are not used.
    walk_entry : tuple
        ``(root, folders, files)`` as returned by ``os.walk``.

    Raises
    ------
    ValueError
        If ``sub_prefix`` is ``None``.
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


def get_output_path(input_path, suffix, extension=None):
    """
    Derive an output file path by appending a suffix to the input stem.

    Handles compound extensions such as ``.nii.gz`` correctly.

    Parameters
    ----------
    input_path : path-like
        Path to the input file.
    suffix : str
        Suffix to append (after an underscore) before the extension(s).
    extension : str, optional
        Extension of the output file, including the leading dot.
        Defaults to the extension(s) of ``input_path``.

    Returns
    -------
    str
        Output file path.
    """
    input_path = Path(input_path)
    # Handles compound extensions (e.g., .nii.gz, .surf.gii).
    base, full_ext = _split_extension(input_path)
    if extension is not None:
        full_ext = extension
    return f'{input_path.parent}/{base}_{suffix}{full_ext}'


def load_image(img_path, load_img=True, load_meta=True, errors='raise'):
    """
    Load an image and/or its JSON sidecar.

    Parameters
    ----------
    img_path : path-like
        Path to the image.
    load_img : bool, optional
        Whether to load the image. Default is ``True``.
    load_meta : bool, optional
        Whether to load the JSON sidecar. Default is ``True``.
    errors : {'raise', 'warn', 'ignore'}, optional
        What to do if loading fails (including a missing sidecar): raise
        the error, log a warning, or log at info level. Default is
        ``'raise'``.

    Returns
    -------
    img : nib.spatialimages.SpatialImage or None
        Loaded image, ``None`` if not requested or loading failed.
    meta : dict or None
        Sidecar contents, ``None`` if not requested or loading failed.
    """
    img_path = Path(img_path)
    img = None
    meta = None

    try:
        if load_img:
            img = nib.load(img_path)

        if load_meta:
            meta = load_sidecar(img_path, errors='raise')
    except Exception as err:
        if errors == 'raise':
            raise err
        elif errors == 'warn':
            logger.warning(f'Warning when loading {img_path}: {err}')
        else:
            logger.info(f'Error loading {img_path}: {err}')

    return img, meta


def load_contrasts_img(img_path, errors='raise', labels_key='volume_labels'):
    """
    Load a 4D image whose volumes are labelled in its JSON sidecar.

    Parameters
    ----------
    img_path : path-like
        Path to the 4D image.
    errors : {'raise', 'warn', 'ignore'}, optional
        How to handle loading errors, see :func:`load_image`. Default is
        ``'raise'``.
    labels_key : str, optional
        Sidecar key holding the list of volume labels, in volume order.
        Default is ``'volume_labels'``.

    Returns
    -------
    img : nib.Nifti1Image or None
        The 4D image.
    meta : dict or None
        Sidecar contents.
    img_dict : dict
        Mapping of volume label to the 3D volume. Empty if the image or
        sidecar could not be loaded.

    Raises
    ------
    ValueError
        If the image is not 4D.
    """
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
    """
    Save an image together with its JSON sidecar.

    Parameters
    ----------
    img : nib.spatialimages.SpatialImage
        Image to save.
    img_path : path-like
        Output path. The sidecar is written next to it.
    meta : dict, optional
        Sidecar contents. An empty sidecar is written if not given.
    """
    if meta is None:
        meta = {}
    # Create the output folder if needed.
    Path(img_path).parent.mkdir(parents=True, exist_ok=True)

    save_sidecar(img_path, meta)
    nib.save(img, img_path)


def save_figure(fig, fig_path, meta=None, save_empty_sidecar=False, interactive=False):
    """
    Save a figure, and its JSON sidecar if there is metadata.

    Parameters
    ----------
    fig : matplotlib.figure.Figure or nilearn plotly display
        Figure to save.
    fig_path : path-like
        Output path.
    meta : dict, optional
        Sidecar contents.
    save_empty_sidecar : bool, optional
        Write a sidecar even if ``meta`` is empty. Default is ``False``.
    interactive : bool, optional
        If ``True``, ``fig`` is a nilearn plotly display and is saved as
        HTML. Otherwise it is saved as a static image at 200 dpi.
        Default is ``False``.
    """
    if meta is None:
        meta = {}
    # Create the output folder if needed.
    Path(fig_path).parent.mkdir(parents=True, exist_ok=True)

    if interactive:
        fig.figure.write_html(fig_path)
    else:
        fig.savefig(fig_path, dpi=200, bbox_inches='tight')

    if save_empty_sidecar or meta:
        save_sidecar(fig_path, meta)


def save_view(view, view_path, meta=None, save_empty_sidecar=False):
    """
    Save a nilearn interactive view as HTML, and its JSON sidecar if
    there is metadata.

    Parameters
    ----------
    view : nilearn.plotting.html_surface.SurfaceView
        View to save.
    view_path : path-like
        Output path.
    meta : dict, optional
        Sidecar contents.
    save_empty_sidecar : bool, optional
        Write a sidecar even if ``meta`` is empty. Default is ``False``.
    """
    if meta is None:
        meta = {}
    # Create the output folder if needed.
    Path(view_path).parent.mkdir(parents=True, exist_ok=True)

    view.save_as_html(view_path)

    if save_empty_sidecar or meta:
        save_sidecar(view_path, meta)


def _get_surface_paths(path, hemi=None, data_type='mesh'):
    """
    Build the path of a mesh or data file belonging to a surface image.

    The suffixes are inserted before the extension(s), e.g. ``surf.gii``
    with ``data_type='data'`` and ``hemi='L'`` ->
    ``surf_data_hemi-L.gii``.

    Parameters
    ----------
    path : path-like
        Base path of the surface image, as passed to
        :func:`save_surface`.
    hemi : {'L', 'R'} or None, optional
        Hemisphere. If ``None`` no hemisphere suffix is added. Default
        is ``None``.
    data_type : {'mesh', 'data'} or None, optional
        Which part of the surface image. If ``None`` no suffix is added.
        Default is ``'mesh'``.

    Returns
    -------
    Path
        Path to the file.
    """
    path = Path(path)
    base, full_ext = _split_extension(path)

    hemi_suffix = ''
    if hemi is not None:
        hemi_suffix = f'_hemi-{hemi}'

    data_suffix = ''
    if data_type is not None:
        data_suffix = f'_{data_type}'

    surf_path = path.parent / f'{base}{data_suffix}{hemi_suffix}{full_ext}'

    return surf_path


def save_surface(surf_img, path, meta=None):
    """
    Save a surface image as mesh and data GIFTI files plus a JSON
    sidecar.

    nilearn writes one file per hemisphere, so for ``path='surf.gii'``
    the files are ``surf_mesh_hemi-{L,R}.gii``,
    ``surf_data_hemi-{L,R}.gii`` and ``surf.json``. Use
    :func:`load_surface` to read them back.

    Parameters
    ----------
    surf_img : nilearn.surface.SurfaceImage
        Surface image to save.
    path : path-like
        Base output path.
    meta : dict, optional
        Sidecar contents. An empty sidecar is written if not given.
    """
    if meta is None:
        meta = {}
    # Create the output folder if needed.
    Path(path).parent.mkdir(parents=True, exist_ok=True)

    path = Path(path)
    
    mesh_path = _get_surface_paths(path, hemi=None, data_type='mesh')
    surf_img.mesh.to_filename(mesh_path)

    data_path = _get_surface_paths(path, hemi=None, data_type='data')
    surf_img.data.to_filename(data_path)

    save_sidecar(path, meta)


def load_surface(path):
    """
    Load a surface image saved with :func:`save_surface`.

    Parameters
    ----------
    path : path-like
        Base path the surface image was saved with.

    Returns
    -------
    surf_image : nilearn.surface.SurfaceImage
        The surface image.
    meta : dict
        Sidecar contents, empty (with a warning) if there is no sidecar.
    """
    path = Path(path)

    mesh = {
        'left': _get_surface_paths(path, hemi='L', data_type='mesh'),
        'right': _get_surface_paths(path, hemi='R', data_type='mesh')
    }

    data = {
        'left': _get_surface_paths(path, hemi='L', data_type='data'),
        'right': _get_surface_paths(path, hemi='R', data_type='data')
    }

    surf_image = nilearn.surface.SurfaceImage(mesh=mesh, data=data)

    meta = load_sidecar(path, errors='warn') or {}

    return surf_image, meta


def save_gifti(data, path, meta=None):
    """
    Save a single-hemisphere data array as a GIFTI file plus a JSON
    sidecar.

    Parameters
    ----------
    data : np.ndarray
        Per-vertex values. Saved as float32.
    path : path-like
        Output path.
    meta : dict, optional
        Sidecar contents. An empty sidecar is written if not given.
    """
    if meta is None:
        meta = {}
    # Create the output folder if needed.
    Path(path).parent.mkdir(parents=True, exist_ok=True)

    darray = nib.gifti.GiftiDataArray(
        data.astype(np.float32),
        intent=nib.nifti1.intent_codes['NIFTI_INTENT_NONE'],
    )

    nib.gifti.GiftiImage(darrays=[darray]).to_filename(path)

    save_sidecar(path, meta)


def convert_to_sec(t):
    """
    Convert an ``HH:MM:SS`` duration (e.g. from ``sacct``) to seconds.

    Parameters
    ----------
    t : str
        Duration as ``HH:MM:SS``; seconds may be fractional.

    Returns
    -------
    float
        Duration in seconds.
    """
    h, m, s = t.split(':')
    dur = float(s) + (float(m)*60) + (float(h)*60*60)
    return dur


def convert_to_min(t):
    """
    Convert an ``HH:MM:SS`` duration (e.g. from ``sacct``) to minutes.

    Parameters
    ----------
    t : str
        Duration as ``HH:MM:SS``; seconds may be fractional.

    Returns
    -------
    float
        Duration in minutes.
    """
    h, m, s = t.split(':')
    dur = (float(s)/60) + float(m) + (float(h)*60)
    return dur


def job_info(job_id, out_format='JobID,JobName,State'):
    """
    Get information about a SLURM job of the current user from
    ``sacct``.

    Parameters
    ----------
    job_id : str
        SLURM job ID (array jobs included).
    out_format : str, optional
        Comma-separated ``sacct --format`` fields. Default is
        ``'JobID,JobName,State'``.

    Returns
    -------
    pd.DataFrame
        One row per job step with the requested fields and an
        ``array_index`` column. If ``Elapsed`` is requested,
        ``<col>_sec`` and ``<col>_min`` columns are added.
    """
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


def unpack_gifti(sphere_path, output_path='/tmp/fsaverage_sphere.surf.gii'):
    """
    Decompress a gzipped GIFTI file (e.g. an fsaverage sphere from
    nilearn).

    Parameters
    ----------
    sphere_path : path-like
        Path to the ``.gii.gz`` file.
    output_path : path-like, optional
        Where to write the uncompressed file. Default is
        ``'/tmp/fsaverage_sphere.surf.gii'``.

    Returns
    -------
    path-like
        ``output_path``.
    """
    with gzip.open(sphere_path, 'rb') as f_in:
        with open(output_path, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)
    return output_path