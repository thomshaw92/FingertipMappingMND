import contextlib
import copy
import json
import os
import warnings
import tempfile
import matplotlib
import numpy as np
import nibabel as nib
import nilearn.datasets
import nilearn.image
import nilearn.plotting
from nilearn.surface import SurfaceImage
from statsmodels.stats.multitest import multipletests
import logging
from pathlib import Path
import pandas as pd
import subprocess
import matplotlib.pyplot as plt
import shlex

import io_utils
import provenance

logger = logging.getLogger(__name__)

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


def _get_output_path(input_path, suffix, extension=None):
    """
    Derive an output file path by appending a suffix to the input stem.

    Handles compound extensions such as ``.nii.gz`` correctly.

    Parameters
    ----------
    input_path : path-like
        Path to the input file.
    suffix : str
        Suffix to append before the file extension(s).

    Returns
    -------
    str
        Output file path with the suffix inserted before the extension.
    """
    input_path = Path(input_path)
    # For files with multiple extensions (e.g., .nii.gz).
    full_ext = "".join(input_path.suffixes)
    if extension is not None:
        full_ext = extension
    return f'{input_path.parent}/{input_path.stem.replace(".nii", "")}_{suffix}{full_ext}'


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

        mask_data = mask_img.get_fdata().astype(bool)  # (x, y, z)
    else:
        # Use everything if mask was not provided.
        mask_data = np.ones(img.shape[:3], dtype=bool)
        mask_input = None

    return mask_data, mask_input


def _atlas_input(atlas):
    """Describe a file atlas for provenance; nilearn atlases are parameters."""
    atlas_str = str(atlas)
    if atlas_str.endswith('.nii') or atlas_str.endswith('.nii.gz'):
        return provenance.describe(atlas_str)
    return None


def _correct_single_img(img, alpha=0.05, method='fdr_bh', mask_data=None):
    """
    Apply multiple-comparison correction to a p-value image.

    NaN voxels are excluded from correction and preserved in the output.

    Parameters
    ----------
    img : nib.Nifti1Image
        3D image of uncorrected p-values.
    alpha : float, optional
        Family-wise error rate. Default is ``0.05``.
    method : str, optional
        Correction method passed to
        ``statsmodels.stats.multitest.multipletests``. Default is
        ``'fdr_bh'`` (Benjamini-Hochberg FDR).

    Returns
    -------
    nib.Nifti1Image
        Image of corrected p-values with the same affine as ``img``.
    """
    data = img.get_fdata().copy()
    if mask_data is not None:
        data[np.invert(mask_data)] = np.nan  # Set voxels outside the mask to NaN.

    flat = data.flatten()
    nans = np.isnan(flat)
    clean = flat[~nans]

    _, corr, _, _ = multipletests(clean, alpha=alpha, method=method)
    # Make sure to preserve NaNs. This is needed for reshaping back to
    # the original shape.
    new = np.empty_like(flat)
    new[~nans] = corr
    new[nans] = np.nan

    corr = new.reshape(data.shape)
    if mask_data is not None:
        corr[np.invert(mask_data)] = 0.0  # set values otuside of the mask to 0s

    return nib.Nifti1Image(corr, affine=img.affine)


def correct_single_image(file_in, meta=None, output_path=None, mask_img=None, alpha=0.05, method='fdr_bh', contrast_idx=None, suffix='corrected', load_errors='raise'):
    """
    Correct p-values in a single image for multiple comparisons.

    Parameters
    ----------
    file_in : path-like or nib.Nifti1Image
        Input p-value image. If a path is given the image is loaded from
        disk.
    meta : dict, optional
        Sidecar of ``file_in``. Loaded from disk if not given.
    output_path : path-like or None, optional
        Path at which to save the corrected image. If ``None`` a default
        path is derived from ``file_in`` and ``suffix``. Pass ``False``
        to suppress saving.
    alpha : float, optional
        Family-wise error rate. Default is ``0.05``.
    method : str, optional
        Correction method. Default is ``'fdr_bh'``.
    contrast_idx : int, optional
        Index of the contrast to correct when ``file_in`` is 4D.
    suffix : str, optional
        Suffix appended to the filename when generating a default output
        path. Default is ``'corrected'``.
    load_errors : {'raise', 'warn'}, optional
        How to handle loading errors. Default is ``'raise'``.

    Returns
    -------
    corr_img : nib.Nifti1Image
        Corrected p-value image.
    meta : dict
        Sidecar of the corrected image.
    """
    img, img_input = _check_input_img(file_in, meta=meta, load_errors=load_errors)

    img = _select_contrast_img(img, contrast_idx=contrast_idx)
    mask_data, mask_input = _prepare_mask(img, mask_img=mask_img, load_errors=load_errors)
    corr_img = _correct_single_img(img, alpha=alpha, method=method, mask_data=mask_data)

    if output_path is None:
        output_path = _get_output_path(file_in, suffix=suffix)

    meta = provenance.record_step(
        'analysis.correct_single_image',
        inputs={'p_values': img_input, 'mask': mask_input},
        parameters={'method': method, 'alpha': alpha, 'contrast_idx': contrast_idx},
        output_path=output_path
    )

    if output_path:
        io_utils.save_image(corr_img, output_path, meta=meta)

    return corr_img, meta


def correct_images(file_in, meta=None, output_path=None, mask_img=None, alpha=0.05, method='fdr_bh', suffix='corrected', load_errors='raise'):
    """
    Correct p-values for multiple comparisons across all contrasts in a
    4D image.

    Each contrast volume is corrected independently.

    Parameters
    ----------
    file_in : path-like
        Path to a 4D image whose volumes correspond to individual
        contrasts.
    meta : dict, optional
        Sidecar of ``file_in``. Loaded from disk if not given.
    output_path : path-like or None, optional
        Path at which to save the corrected 4D image. If ``None`` a
        default path is derived from ``file_in`` and ``suffix``. Pass
        ``False`` to suppress saving.
    alpha : float, optional
        Family-wise error rate. Default is ``0.05``.
    method : str, optional
        Correction method. Default is ``'fdr_bh'``.
    suffix : str, optional
        Suffix appended to the filename when generating a default output
        path. Default is ``'corrected'``.
    load_errors : {'raise', 'warn'}, optional
        How to handle loading errors. Default is ``'raise'``.

    Returns
    -------
    concat_img : nib.Nifti1Image
        4D image of corrected p-values, contrasts concatenated in the
        same order as the input.
    meta : dict
        Sidecar of the corrected image.
    """
    img, img_meta, img_dict = io_utils.load_contrasts_img(file_in, errors=load_errors)
    img_input = provenance.describe(file_in, meta if meta is not None else img_meta)

    new_imgs = {}
    for contrast, img in img_dict.items():
        mask_data, mask_input = _prepare_mask(img, mask_img=mask_img, load_errors=load_errors)
        new_imgs[contrast] = _correct_single_img(img, alpha=alpha, method=method, mask_data=mask_data)

    # Concatenate along a new axis to create a 4D image.
    concat_img = nib.concat_images(list(new_imgs.values()))

    if output_path is None:
        output_path = _get_output_path(file_in, suffix=suffix)

    meta = provenance.record_step(
        'analysis.correct_images',
        inputs={'p_values': img_input, 'mask': mask_input},
        parameters={'method': method, 'alpha': alpha},
        output_path=output_path,
        fields={'volume_labels': list(new_imgs.keys())}
    )

    if output_path:
        io_utils.save_image(concat_img, output_path, meta=meta)

    return concat_img, meta, new_imgs


