"""
Private helpers and settings shared by ``volume``, ``surface`` and
``plotting``.

Conventions of the public functions in those modules:
  * Inputs can be in memory (images, surface images, meshes) or paths.
  * The sidecar of the main input is passed as ``meta`` and that of any
    other input ``x`` as ``x_meta``. Sidecars of paths are loaded from
    disk when not given.
  * Results are only saved when ``output_path`` is given.
  * Functions return ``(result, meta)``.
"""
import os
from pathlib import Path

import nibabel as nib
import nilearn.datasets
import nilearn.image
import nilearn.surface
import numpy as np
from nilearn.surface import SurfaceImage

import io_utils
import provenance

# Lmod modules for the external tools (recorded in provenance).
ANTS_MODULE = 'ants/2.6.0'
WB_MODULE = 'connectomeworkbench/1.5.0'


def _select_contrast_img(img, contrast_idx=None):
    """
    Select a 3D contrast volume from a potentially 4D image.

    Parameters
    ----------
    img : nib.Nifti1Image
        Input image, either 3D or 4D.
    contrast_idx : int, optional
        Index of the contrast to select along the 4th dimension.
        Required when ``img`` is 4D.

    Returns
    -------
    nib.Nifti1Image
        3D image corresponding to the selected contrast, or the original
        image if it was already 3D.

    Raises
    ------
    ValueError
        If ``img`` is 4D and ``contrast_idx`` is not provided, or if
        ``img`` is 3D and ``contrast_idx`` is provided.
    """
    if img.ndim == 4:
        if contrast_idx is None:
            get_filename = getattr(img, 'get_filename', lambda: 'unknown')
            filename = get_filename()
            raise ValueError(f'4D image must have `contrast_idx` specified. File: {filename}')
        return img.slicer[..., contrast_idx]
    if contrast_idx is not None:
        get_filename = getattr(img, 'get_filename', lambda: 'unknown')
        filename = get_filename()
        raise ValueError(f'Image is 3D but `contrast_idx` was provided for file: {filename}')
    return img


def _check_input_img(img, meta=None, load_errors='raise'):
    """
    Ensure ``img`` is a NiftiImage, loading from disk if necessary.

    Parameters
    ----------
    img : nib.Nifti1Image or path-like
        Image to check. If not already a NiftiImage, it will be loaded
        via ``io_utils.load_image``.
    meta : dict, optional
        Sidecar of ``img``. Required for in-memory images to keep their
        provenance. If ``img`` is a path and ``meta`` is not given, the
        sidecar is loaded from disk.
    load_errors : {'raise', 'warn'}, optional
        How to handle loading errors. Default is ``'raise'``.

    Returns
    -------
    img : nib.Nifti1Image
        The loaded image.
    inp : tuple
        ``(path, meta)`` describing the input for
        ``provenance.record_step``.
    """
    if not isinstance(img, nib.Nifti1Image):
        path = img
        img, disk_meta = io_utils.load_image(img, errors=load_errors)
        if meta is None:
            meta = disk_meta
        return img, provenance.describe(path, meta)

    return img, provenance.describe(img, meta)


def _check_contrasts_img(img, meta=None, load_errors='raise'):
    """
    Load a 4D image whose volumes are labelled by ``volume_labels`` in
    its sidecar, from memory or from disk.

    Parameters
    ----------
    img : nib.Nifti1Image or path-like
        The 4D image.
    meta : dict, optional
        Its sidecar; must contain ``volume_labels`` for in-memory
        images. Loaded from disk for paths if not given.
    load_errors : {'raise', 'warn'}, optional
        How to handle loading errors. Default is ``'raise'``.

    Returns
    -------
    img_dict : dict
        Mapping of volume label to the 3D volume, in volume order.
    inp : tuple
        ``(path, meta)`` describing the input for
        ``provenance.record_step``.

    Raises
    ------
    ValueError
        If the image is not 4D or its sidecar has no ``volume_labels``.
    """
    img, inp = _check_input_img(img, meta=meta, load_errors=load_errors)
    meta = inp[1] or {}
    if img.ndim != 4:
        raise ValueError(f'Expected a 4D image of contrasts, got a {img.ndim}D image.')
    if 'volume_labels' not in meta:
        raise ValueError('The sidecar of a 4D image of contrasts must contain `volume_labels`.')
    img_dict = {label: img.slicer[..., idx] for idx, label in enumerate(meta['volume_labels'])}
    return img_dict, inp


def _check_input_surface(surf, meta=None):
    """
    Load a surface image from memory or from disk.

    Parameters
    ----------
    surf : SurfaceImage or path-like
        Surface image, or the base path it was saved with
        (``io_utils.save_surface``).
    meta : dict, optional
        Its sidecar. Loaded from disk for paths if not given.

    Returns
    -------
    surf : SurfaceImage
        The surface image.
    inp : tuple
        ``(path, meta)`` describing the input for
        ``provenance.record_step``.
    """
    if isinstance(surf, SurfaceImage):
        return surf, (None, meta)
    surface_image, disk_meta = io_utils.load_surface(surf)
    return surface_image, provenance.describe(surf, meta if meta is not None else disk_meta)