def correct_images_folder(path, suffix='corrected', filename_contains='p_value', verbose=True, alpha=0.05, method='fdr_bh', mask_img=None):
    """
    Correct all p-value images in a folder for multiple comparisons.

    Files are processed in-place: each corrected image is saved next to
    its source with ``suffix`` appended to the filename. 3D files are
    corrected with :func:`correct_single_image`; 4D files with
    :func:`correct_images`. Already corrected files (i.e. those whose
    name contains ``suffix``) are skipped.

    Parameters
    ----------
    path : path-like
        Folder to search for p-value images.
    suffix : str, optional
        Suffix appended to corrected filenames. Also used to skip files
        that were already corrected. Default is ``'corrected'``.
    filename_contains : str, optional
        Only files whose name contains this string are processed.
        Default is ``'p_value'``.
    verbose : bool, optional
        If ``True``, log each skipped and corrected file. Default is
        ``True``.
    alpha : float, optional
        Family-wise error rate. Default is ``0.05``.
    method : str, optional
        Correction method. Default is ``'fdr_bh'``.
    mask_img : nib.Nifti1Image, optional
        Mask image to use for correction. If not provided, no masking will be applied.
    """
    for file in Path(path).iterdir():
        if file.is_dir():
            continue

        if (filename_contains not in file.name) or (suffix in file.name) or ('.nii' not in file.suffixes):
            if verbose:
                logger.info(f'Skipping {file.relative_to(path)}')
            continue

        if nib.load(file).ndim > 3:
            corr_img, _, _ = correct_images(file, alpha=alpha, method=method, suffix=suffix, load_errors='warn', mask_img=mask_img)
        else:
            corr_img, _ = correct_single_image(file, alpha=alpha, method=method, suffix=suffix, load_errors='warn', mask_img=mask_img)

        if verbose:
            corr_filename = corr_img.get_filename()
            corr_display = Path(corr_filename).relative_to(path) if corr_filename else 'unknown'
            logger.info(f'Corrected {file.relative_to(path)} -> {corr_display}')


def _roi_single_img(img, regions, atlas='destrieux_2009', outside_val=np.nan):
    """
    Mask a 3D image to retain only the specified atlas regions.

    Parameters
    ----------
    img : nib.Nifti1Image
        Image to mask.
    regions : list of str
        Atlas region names to retain.
    atlas : str, optional
        Atlas name passed to :func:`get_roi_mask`. Default is
        ``'destrieux_2009'``.

    Returns
    -------
    nib.Nifti1Image
        Image with voxels outside the ROI set to NaN.
    """
    mask = get_roi_mask(img=img, atlas=atlas, regions=regions, use_temp=False, verbose=0)
    img_data = img.get_fdata()
    mask_data = mask.get_fdata()
    masked_data = np.where(mask_data, img_data, outside_val)
    return nib.Nifti1Image(masked_data, affine=img.affine)


def get_roi_mask(img, regions, atlas='destrieux_2009', use_temp=True, verbose=1):
    """
    Get a binary mask for specified regions from an atlas.

    The atlas is either fetched via nilearn or loaded from a NIfTI file.
    When ``atlas`` is a path to a ``.nii`` or ``.nii.gz`` file, a JSON
    sidecar with the same stem is expected alongside it (e.g.
    ``atlas.json`` for ``atlas.nii.gz``). The sidecar must map integer
    label indices to objects with a ``"name"`` key, e.g.::

        {"1": {"name": "Left-Cerebral-Exterior", ...}, ...}

    The atlas is resampled to match ``img``.

    Parameters
    ----------
    img : nib.Nifti1Image
        Reference image that defines the output mask space.
    regions : list of str
        Names of atlas regions to include in the mask.
    atlas : str or path-like, optional
        Either a nilearn atlas name corresponding to a
        ``nilearn.datasets.fetch_atlas_*`` function (default
        ``'destrieux_2009'``), or a path to a NIfTI atlas file with a
        JSON sidecar.
    use_temp : bool, optional
        Only used when ``atlas`` is a nilearn atlas name. If ``True``,
        the atlas is downloaded to a temporary directory. Default is
        ``True``.
    verbose : int, optional
        Only used when ``atlas`` is a nilearn atlas name. Verbosity
        level passed to the nilearn atlas fetcher. Default is ``1``.

    Returns
    -------
    nib.Nifti1Image
        Binary mask resampled to the space of ``img``.

    Raises
    ------
    FileNotFoundError
        If ``atlas`` is a NIfTI path but the JSON sidecar is missing.
    KeyError
        If a requested region name is not found in the atlas labels.
    """
    atlas_str = str(atlas)
    atlas_is_file = atlas_str.endswith('.nii') or atlas_str.endswith('.nii.gz')

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")

        if atlas_is_file:
            atlas_img, label_map = io_utils.load_image(atlas_str)
            name_to_idx = {v['name']: int(k) for k, v in label_map.items()}
            region_indices = [name_to_idx[rg] for rg in regions]
            mask = nilearn.image.math_img(" + ".join([f"(img == {i})" for i in region_indices]), img=atlas_img)
        else:
            getter = getattr(nilearn.datasets, f'fetch_atlas_{atlas}')
            # Either use a temp directory or use None (which defaults to nilearn's caching directory).
            ctx = tempfile.TemporaryDirectory() if use_temp else contextlib.nullcontext()
            with ctx as tmpdir:
                dest = getter(data_dir=tmpdir, verbose=verbose)
                atlas_img = nib.load(dest['maps'])
                labels = dest['labels']
                region_indices = [labels.index(rg) for rg in regions]
                # math_img must stay inside the context: nib.load is lazy and
                # the temp directory must still exist when the data is read.
                mask = nilearn.image.math_img(" + ".join([f"(img == {i})" for i in region_indices]), img=atlas_img)

        mask_resampled = nilearn.image.resample_to_img(mask, img, interpolation='nearest', copy_header=True, force_resample=True)

    return mask_resampled


def roi_single_image(input_path, regions, meta=None, contrast_idx=None, atlas='destrieux_2009', output_path=None, suffix='roi', load_errors='raise', outside_val=np.nan):
    """
    Apply an atlas-based ROI mask to a single image.

    Parameters
    ----------
    input_path : path-like or nib.Nifti1Image
        Input image to mask.
    regions : list of str
        Atlas region names to retain.
    meta : dict, optional
        Sidecar of ``input_path``. Required to keep the provenance of
        in-memory images; loaded from disk for paths if not given.
    contrast_idx : int, optional
        Index of the contrast to mask when ``input_path`` is 4D.
    atlas : str, optional
        Atlas name. Default is ``'destrieux_2009'``.
    output_path : path-like or None, optional
        Path at which to save the masked image. If ``None`` a default
        path is derived from ``input_path`` and ``suffix``. Pass
        ``False`` to suppress saving.
    suffix : str, optional
        Suffix appended to the filename when generating a default output
        path. Default is ``'roi'``.
    load_errors : {'raise', 'warn'}, optional
        How to handle loading errors. Default is ``'raise'``.

    Returns
    -------
    masked_img : nib.Nifti1Image
        Image with voxels outside the ROI set to NaN.
    meta : dict
        Sidecar of the masked image.
    """
    img, img_input = _check_input_img(input_path, meta=meta, load_errors=load_errors)
    img = _select_contrast_img(img, contrast_idx=contrast_idx)
    masked_img = _roi_single_img(img, regions, atlas=atlas, outside_val=outside_val)

    if output_path is None:
        output_path = _get_output_path(input_path, suffix=suffix)

    atlas_input = _atlas_input(atlas)
    meta = provenance.record_step(
        'analysis.roi_single_image',
        inputs={'img': img_input, 'atlas': atlas_input},
        parameters={
            'atlas': atlas if atlas_input is None else None,
            'regions': regions,
            'contrast_idx': contrast_idx,
            'outside_val': outside_val
        },
        output_path=output_path
    )

    if output_path:
        io_utils.save_image(masked_img, output_path, meta=meta)

    return masked_img, meta


def roi_images(input_path, regions, meta=None, atlas='destrieux_2009', output_path=None, suffix='roi', load_errors='raise', outside_val=np.nan):
    """
    Apply an atlas-based ROI mask to all contrasts in a 4D image.

    Parameters
    ----------
    input_path : path-like
        Path to a 4D image whose volumes correspond to individual
        contrasts.
    regions : list of str
        Atlas region names to retain.
    meta : dict, optional
        Sidecar of ``input_path``. Loaded from disk if not given.
    atlas : str, optional
        Atlas name. Default is ``'destrieux_2009'``.
    output_path : path-like or None, optional
        Path at which to save the masked 4D image. If ``None`` a default
        path is derived from ``input_path`` and ``suffix``. Pass
        ``False`` to suppress saving.
    suffix : str, optional
        Suffix appended to the filename when generating a default output
        path. Default is ``'roi'``.
    load_errors : {'raise', 'warn'}, optional
        How to handle loading errors. Default is ``'raise'``.

    Returns
    -------
    concat_img : nib.Nifti1Image
        4D masked image with contrasts concatenated in the same order as
        the input.
    meta : dict
        Sidecar of the masked image.
    """
    img, img_meta, img_dict = io_utils.load_contrasts_img(input_path, errors=load_errors)
    img_input = provenance.describe(input_path, meta if meta is not None else img_meta)

    new_imgs = {}
    for contrast, contrast_img in img_dict.items():
        new_imgs[contrast] = _roi_single_img(contrast_img, regions, atlas=atlas, outside_val=outside_val)

    # Concatenate along a new axis to create a 4D image.
    concat_img = nib.concat_images(list(new_imgs.values()))

    if output_path is None:
        output_path = _get_output_path(input_path, suffix=suffix)

    atlas_input = _atlas_input(atlas)
    meta = provenance.record_step(
        'analysis.roi_images',
        inputs={'img': img_input, 'atlas': atlas_input},
        parameters={
            'atlas': atlas if atlas_input is None else None,
            'regions': regions,
            'outside_val': outside_val
        },
        output_path=output_path,
        fields={'volume_labels': list(new_imgs.keys())}
    )

    if output_path:
        io_utils.save_image(concat_img, output_path, meta=meta)

    return concat_img, meta, new_imgs


def _threshold_single_img(img, thresh_img, alpha=0.05, thresh_val=np.nan, mask_data=None):
    """
    Threshold an image using a p-value map.

    Voxels where the p-value exceeds ``alpha`` are set to NaN.

    Parameters
    ----------
    img : nib.Nifti1Image
        Image to threshold (e.g. a contrast estimate map).
    thresh_img : nib.Nifti1Image
        Corresponding p-value image with the same shape as ``img``.
    alpha : float, optional
        Significance threshold. Default is ``0.05``.

    Returns
    -------
    nib.Nifti1Image
        Thresholded image with the same affine as ``img``.
    """
    img_data = img.get_fdata()
    thresh_data = thresh_img.get_fdata()
    mask = thresh_data <= alpha
    masked_data = np.where(mask, img_data, thresh_val)
    if mask_data is not None:
        masked_data[np.invert(mask_data)] = 0.0  # Set voxels outside the mask to a background value.
    return nib.Nifti1Image(masked_data, affine=img.affine)


def threshold_single_image(img_to_thresh, thresh_img, meta=None, alpha=0.05, contrast_idx=None, output_path=None, suffix='thresholded', load_errors='raise', thresh_val=np.nan, mask_img=None):
    """
    Threshold a single image using a p-value map.

    Parameters
    ----------
    img_to_thresh : path-like or nib.Nifti1Image
        Image to threshold (e.g., a contrast estimate map).
    thresh_img : path-like or nib.Nifti1Image
        Corresponding p-value image used as the threshold mask.
    meta : dict, optional
        Sidecar of ``img_to_thresh``. Loaded from disk if not given.
    alpha : float, optional
        Significance threshold. Default is ``0.05``.
    contrast_idx : int, optional
        Index of the contrast to threshold when either input is 4D.
    output_path : path-like or None, optional
        Path at which to save the thresholded image. If ``None`` a
        default path is derived from ``img_to_thresh`` and ``suffix``.
        Pass ``False`` to suppress saving.
    suffix : str, optional
        Suffix appended to the filename when generating a default output
        path. Default is ``'thresholded'``.
    load_errors : {'raise', 'warn'}, optional
        How to handle loading errors. Default is ``'raise'``.

    Returns
    -------
    masked_img : nib.Nifti1Image
        Thresholded image.
    meta : dict
        Sidecar of the thresholded image.
    """
    est_img, est_input = _check_input_img(img_to_thresh, meta=meta, load_errors=load_errors)
    est_img = _select_contrast_img(est_img, contrast_idx=contrast_idx)

    p_img, p_input = _check_input_img(thresh_img, load_errors=load_errors)
    p_img = _select_contrast_img(p_img, contrast_idx=contrast_idx)

    mask_data, mask_input = _prepare_mask(est_img, mask_img=mask_img, load_errors=load_errors)

    masked_img = _threshold_single_img(est_img, p_img, alpha=alpha, thresh_val=thresh_val, mask_data=mask_data)

    if output_path is None:
        output_path = _get_output_path(img_to_thresh, suffix=suffix)

    meta = provenance.record_step(
        'analysis.threshold_single_image',
        inputs={'img': est_input, 'thresh_img': p_input, 'mask': mask_input},
        parameters={'alpha': alpha, 'contrast_idx': contrast_idx, 'thresh_val': thresh_val},
        output_path=output_path
    )

    if output_path:
        io_utils.save_image(masked_img, output_path, meta=meta)

    return masked_img, meta


def threshold_images(img_to_thresh, thresh_img, meta=None, alpha=0.05, output_path=None, suffix='thresholded', load_errors='raise', thresh_val=np.nan, mask_img=None):
    """
    Threshold a 4D image using a p-value image, contrast by contrast.

    If ``thresh_img`` is 4D, its contrasts must match those of
    ``img_to_thresh``. If it is 3D, the same threshold map is applied to
    every contrast.

    Parameters
    ----------
    img_to_thresh : path-like
        Path to a 4D image to threshold (e.g., contrast estimate maps).
    thresh_img : path-like
        Path to the p-value image used as the threshold mask. May be 3D
        (applied to all contrasts) or 4D (matched per contrast).
    meta : dict, optional
        Sidecar of ``img_to_thresh``. Loaded from disk if not given.
    alpha : float, optional
        Significance threshold. Default is ``0.05``.
    output_path : path-like or None, optional
        Path at which to save the thresholded 4D image. If ``None`` a
        default path is derived from ``img_to_thresh`` and ``suffix``.
        Pass ``False`` to suppress saving.
    suffix : str, optional
        Suffix appended to the filename when generating a default output
        path. Default is ``'thresholded'``.
    load_errors : {'raise', 'warn'}, optional
        How to handle loading errors. Default is ``'raise'``.

    Returns
    -------
    concat_img : nib.Nifti1Image
        4D thresholded image with contrasts in the same order as the
        input.
    meta : dict
        Sidecar of the thresholded image.

    Raises
    ------
    ValueError
        If both images are 4D but their contrast keys do not match.
    """
    est_img, est_meta, est_dict = io_utils.load_contrasts_img(img_to_thresh, errors=load_errors)
    est_input = provenance.describe(img_to_thresh, meta if meta is not None else est_meta)
    p_img = nib.load(thresh_img)

    if p_img.ndim == 4:
        _, p_meta, p_dict = io_utils.load_contrasts_img(thresh_img, errors=load_errors)
        if set(p_dict.keys()) != set(est_dict.keys()):
            raise ValueError('Threshold image contrasts do not match target image contrasts.')
        p_input = provenance.describe(thresh_img, p_meta)
    else:
        logger.warning(f'Thresholding image {thresh_img} is 3D. Applying same threshold to all contrasts in {img_to_thresh}.')
        p_dict = {contrast: p_img for contrast in est_dict.keys()}
        p_input = provenance.describe(thresh_img)

    new_imgs = {}
    for contrast, est_contrast_img in est_dict.items():
        p_contrast_img = p_dict[contrast]
        mask_data, mask_input = _prepare_mask(est_contrast_img, mask_img=mask_img, load_errors=load_errors)
        new_imgs[contrast] = _threshold_single_img(est_contrast_img, p_contrast_img, alpha=alpha, thresh_val=thresh_val, mask_data=mask_data)

    # Concatenate along a new axis to create a 4D image.
    concat_img = nib.concat_images(list(new_imgs.values()))

    if output_path is None:
        output_path = _get_output_path(img_to_thresh, suffix=suffix)

    meta = provenance.record_step(
        'analysis.threshold_images',
        inputs={'img': est_input, 'thresh_img': p_input, 'mask': mask_input},
        parameters={'alpha': alpha, 'thresh_val': thresh_val},
        output_path=output_path,
        fields={'volume_labels': list(new_imgs.keys())}
    )

    if output_path:
        io_utils.save_image(concat_img, output_path, meta=meta)

    return concat_img, meta, new_imgs