def _check_input_mesh(mesh, meta=None, standard_surface='fsaverage6', verbose=False):
    """
    Get a mesh given as an fsaverage mesh name, a path or in memory.

    Parameters
    ----------
    mesh : str, path-like or nilearn.surface.PolyMesh
        A mesh of the ``standard_surface`` fsaverage (e.g. ``'pial'``),
        the base path of a mesh saved with ``PolyMesh.to_filename`` (as
        ``<name>_hemi-L/R.gii``, a string ending in ``.gii`` or a
        ``Path``), or a mesh in memory.
    meta : dict, optional
        Sidecar of the mesh. Loaded from disk for paths if not given.
    standard_surface : str, optional
        fsaverage resolution for mesh names. Default is
        ``'fsaverage6'``.
    verbose : bool, optional
        If ``False``, suppress nilearn's printed output. Default is
        ``False``.

    Returns
    -------
    mesh : nilearn.surface.PolyMesh
        The mesh.
    name : str or None
        The fsaverage mesh name, ``None`` for other meshes.
    inp : tuple or None
        ``(path, meta)`` describing the input for
        ``provenance.record_step``; ``None`` for fsaverage meshes, which
        are recorded as parameters.
    """
    if isinstance(mesh, str) and not mesh.endswith('.gii'):
        with io_utils.optional_silent_print(verbose):
            return nilearn.datasets.load_fsaverage(mesh=standard_surface)[mesh], mesh, None
    if isinstance(mesh, (str, os.PathLike)):
        polymesh, disk_meta = _load_polymesh(mesh)
        return polymesh, None, provenance.describe(mesh, meta if meta is not None else disk_meta)
    if not isinstance(mesh, nilearn.surface.PolyMesh):
        mesh = nilearn.surface.PolyMesh(**mesh)
    return mesh, None, (None, meta)


def _load_polymesh(path):
    """
    Load a mesh saved with ``PolyMesh.to_filename`` (as
    ``<name>_hemi-L.gii`` and ``<name>_hemi-R.gii``) and its sidecar.

    Parameters
    ----------
    path : path-like
        Base path the mesh was saved with.

    Returns
    -------
    mesh : nilearn.surface.PolyMesh
        The mesh.
    meta : dict or None
        Its sidecar, ``None`` if there is none.
    """
    path = Path(path)
    parts = {hemi: path.with_name(f'{path.stem}_hemi-{h}{path.suffix}') for hemi, h in (('left', 'L'), ('right', 'R'))}
    return nilearn.surface.PolyMesh(**parts), io_utils.load_sidecar(path, errors='ignore')


def _labels(meta):
    """
    Label names recorded in a sidecar (e.g. by
    ``volume.winner_take_all``).

    Parameters
    ----------
    meta : dict or None
        Sidecar.

    Returns
    -------
    dict or None
        Mapping of label value (str) to name, ``None`` if not recorded.
    """
    return (meta or {}).get('labels')


def _prepare_mask(img, mask_img=None, load_errors='raise'):
    """
    Prepare a binary mask for a 3D or 4D image.

    If ``mask_img`` is provided, it is checked for shape and affine
    compatibility with ``img``. If they do not match, the mask is
    resampled to the image space using nearest-neighbor interpolation.
    If no mask is provided, a default mask of all ones is created.

    Parameters
    ----------
    img : nib.Nifti1Image
        Image for which to prepare the mask.
    mask_img : nib.Nifti1Image or path-like, optional
        Optional binary mask image. If provided, it will be checked and
        potentially resampled to match ``img``.
    load_errors : {'raise', 'warn'}, optional
        How to handle loading errors when loading ``mask_img``. Default
        is ``'raise'``.

    Returns
    -------
    mask_data : np.ndarray
        Boolean array of shape (x, y, z) representing the binary mask.
    mask_input : tuple or None
        ``(path, meta)`` describing the mask for
        ``provenance.record_step``, ``None`` if no mask was given.
    """
    if mask_img is not None:
        mask_img, mask_input = _check_input_img(mask_img, load_errors=load_errors)
        # Check if the mask needs to be resampled to match the image.
        shapes_match = img.shape[:3] == mask_img.shape[:3]
        # Check affine (voxel size + orientation + origin).
        affines_match = np.allclose(img.affine, mask_img.affine, atol=1e-3)

        if not shapes_match or not affines_match:
            mask_img = nilearn.image.resample_to_img(mask_img, img, interpolation='nearest')

        mask_data = mask_img.get_fdata(caching='unchanged').astype(bool)  # (x, y, z)
    else:
        # Use everything if mask was not provided.
        mask_data = np.ones(img.shape[:3], dtype=bool)
        mask_input = None

    return mask_data, mask_input


def _atlas_input(atlas):
    """
    Describe an atlas for ``provenance.record_step``.

    Parameters
    ----------
    atlas : str or path-like
        Path to a NIfTI atlas or a nilearn atlas name.

    Returns
    -------
    tuple or None
        ``(path, meta)`` for a NIfTI atlas. ``None`` for a nilearn
        atlas, which is recorded as a parameter instead.
    """
    atlas_str = str(atlas)
    if atlas_str.endswith('.nii') or atlas_str.endswith('.nii.gz'):
        return provenance.describe(atlas_str)
    return None