def argmax_contrast(img, meta=None, output_path=None, below_thresh_val=np.nan, outside_roi_val=np.nan, no_result_idx=-1, suffix='argmax', inconsistent_roi='raise', load_errors='raise'):
    """
    Return the contrast index with the highest z-score per voxel.

    For each voxel the index of the contrast with the largest
    z-score is returned. Two types of masked values are handled:

    - *Below threshold*: values equal to ``thresh_val`` (NaN by
      default). Excluded from the argmax per contrast independently.
    - *Outside ROI*: voxels identified by ``roi_mask`` or by
      values equal to ``outside_val``. Must be consistent across
      all contrasts at each voxel.

    Parameters
    ----------
    img : path-like or nib.Nifti1Image
        4D image of z-scores. The 4th dimension indexes contrasts.
    roi_mask : path-like or nib.Nifti1Image, optional
        3D binary mask. Voxels where the mask is zero are set to
        NaN in the output. If ``None``, the ROI is inferred from
        ``outside_val`` when it differs from ``thresh_val``; if
        they are indistinguishable, all masked voxels are treated
        as below threshold with no inconsistency check.
    thresh_val : float, optional
        Sentinel value indicating a below-threshold contrast.
        NaN by default (NaN-aware comparison is used).
    outside_val : float, optional
        Sentinel value indicating an outside-ROI voxel.
        NaN by default. May equal ``thresh_val``.
    no_result_idx : int, optional
        Value written to voxels where all contrasts are below
        threshold. Default is ``-1``.
    inconsistent_roi : {'raise', 'warn'}, optional
        Action taken when the outside-ROI masking is inconsistent
        across contrasts at any voxel. Default is ``'raise'``.
    load_errors : {'raise', 'warn'}, optional
        How to handle loading errors. Default is ``'raise'``.

    Returns
    -------
    argmax_img : nib.Nifti1Image
        3D image of contrast indices (float32). NaN where outside
        the ROI; ``no_result_idx`` where all contrasts are masked.
    meta : dict
        Metadata including the parameters used.

    Raises
    ------
    ValueError
        If ``img`` is not 4D.
    ValueError
        If ``inconsistent_roi='raise'`` and the outside-ROI
        masking is inconsistent across contrasts.
    """
    img, img_input = _check_input_img(img, meta=meta, load_errors=load_errors)

    if img.ndim != 4:
        raise ValueError(f'img must be 4D, got {img.ndim}D.')

    data = img.get_fdata()
    n_contrasts = data.shape[-1]

    thresh_is_nan = bool(np.isnan(below_thresh_val))
    outside_is_nan = bool(np.isnan(outside_roi_val))
    # Are thresholded values and outside-ROI values indistinguishable?
    vals_same = (thresh_is_nan and outside_is_nan) or (
        not thresh_is_nan and not outside_is_nan
        and below_thresh_val == outside_roi_val
    )

    below_thresh = np.isnan(data) if thresh_is_nan else (data == below_thresh_val)
    outside_arr = np.isnan(data) if outside_is_nan else (data == outside_roi_val)
    not_valid = below_thresh | outside_arr

    if not vals_same:
        # Infer ROI from outside_val (distinguishable from thresh_val).
        outside_count = outside_arr.sum(axis=-1)
        # Since these are numpy.arrays we cannot use 
        # ``0 < outside_count < n_contrast``.
        partially_outside = (0 < outside_count) & (outside_count < n_contrasts)
        if np.any(partially_outside):
            n = int(np.sum(partially_outside))
            msg = (
                f'{n} voxel(s) have outside-ROI values in some '
                f'but not all contrasts — the contrast images may '
                f'not have been masked identically.'
            )
            if inconsistent_roi == 'raise':
                raise ValueError(msg)
            else:
                logger.warning(msg)
        # Mark voxels where not all contrasts are inside the ROI as
        # outside the ROI.
        in_roi = ~np.all(outside_arr, axis=-1)
    else:
        # If below_thresh_val and outside_roi_val are indistinguishable
        # use all values without inferring what is inside/outside the
        # ROI.
        in_roi = np.ones(data.shape[:3], dtype=bool)

    result = np.full(data.shape[:3], 0.0, dtype=np.float32)

    # All voxels that are within the ROI but have all contrasts below
    # threshold get a special value of `no_result_idx`.
    all_non_valid = np.all(not_valid, axis=-1)
    result[in_roi & all_non_valid] = no_result_idx

    some_valid_in_roi = in_roi & ~all_non_valid
    if np.any(some_valid_in_roi):
        # Use -np.inf so that argmax never selects it by accident.
        data_for_argmax = np.where(not_valid, -np.inf, data)
        # 0 is reserved for outside of ROI/Background.
        argmax_vals = np.argmax(data_for_argmax, axis=-1) + 1
        result[some_valid_in_roi] = argmax_vals[some_valid_in_roi]

    out_img = nib.Nifti1Image(result, affine=img.affine)

    if output_path is None:
        if img.get_filename() is None:
            logger.warning('Input image has no filename and `ouput_path` has not been provided. Cannot derive output path. Not saving output image.')
            output_path = False
        else:
            output_path = _get_output_path(img, suffix=suffix)

    meta = provenance.record_step(
        'analysis.argmax_contrast',
        inputs={'img': img_input},
        parameters={
            'below_thresh_val': below_thresh_val,
            'outside_roi_val': outside_roi_val,
            'no_result_idx': no_result_idx,
            'inconsistent_roi': inconsistent_roi
        },
        output_path=output_path
    )

    if output_path:
        io_utils.save_image(out_img, output_path, meta=meta)

    return out_img, meta


def apply_over_time(img, func, mask_img=None, meta=None, output_path=None, suffix='apply', load_errors='raise', **func_kwargs):
    
    img, img_input = _check_input_img(img, meta=meta, load_errors=load_errors)
    if img.ndim != 4:
        raise ValueError(f'img must be 4D, got {img.ndim}D.')

    mask_data, mask_input = _prepare_mask(img, mask_img, load_errors=load_errors)

    data = img.get_fdata()  # (x, y, z, t)
    data_2d = data[mask_data, :]  # (n_voxels, t)

    result_1d = np.apply_along_axis(func, axis=1, arr=data_2d, **func_kwargs)  # (n_voxels,)
    # Put back into volume but use 3D.
    result_3d = np.full(img.shape[:3], 0.0, dtype=np.float32)
    result_3d[mask_data] = result_1d

    result_img = nib.Nifti1Image(result_3d, img.affine, img.header)

    if output_path is None:
        if img.get_filename() is None:
            logger.warning('Input image has no filename and `ouput_path` has not been provided. Cannot derive output path. Not saving output image.')
            output_path = False
        else:
            output_path = _get_output_path(img, suffix=suffix)

    meta = provenance.record_step(
        'analysis.apply_over_time',
        inputs={'img': img_input, 'mask': mask_input},
        parameters={'func': func, 'func_kwargs': func_kwargs},
        output_path=output_path
    )

    if output_path:
        io_utils.save_image(result_img, output_path, meta=meta)

    return result_img, meta


def concat_images(imgs, metas=None, labels=None, output_path=None):
    """
    Concatenate 3D images into a 4D image.

    Parameters
    ----------
    imgs : list of nib.Nifti1Image or path-like
        Images to concatenate, in order.
    metas : list of dict, optional
        Sidecars of ``imgs``. Required to keep the provenance of
        in-memory images.
    labels : list of str, optional
        Label of each volume. Saved as ``volume_labels`` so the result
        can be read with ``io_utils.load_contrasts_img``.
    output_path : path-like or None, optional
        Path at which to save the 4D image. Pass ``None``/``False`` to
        suppress saving.

    Returns
    -------
    concat_img : nib.Nifti1Image
        4D image.
    meta : dict
        Sidecar of the 4D image.
    """
    if metas is None:
        metas = [None] * len(imgs)
    if labels is None:
        labels = [str(idx) for idx in range(len(imgs))]
    if not len(imgs) == len(metas) == len(labels):
        raise ValueError('`imgs`, `metas` and `labels` must have the same length.')

    concat_img = nib.concat_images(imgs)
    if concat_img.ndim != 4 or concat_img.shape[-1] != len(imgs):
        raise ValueError(f'Images have not been concatenated along the 4th dimension. The concatenated image shape: {concat_img.shape}')

    meta = provenance.record_step(
        'analysis.concat_images',
        inputs={lab: provenance.describe(img, img_meta) for lab, img, img_meta in zip(labels, imgs, metas)},
        output_path=output_path,
        fields={'volume_labels': list(labels)}
    )

    if output_path:
        io_utils.save_image(concat_img, output_path, meta=meta)

    return concat_img, meta


def wta(data, below_thresh_val=np.nan, outside_val=np.nan, no_result_idx=-1, only_positive=True):
    """
    Winner-take-all function to be applied with `apply_over_time`.

    For each voxel, the index of the maximum value is returned. Voxels
    where all values are equal to `below_thresh_val` (e.g. NaN) get
    `no_result_idx`. Voxels where all values are equal to `outside_val`
    get 0. If `below_thresh_val` and `outside_val` are indistinguishable,
    all masked voxels get `no_result_idx`.

    Parameters
    ----------
    data : 1D array-like
        Values for a single voxel across contrasts.
    below_thresh_val : float, optional
        Sentinel value indicating a below-threshold contrast. NaN by
        default (NaN-aware comparison is used).
    outside_val : float, optional
        Sentinel value indicating an outside-ROI voxel. NaN by default.
        May equal `below_thresh_val`.
    no_result_idx : int, optional
        Value returned for voxels where all contrasts are below threshold. Default is `-1`.
    """
    data = np.asarray(data)

    if np.isnan(below_thresh_val) and np.isnan(outside_val):
        # Can't distinguish outside from below_thresh; use data as is.
        outside = np.zeros(data.size, dtype=bool)
    else:
        outside = np.isnan(data) if np.isnan(outside_val) else (data == outside_val)
        if outside.all():
            return 0

    below_thresh = np.isnan(data) if np.isnan(below_thresh_val) else (data == below_thresh_val)

    if only_positive:
        positive_filter = data >= 0
    else:
        positive_filter = np.ones(data.size, dtype=bool)

    valid = ~outside & ~below_thresh & positive_filter
    if not valid.any():
        return no_result_idx
    
    # Use argmax only on the valid data (inside ROI and above threshold
    # ). Make sure to get the max index from the original data.
    valid_indices = np.where(valid)[0]
    valid_data = data[valid_indices]
    if np.nansum(valid_data) == 0:
        return 0
    max_valid_idx = np.argmax(valid_data)
    
    return valid_indices[max_valid_idx] + 1  # +1 to reserve 0 for outside ROI


def save_as_segmentation(img, meta=None, template=None, labels=None, output_path=None, suffix='segmentation', load_errors='raise', color_palette=None):
    """
    Save an image as a segmentation file.

    The image is saved in the same format as the input but with a filename
    suffix (default ``'segmentation'``) that can be used to identify it as
    a segmentation. The metadata is updated with a 'type' field set to
    'segmentation' and any additional parameters passed via kwargs.

    Parameters
    ----------
    img : path-like or nib.Nifti1Image
        Image to save as a segmentation. If a path is given, the image is
        loaded from disk.
    meta : dict, optional
        Sidecar of ``img``. Required to keep the provenance of in-memory
        images.
    template : path-like, nib.Nifti1Image or False, optional
        Image defining the output grid. Defaults to the 1mm MNI152
        template from nilearn. Pass ``False`` to keep the input grid.
    labels : dict or list, optional
        Label names, saved in the sidecar and as an ITK-SNAP label
        description file.
    output_path : path-like or None, optional
        Path at which to save the segmentation image. If ``None`` a
        default path is derived from the input image path and ``suffix``.
        Pass ``False`` to suppress saving.
    suffix : str, optional
        Suffix appended to the filename when generating a default output
        path. Default is ``'segmentation'``.
    load_errors : {'raise', 'warn'}, optional
        How to handle loading errors. Default is ``'raise'``.
    """
    img, img_input = _check_input_img(img, meta=meta, load_errors=load_errors)

    out_img = nib.Nifti1Image(
        img.get_fdata().astype(np.int16),
        affine=img.affine,
        header=img.header
    )
    out_img.header.set_data_dtype(np.int16)

    template_input = None
    template_name = None
    if template is None:
        template = nilearn.datasets.load_mni152_template(resolution=1)
        template_name = 'nilearn.datasets.load_mni152_template(resolution=1)'
    elif template is not False:
        template_input = provenance.describe(template)

    if template is not False:
        out_img = nilearn.image.resample_to_img(
            source_img=out_img,
            target_img=template,        # defines the output grid (space + resolution)
            interpolation='nearest',        # MUST be nearest for label images
            force_resample=True,
            copy_header=True,
        )

    if isinstance(labels, dict):
        # Only strings are allowed keys when saving as JSON.
        meta_labels = {str(k): v for k, v in labels.items()}
    else:
        meta_labels = labels

    if output_path is None:
        if img.get_filename() is None:
            logger.warning('Input image has no filename and `ouput_path` has not been provided. Cannot derive output path. Not saving output image.')
            output_path = False
        else:
            output_path = _get_output_path(img, suffix=suffix)

    labels_output_path = None
    if labels is not None and output_path:
        labels_output_path = _get_output_path(output_path, suffix='labels', extension='.txt')

    meta = provenance.record_step(
        'analysis.save_as_segmentation',
        inputs={'img': img_input, 'template': template_input},
        parameters={'template': template_name, 'color_palette': color_palette},
        output_path=output_path,
        fields={'labels': meta_labels, 'label_description_file': labels_output_path}
    )

    if output_path:
        io_utils.save_image(out_img, output_path, meta=meta)

    if labels_output_path:
        _save_itksnap_label_description(labels, output_path=labels_output_path, color_palette=color_palette)

    return out_img, meta


def _save_itksnap_label_description(labels, output_path=None, color_palette=None):
    def _get_color(label):
        if color_palette is not None and label in color_palette:
            return color_palette[label]
        elif callable(color_palette):
            return color_palette(label)
        else:
            # Default color palette (hex colors).
            default_colors = [
                '#e6194b', '#3cb44b', '#ffe119', '#4363d8', '#f58231',
                '#911eb4', '#46f0f0', '#f032e6', '#bcf60c', '#fabebe',
                '#008080', '#e6beff', '#9a6324', '#fffac8', '#800000',
                '#aaffc3', '#808000', '#ffd8b1', '#000075', '#808080',
                '#ffffff', '#000000'
            ]
            idx = hash(label) % len(default_colors)
            return default_colors[idx]
        
    def _hex_to_rgb(hex_color):
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    if not isinstance(labels, dict):
        labels = {idx: lab for idx, lab in enumerate(labels)}

    if not isinstance (next(iter(labels.values())), (tuple, list)):
        labels = {idx: (lab, _get_color(lab)) for idx, lab in labels.items()}

    # --- Write ITK-SNAP label description file ---
    # Format: <index>  <R>  <G>  <B>  <A>  <vis>  <mesh>  "label name"
    # A is 0–1 float; vis/mesh are 1=visible
    label_lines = [
        "################################################",
        "# ITK-SNAP Label Description File",
        "# File format:",
        "# IDX  R  G  B  A  VIS  MESH  LABEL",
        "################################################"
    ]

    for orig_idx, (label, color) in sorted(labels.items()):
        if isinstance(color, str):
            r, g, b = _hex_to_rgb(color)
        else:
            r, g, b, _ = (int(c * 255) for c in color)
        label_lines.append(f"{orig_idx}  {r}  {g}  {b}  1.0  1  1  \"{label}\"")

    if output_path:
        with open(output_path, 'w') as f:
            f.write('\n'.join(label_lines))

    return labels


def _remove_zeros(surf_img):
    """
    Replace zero values with NaN in a surface image.

    Prevents zeros from appearing in surface plots where NaN is treated
    as transparent.

    Parameters
    ----------
    surf_img : SurfaceImage
        Surface image to modify. A deep copy is made; the original is
        not modified.

    Returns
    -------
    SurfaceImage
        Copy of ``surf_img`` with zeros replaced by NaN in both
        hemispheres.
    """
    surf_img = copy.deepcopy(surf_img)
    for hemi in ['left', 'right']:
        idx = surf_img.data.parts[hemi] == 0
        surf_img.data.parts[hemi][idx] = np.nan

    return surf_img


def project_image(img_to_project, contrast=None, meta=None, output_path=None, mesh='pial', standard_surface='fsaverage6', verbose=True, load_errors='raise', inner_mesh='white_matter', radius=4, n_samples=20, mesh_meta=None, inner_mesh_meta=None, **kwargs):
    """
    Project a volumetric image onto a standard surface.

    Parameters
    ----------
    img_to_project : path-like
        Path to the volumetric image to project. May be 3D or 4D.
    contrast : str
        Name of the contrast to project. Used to select a volume from a
        4D image and to name the output file.
    meta : dict, optional
        Sidecar of ``img_to_project``. Loaded from disk if not given.
    output_path : path-like or None, optional
        Path at which to save the surface image. If ``None`` the file is
        saved in a ``surf/`` folder adjacent to the parent of
        ``img_to_project``. Pass ``False`` to suppress saving.
    standard_surface : str, optional
        fsaverage mesh resolution. Default is ``'fsaverage6'``.
    mesh : str, optional
        Surface mesh to use (e.g. ``'inflated'``, ``'pial'``). Default is
        ``'pial'``.
    verbose : bool, optional
        If ``True``, suppress nilearn's printed output. Default is
        ``True``.
    load_errors : {'raise', 'warn'}, optional
        How to handle loading errors. Default is ``'raise'``.
    inner_mesh : str, optional
        Inner mesh used for volume-to-surface projection. Default is
        ``'white_matter'``.
    radius : float, optional
        Radius (mm) for sampling around each surface vertex. Default is
        ``4``.
    n_samples : int, optional
        Number of samples along the normal for projection. Default is
        ``20``.
    mesh_meta, inner_mesh_meta : dict, optional
        Sidecars of ``mesh`` and ``inner_mesh`` when they are in-memory
        meshes (e.g. from :func:`transform_surface_to_mni`).
    **kwargs
        Additional keyword arguments passed to
        ``SurfaceImage.from_volume``.

    Returns
    -------
    surface_image : SurfaceImage
        Projected surface image.
    meta : dict
        Sidecar of the surface image.
    """
    mesh_param = mesh if isinstance(mesh, str) else None
    inner_mesh_param = inner_mesh if isinstance(inner_mesh, str) else None
    if isinstance(mesh, str):
        with io_utils.optional_silent_print(verbose):
            fsaverage = nilearn.datasets.load_fsaverage(mesh=standard_surface)
            mesh = fsaverage[mesh]
    if isinstance(inner_mesh, str):
        with io_utils.optional_silent_print(verbose):
            fsaverage = nilearn.datasets.load_fsaverage(mesh=standard_surface)
            inner_mesh = fsaverage[inner_mesh]

    vol_img = nib.load(img_to_project)
    if vol_img.ndim == 4:
        _, vol_meta, img_dict = io_utils.load_contrasts_img(img_to_project, errors=load_errors)
        vol_img = img_dict[contrast]
    else:
        vol_img, vol_meta = io_utils.load_image(img_to_project, errors=load_errors)
    vol_input = provenance.describe(img_to_project, meta if meta is not None else vol_meta)

    surface_image = SurfaceImage.from_volume(
        mesh=mesh,
        volume_img=vol_img,
        inner_mesh=inner_mesh,
        radius=radius,
        n_samples=n_samples,
        **kwargs
    )
    surface_image = _remove_zeros(surface_image)

    if output_path is None:
        # Make the `surf` folder outside of the `func` folder.
        surf_folder = Path(img_to_project).parent.parent / 'surf'
        output_path = surf_folder / f'{standard_surface}_{surface_type}_{contrast if contrast is not None else "unknown"}.gii'

    meta = provenance.record_step(
        'analysis.project_image',
        inputs={
            'img': vol_input,
            'mesh': None if mesh_param else (None, mesh_meta),
            'inner_mesh': None if inner_mesh_param else (None, inner_mesh_meta),
        },
        parameters={
            'standard_surface': standard_surface if (mesh_param or inner_mesh_param) else None,
            'mesh': mesh_param,
            'inner_mesh': inner_mesh_param,
            'contrast': contrast,
            'radius': radius,
            'n_samples': n_samples,
            'zeros_to_nan': True,
            **kwargs
        },
        output_path=output_path
    )

    if output_path:
        os.makedirs(Path(output_path).parent, exist_ok=True)
        io_utils.save_surface(surface_image, output_path, meta=meta)

    return surface_image, meta


def _surface_inputs(surf_file, meta=None):
    """
    Load surface data for plotting and describe it for provenance.

    ``surf_file`` is either a path saved by ``io_utils.save_surface`` or
    a dict with ``'left'``/``'right'`` keys holding paths to per-hemi
    GIFTI files or arrays. For in-memory arrays, ``meta`` may be a dict
    with the same keys holding the sidecar of each hemisphere.
    """
    if isinstance(surf_file, (Path, str)):
        surface_image, surf_meta = io_utils.load_surface(surf_file)
        if meta is not None:
            surf_meta = meta
        return surface_image, {'surface': provenance.describe(surf_file, surf_meta)}

    data, inputs = {}, {}
    for hemi, hemi_data in surf_file.items():
        hemi_meta = meta.get(hemi) if isinstance(meta, dict) and hemi in meta else meta
        if isinstance(hemi_data, (Path, str)):
            inputs[hemi] = provenance.describe(hemi_data, hemi_meta)
            hemi_data = nilearn.surface.load_surf_data(str(hemi_data))
        else:
            inputs[hemi] = (None, hemi_meta)
        data[hemi] = hemi_data
    return data, inputs


def _plot_surface(surf_file, meta=None, standard_surface='fsaverage6', mesh='inflated', verbose=False, colorbar_labels=None, cmap=None, cmap_bg_first=False, mesh_meta=None, **kwargs):
    """
    Plot a surface image. See :func:`make_plot`.

    Returns
    -------
    display
        The nilearn display object.
    inputs : dict
        Inputs for ``provenance.record_step``.
    parameters : dict
        Plotting parameters for ``provenance.record_step``.
    """
    parameters = {
        'standard_surface': standard_surface if isinstance(mesh, str) else None,
        'mesh': mesh if isinstance(mesh, str) else None,
        'colorbar_labels': colorbar_labels,
        'cmap': cmap,
        'cmap_bg_first': cmap_bg_first,
        **kwargs
    }

    if isinstance(mesh, str):
        with io_utils.optional_silent_print(verbose):
            fsaverage = nilearn.datasets.load_fsaverage(mesh=standard_surface)
            fsaverage_data = nilearn.datasets.load_fsaverage_data(mesh=standard_surface, data_type="sulcal", mesh_type=mesh)
            mesh = fsaverage[mesh]
        mesh_input = None
    else:
        fsaverage_data = None
        mesh_input = (None, mesh_meta)

    surface_image, inputs = _surface_inputs(surf_file, meta=meta)
    if not isinstance(surface_image, SurfaceImage):
        surface_image = SurfaceImage(mesh=mesh, data=surface_image)
    inputs['mesh'] = mesh_input

    if 'vmin' not in kwargs or 'vmax' not in kwargs:
        # Set vmin/vmax based on the data range across both hemispheres.
        data = np.concatenate([surface_image.data.parts['left'], surface_image.data.parts['right']])
        kwargs['vmin'] = kwargs.get('vmin', np.nanmin(data))
        kwargs['vmax'] = kwargs.get('vmax', np.nanmax(data))

    if isinstance(cmap, list):
        if cmap_bg_first:
            # Remove the first color (background) from the colormap so
            # that it is not used in the plot or the legend.
            cmap = cmap[1:]
        cmap = matplotlib.colors.ListedColormap(cmap)
    if cmap is not None:
        # The default value for `cmap` in `plot_surf_stat_map` is a
        # constant var so cannot pass `cmap=None` directly.
        kwargs['cmap'] = cmap

    display = nilearn.plotting.plot_surf_stat_map(
        surf_mesh=mesh,
        stat_map=surface_image,
        bg_map=fsaverage_data,
        **kwargs
    )

    vmin = kwargs['vmin']
    vmax = kwargs['vmax']
    if colorbar_labels is None:
        colorbar_labels = [str(i) for i in range(vmin, vmax + 1)]
    if 'engine' in kwargs and kwargs['engine'] == 'plotly':
        n = len(colorbar_labels)

        display.figure.update_traces(
            cmin=vmin-0.5, cmax=vmax+0.5,  # to make sure that the colors extend past labels
            colorbar=dict(
                tickvals=np.arange(vmin, n + 1),   # [1, 2, 3, ... 8]
                ticktext=colorbar_labels,
                tickfont=dict(size=35),
                tickmode='array',
            )
        )
    else:
        n = len(colorbar_labels)

        cbar_ax = display.axes[-1]
        cbar = cbar_ax._colorbar

        cbar.vmin = vmin - 0.5
        cbar.vmax = vmax + 0.5
        cbar.boundaries = np.arange(vmin - 0.5, vmax + 1.5)
        cbar._draw_all()  # needed to update the colorbar

        cbar_ax.set_ylim(vmin - 0.5, vmax + 0.5)
        cbar_ax.set_yticks(np.arange(vmin, n + 1))
        cbar_ax.set_yticklabels(colorbar_labels)
        cbar_ax.tick_params(labelsize=16)

    return display, inputs, parameters


def _plot_contrast(inputs):
    """Contrast of the projected image a plot was made from, if known."""
    surf_input = inputs.get('surface') or inputs.get('left') or (None, None)
    return provenance.last_step(surf_input[1]).get('parameters', {}).get('contrast') or 'unknown_contrast'


def make_plot(surf_file, meta=None, output_path=None, standard_surface='fsaverage6', mesh='inflated', verbose=False, colorbar_labels=None, cmap=None, cmap_bg_first=False, mesh_meta=None, **kwargs):
    """
    Create a static surface stat-map plot.

    Parameters
    ----------
    surf_file : path-like or dict
        Path to a surface image file created by :func:`project_img` or
        saved using ``io_utils.save_surface``, or a dict with
        ``'left'``/``'right'`` keys holding per-hemi GIFTI paths or
        arrays.
    meta : dict, optional
        Sidecar of ``surf_file`` (or a dict of per-hemi sidecars).
        Loaded from disk for paths if not given.
    mesh_meta : dict, optional
        Sidecar of ``mesh`` when it is an in-memory mesh.
    output_path : path-like or None, optional
        Path at which to save the plot. If ``None`` the file is saved in
        a ``plots/`` folder adjacent to the parent of ``surf_file``.
        Pass ``False`` to suppress saving.
    standard_surface : str, optional
        fsaverage mesh resolution. Default is ``'fsaverage6'``.
    surface_type : str, optional
        Surface type. Default is ``'inflated'``.
    verbose : bool, optional
        If ``True``, suppress nilearn's printed output. Default is
        ``False``.
    **kwargs
        Additional keyword arguments passed to
        ``nilearn.plotting.plot_surf_stat_map``.

    Returns
    -------
    display : nilearn.plotting.displays.SurfaceAxes
        The nilearn display object.
    meta : dict
        Sidecar of the plot.
    """
    display, inputs, parameters = _plot_surface(
        surf_file, meta=meta, standard_surface=standard_surface, mesh=mesh, verbose=verbose,
        colorbar_labels=colorbar_labels, cmap=cmap, cmap_bg_first=cmap_bg_first, mesh_meta=mesh_meta, **kwargs
    )
    contrast = _plot_contrast(inputs)

    if output_path is None:
        # Make the `plots` folder outside of the `func` folder.
        plot_folder = Path(surf_file).parent.parent / 'plots'
        output_path = plot_folder / f'{standard_surface}_{surface_type}_{contrast}.png'

    meta = provenance.record_step('analysis.make_plot', inputs=inputs, parameters=parameters, output_path=output_path)

    if output_path:
        os.makedirs(Path(output_path).parent, exist_ok=True)
        io_utils.save_figure(display, output_path, meta=meta)

    if isinstance(display, matplotlib.figure.Figure):
        plt.close(display)

    return display, meta


def make_html2(surf_file, meta=None, output_path=None, standard_surface='fsaverage6', mesh='inflated', verbose=False, atlas=None, **kwargs):
    """
    Create an interactive (plotly) HTML surface plot. Takes the same
    arguments as :func:`make_plot`.
    """
    display, inputs, parameters = _plot_surface(
        surf_file,
        meta=meta,
        standard_surface=standard_surface,
        mesh=mesh,
        verbose=verbose,
        engine='plotly',
        **kwargs
    )
    if output_path is None:
        # Make the `htmls` folder outside of the `func` folder.
        html_folder = Path(surf_file).parent.parent / 'htmls'
        output_path = html_folder / f'{standard_surface}_{surface_type}_{_plot_contrast(inputs)}.html'

    meta = provenance.record_step('analysis.make_html2', inputs=inputs, parameters=parameters, output_path=output_path)

    if output_path:
        os.makedirs(Path(output_path).parent, exist_ok=True)
        io_utils.save_figure(display, output_path, meta=meta, interactive=True)

    return display, meta


def make_html(surf_file, meta=None, output_path=None, hemi='left', standard_surface='fsaverage6', surface_type='inflated', verbose=False, **kwargs):
    """
    Create an interactive HTML surface viewer.

    The colour scale is set symmetrically around zero based on the data
    range across both hemispheres, unless ``vmin``/``vmax`` are supplied
    in ``**kwargs``.

    Parameters
    ----------
    surf_file : path-like
        Path to a surface image file created by :func:`project_img`.
    meta : dict, optional
        Sidecar of ``surf_file``. Loaded from disk if not given.
    output_path : path-like or None, optional
        Path at which to save the HTML file. If ``None`` the file is
        saved in an ``htmls/`` folder adjacent to the parent of
        ``surf_file``. Pass ``False`` to suppress saving.
    hemi : {'left', 'right'}, optional
        Hemisphere to display. Default is ``'left'``. The interactive
        viewer does not support plotting both hemispheres at once, so
        only one can be selected.
    standard_surface : str, optional
        fsaverage mesh resolution. Default is ``'fsaverage6'``.
    surface_type : str, optional
        Surface type. Default is ``'inflated'``.
    verbose : bool, optional
        If ``True``, suppress nilearn's printed output. Default is
        ``False``.
    **kwargs
        Additional keyword arguments passed to
        ``nilearn.plotting.view_surf``. ``vmin`` and ``vmax`` are set
        automatically if not provided.

    Returns
    -------
    view : nilearn.plotting.html_surface.SurfaceView
        The nilearn interactive view object.
    meta : dict
        Sidecar of the HTML file.
    """
    with io_utils.optional_silent_print(verbose):
        fsaverage = nilearn.datasets.load_fsaverage(mesh=standard_surface)
        fsaverage_data = nilearn.datasets.load_fsaverage_data(mesh=standard_surface, data_type="sulcal", mesh_type=surface_type)

    surface_image, inputs = _surface_inputs(surf_file, meta=meta)
    contrast = _plot_contrast(inputs)

    # Automatic vmin/vmax does not work that well in view_surf.
    surface_data = surface_image.data.parts
    data_max = float(np.nanmax([
        np.nanmax(np.abs(surface_data['left'])),
        np.nanmax(np.abs(surface_data['right']))
    ]))
    # Ensure that user-supplied values are not overridden.
    if 'vmin' not in kwargs:
        kwargs['vmin'] = -data_max
    if 'vmax' not in kwargs:
        kwargs['vmax'] = data_max

    view = nilearn.plotting.view_surf(
        surf_mesh=fsaverage[surface_type],
        surf_map=surface_image,
        bg_map=fsaverage_data,
        hemi=hemi,
        **kwargs
    )

    if output_path is None:
        # Make the `htmls` folder outside of the `func` folder.
        html_folder = Path(surf_file).parent.parent / 'htmls'
        output_path = html_folder / f'{standard_surface}_{surface_type}_{contrast}.html'

    meta = provenance.record_step(
        'analysis.make_html',
        inputs=inputs,
        parameters={
            'standard_surface': standard_surface,
            'surface_type': surface_type,
            'hemi': hemi,
            **kwargs
        },
        output_path=output_path
    )

    if output_path:
        os.makedirs(Path(output_path).parent, exist_ok=True)
        io_utils.save_view(view, output_path, meta=meta)

    return view, meta


def _transform_surface(coords, xfm_t1w_mni, xfm_fsnative_t1w=None, use_temp=True):
    tmpdir = os.getenv('TMPDIR', '/tmp')
    ctx = tempfile.TemporaryDirectory(dir=tmpdir) if use_temp else contextlib.nullcontext()
    with ctx as tmpdir:
        df = pd.DataFrame(coords, columns=['x', 'y', 'z'])
        df['t'] = 0
        # RAS → LPS
        df['x'] = -df['x']
        df['y'] = -df['y']
        df.to_csv(f'{tmpdir}/coords_in.csv', index=False)
    
        ants_cmd = [
            "antsApplyTransformsToPoints",
            "-d", "3",
            "-i", f"{tmpdir}/coords_in.csv",
            "-o", f"{tmpdir}/coords_out.csv",
            "-t", str(xfm_t1w_mni),
        ]
        
        if xfm_fsnative_t1w is not None:
            ants_cmd += ["-t", str(xfm_fsnative_t1w)]
        
        cmd = f"ml load {ANTS_MODULE} && " + shlex.join(ants_cmd)
    
        # This should handle setups where a login shell needs to be
        # used for lmod to work (e.g., HPC).
        subprocess.run(
            ["/bin/bash", "-lc", cmd],
            check=True
        )
    
        out = pd.read_csv(f'{tmpdir}/coords_out.csv')
        # LPS → RAS
        out['x'] = -out['x']
        out['y'] = -out['y']
    return out[['x', 'y', 'z']].values


def transform_surface_to_mni(left_surf, right_surf, xfm_t1w_mni, xfm_fsnative_t1w=None, output_path=None, meta=None):
    surf_mesh = {}
    for hemi in ('left', 'right'):
        surf = nib.load(left_surf if hemi == 'left' else right_surf)
        
        coords = surf.darrays[0].data
        faces = surf.darrays[1].data

        # ANTS warps surfaces in reverse therefore, inverse transforms
        # are needed.
        surf_mni = _transform_surface(
            coords,
            xfm_t1w_mni=xfm_t1w_mni,
            xfm_fsnative_t1w=xfm_fsnative_t1w
        )
        
        # Build InMemoryMesh objects
        surf_mesh[hemi] = nilearn.surface.surface.InMemoryMesh(surf_mni, faces)

    surf_polymesh  = nilearn.surface.surface.PolyMesh(**surf_mesh)

    meta = provenance.record_step(
        'analysis.transform_surface_to_mni',
        inputs={
            'left_surf': provenance.describe(left_surf),
            'right_surf': provenance.describe(right_surf),
            'xfm_t1w_mni': provenance.describe(xfm_t1w_mni),
            'xfm_fsnative_t1w': provenance.describe(xfm_fsnative_t1w) if xfm_fsnative_t1w is not None else None,
        },
        parameters={'tool': f'antsApplyTransformsToPoints ({ANTS_MODULE})'},
        output_path=output_path
    )

    if output_path:
        os.makedirs(Path(output_path).parent, exist_ok=True)
        surf_polymesh.to_filename(output_path)
        io_utils.save_sidecar(output_path, meta)
    
    return surf_polymesh, meta


def _resample_to_fsaverage(data_path, sphere_path, fsavg_sphere, use_temp=True):
    """
    Resample a surface texture to fsaverage using wb_command.
    fsavg_spheres: dict with 'L' and 'R' paths to fsaverage sphere GIFTI files
    (converted from FreeSurfer binary using mris_convert).
    """
    # fs_hemi = 'L' if hemi == 'left' else 'R'
    # anat_dir = Path(fmriprep_dir) / sub / ses / 'anat'

    # # Save texture as GIFTI
    # texture_path = f'/tmp/{sub}_{ses}_{fs_hemi}_texture.func.gii'
    # darray = nib.gifti.GiftiDataArray(
    #     texture.astype(np.float32),
    #     intent=nib.nifti1.intent_codes['NIFTI_INTENT_NONE'],
    # )
    # nib.gifti.GiftiImage(darrays=[darray]).to_filename(texture_path)

    # subject_sphere = str(anat_dir / f'{sub}_{ses}_hemi-{fs_hemi}_space-fsaverage_desc-reg_sphere.surf.gii')

    tmpdir = os.getenv('TMPDIR', '/tmp')
    ctx = tempfile.TemporaryDirectory(dir=tmpdir) if use_temp else contextlib.nullcontext()
    with ctx as tmpdir:

        # fsavg_out_path = f'{tmpdir}/fsaverage_sphere_reg.surf.gii'
        # cmd = f'ml load structural_imaging/freesurfer/7.4.1 && mris_convert {fsavg_sphere} {fsavg_out_path}'
        # subprocess.run(['/bin/bash', '-lc', cmd], check=True)
        # logger.info(f'Converted {fsavg_sphere} sphere to {fsavg_out_path}')

        fsavg_sphere = io_utils.unpack_gifti(fsavg_sphere, output_path=Path(tmpdir) / Path(fsavg_sphere).name.replace('.gz', ''))

        out_path = Path(tmpdir) / 'resampled.func.gii'
        wb_cmd = [
            'wb_command', '-metric-resample',
            str(data_path),
            str(sphere_path),
            str(fsavg_sphere),
            'BARYCENTRIC',
            str(out_path),
            '-largest',
        ]

        cmd = f'ml load {WB_MODULE} && ' + shlex.join(wb_cmd)
        subprocess.run(['/bin/bash', '-lc', cmd], check=True)

        # Only need vertex data not their faces/mesh info.
        coords = nib.load(str(out_path)).darrays[0].data

    return coords


def transform_surface_to_fsaverage(surf_file, surf_sphere, hemi, standard_surface='fsaverage6', output_path=None, meta=None, verbose=True):
    with io_utils.optional_silent_print(verbose):
        fsaverage_surf = nilearn.datasets.fetch_surf_fsaverage(mesh=standard_surface)
        fsavg_sphere = fsaverage_surf[f'sphere_{hemi}']
    
    surf = io_utils._get_surface_paths(surf_file, hemi='L' if hemi == 'left' else 'R', data_type='data')

    surf_fsavg = _resample_to_fsaverage(
        surf,
        surf_sphere,
        fsavg_sphere
    )

    # The per-hemi data files share the sidecar of `surf_file`.
    surf_meta = meta if meta is not None else io_utils.load_sidecar(surf_file, errors='warn')
    meta = provenance.record_step(
        'analysis.transform_surface_to_fsaverage',
        inputs={
            'surface': provenance.describe(surf, surf_meta),
            'sphere': provenance.describe(surf_sphere),
            'fsaverage_sphere': provenance.describe(fsavg_sphere),
        },
        parameters={
            'standard_surface': standard_surface,
            'hemi': hemi,
            'tool': f'wb_command -metric-resample BARYCENTRIC -largest ({WB_MODULE})'
        },
        output_path=output_path
    )

    if output_path:
        io_utils.save_gifti(surf_fsavg, path=output_path, meta=meta)

    return surf_fsavg, meta
