import contextlib
import copy
import json
import os
import pdb
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
import pdb
import pandas as pd
import subprocess
import matplotlib.pyplot as plt
import shlex

import io_utils

logger = logging.getLogger(__name__)


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
        Existing metadata dict to update with any metadata loaded from
        disk. Defaults to an empty dict.
    load_errors : {'raise', 'warn'}, optional
        How to handle loading errors. Default is ``'raise'``.

    Returns
    -------
    img : nib.Nifti1Image
        The loaded image.
    meta : dict
        Updated metadata dict.
    """
    if meta is None:
        meta = {}

    if not isinstance(img, nib.Nifti1Image):
        img, orig_meta = io_utils.load_image(img, errors=load_errors)
        meta.update(orig_meta or {})

    return img, meta


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


def _create_meta(meta, **kwargs):
    """
    Recursively build or update a metadata dictionary.

    Values that are None are not included in the updated dictionary.
    Dict values are merged recursively, allowing for nested metadata
    structures.

    Parameters
    ----------
    meta : dict or None
        Existing metadata to update. If ``None``, a new empty dict is
        created.
    **kwargs
        Key-value pairs to add. Dict values are merged recursively;
        ``None`` values (and their keys) are ignored.

    Returns
    -------
    dict
        Updated metadata dictionary.
    """
    if meta is None:
        meta = {}

    for k, v in kwargs.items():
        if isinstance(v, dict):
            meta[k] = _create_meta(meta.get(k), **v)
        elif v is not None:
            meta[k] = v
    return meta


def _correct_single_img(img, alpha=0.05, method='fdr_bh'):
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
    data = img.get_fdata()

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

    return nib.Nifti1Image(corr, affine=img.affine)


def correct_single_image(file_in, meta=None, output_path=None, alpha=0.05, method='fdr_bh', contrast_idx=None, suffix='corrected', load_errors='raise'):
    """
    Correct p-values in a single image for multiple comparisons.

    Parameters
    ----------
    file_in : path-like or nib.Nifti1Image
        Input p-value image. If a path is given the image is loaded from
        disk.
    meta : dict, optional
        Metadata to propagate. Correction parameters are appended.
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
        Updated metadata including correction parameters.
    """
    img, img_meta = _check_input_img(file_in, meta=meta, load_errors=load_errors)

    img = _select_contrast_img(img, contrast_idx=contrast_idx)
    corr_img = _correct_single_img(img, alpha=alpha, method=method)

    meta = _create_meta(
        meta,
        correction={
            'method': method,
            'alpha': alpha,
            'contrast_idx': contrast_idx
        },
        source_meta=img_meta
    )

    if output_path is None:
        output_path = _get_output_path(file_in, suffix=suffix)
    if output_path:
        io_utils.save_image(corr_img, output_path, meta=meta)

    return corr_img, meta


def correct_images(file_in, meta=None, output_path=None, alpha=0.05, method='fdr_bh', suffix='corrected', load_errors='raise'):
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
        Metadata to propagate. Correction parameters are appended.
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
        Updated metadata including correction parameters.
    """
    img, img_meta, img_dict = io_utils.load_contrasts_img(file_in, errors=load_errors)

    new_imgs = {}
    for contrast, img in img_dict.items():
        new_imgs[contrast] = _correct_single_img(img, alpha=alpha, method=method)

    # Concatenate along a new axis to create a 4D image.
    concat_img = nib.concat_images(list(new_imgs.values()))

    meta = _create_meta(
        meta,
        **img_meta,
        correction={
            'method': method,
            'alpha': alpha,
        },
        source_meta=img_meta
    )

    if output_path is None:
        output_path = _get_output_path(file_in, suffix=suffix)
    if output_path:
        io_utils.save_image(concat_img, output_path, meta=meta)

    return concat_img, meta, new_imgs


def correct_images_folder(path, meta=None, suffix='corrected', filename_contains='p_value', verbose=True, alpha=0.05, method='fdr_bh'):
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
    meta : dict, optional
        Metadata to propagate to each corrected image.
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
    contrast_idx : int, optional
        Contrast index passed to :func:`correct_single_image` for 3D
        files.
    """
    for file in Path(path).iterdir():
        if file.is_dir():
            continue

        if (filename_contains not in file.name) or (suffix in file.name) or ('.nii' not in file.suffixes):
            if verbose:
                logger.info(f'Skipping {file.relative_to(path)}')
            continue

        if nib.load(file).ndim > 3:
            corr_img, _ = correct_images(file, meta=meta, alpha=alpha, method=method, suffix=suffix, load_errors='warn')
        else:
            corr_img, _ = correct_single_image(file, meta=meta, alpha=alpha, method=method, suffix=suffix, load_errors='warn')

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
        Metadata to propagate. ROI parameters are appended.
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
        Updated metadata including ROI parameters.
    """
    img, img_meta = _check_input_img(input_path, meta=meta, load_errors=load_errors)
    img = _select_contrast_img(img, contrast_idx=contrast_idx)
    masked_img = _roi_single_img(img, regions, atlas=atlas, outside_val=outside_val)

    meta = _create_meta(
        meta,
        roi={
            'atlas': atlas,
            'regions': regions,
            'contrast_idx': contrast_idx,
            'outside_val': outside_val
        },
        source_meta=img_meta
    )

    if output_path is None:
        output_path = _get_output_path(input_path, suffix=suffix)
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
        Metadata to propagate. ROI parameters are appended.
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
        Updated metadata including ROI parameters.
    """
    img, img_meta, img_dict = io_utils.load_contrasts_img(input_path, errors=load_errors)

    new_imgs = {}
    for contrast, contrast_img in img_dict.items():
        new_imgs[contrast] = _roi_single_img(contrast_img, regions, atlas=atlas, outside_val=outside_val)

    # Concatenate along a new axis to create a 4D image.
    concat_img = nib.concat_images(list(new_imgs.values()))

    meta = _create_meta(
        meta, roi={
            'atlas': atlas,
            'regions': regions,
            'outside_val': outside_val
        },
        source_meta=img_meta
    )

    if output_path is None:
        output_path = _get_output_path(input_path, suffix=suffix)
    if output_path:
        io_utils.save_image(concat_img, output_path, meta=meta)

    return concat_img, meta, new_imgs


def _threshold_single_img(img, thresh_img, alpha=0.05, thresh_val=np.nan):
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
    return nib.Nifti1Image(masked_data, affine=img.affine)


def threshold_single_image(img_to_thresh, thresh_img, meta=None, alpha=0.05, contrast_idx=None, output_path=None, suffix='thresholded', load_errors='raise', thresh_val=np.nan):
    """
    Threshold a single image using a p-value map.

    Parameters
    ----------
    img_to_thresh : path-like or nib.Nifti1Image
        Image to threshold (e.g., a contrast estimate map).
    thresh_img : path-like or nib.Nifti1Image
        Corresponding p-value image used as the threshold mask.
    meta : dict, optional
        Metadata to propagate. Thresholding parameters are appended.
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
        Updated metadata including thresholding parameters and source
        metadata for both inputs.
    """
    est_img, est_meta = _check_input_img(img_to_thresh, meta=None, load_errors=load_errors)
    est_img = _select_contrast_img(est_img, contrast_idx=contrast_idx)

    p_img, p_meta = _check_input_img(thresh_img, meta=None, load_errors=load_errors)
    p_img = _select_contrast_img(p_img, contrast_idx=contrast_idx)

    masked_img = _threshold_single_img(est_img, p_img, alpha=alpha, thresh_val=thresh_val)

    meta = _create_meta(
        meta,
        thresholding={
            'alpha': alpha,
            'contrast_idx': contrast_idx,
            'thresh_val': thresh_val
        },
        thresholded_from_meta=est_meta,
        thresholding_meta=p_meta
    )

    if output_path is None:
        output_path = _get_output_path(img_to_thresh, suffix=suffix)
    if output_path:
        io_utils.save_image(masked_img, output_path, meta=meta)

    return masked_img, meta


def threshold_images(img_to_thresh, thresh_img, meta=None, alpha=0.05, output_path=None, suffix='thresholded', load_errors='raise', thresh_val=np.nan):
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
        Metadata to propagate. Thresholding parameters are appended.
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
        Updated metadata including thresholding parameters.

    Raises
    ------
    ValueError
        If both images are 4D but their contrast keys do not match.
    """
    est_img, est_meta, est_dict = io_utils.load_contrasts_img(img_to_thresh, errors=load_errors)
    p_img = nib.load(thresh_img)

    if p_img.ndim == 4:
        _, p_meta, p_dict = io_utils.load_contrasts_img(thresh_img, errors=load_errors)
        if set(p_dict.keys()) != set(est_dict.keys()):
            raise ValueError('Threshold image contrasts do not match target image contrasts.')
    else:
        logger.warning(f'Thresholding image {thresh_img} is 3D. Applying same threshold to all contrasts in {img_to_thresh}.')
        p_dict = {contrast: p_img for contrast in est_dict.keys()}
        p_meta = {}

    new_imgs = {}
    for contrast, est_contrast_img in est_dict.items():
        p_contrast_img = p_dict[contrast]
        new_imgs[contrast] = _threshold_single_img(est_contrast_img, p_contrast_img, alpha=alpha, thresh_val=thresh_val)

    # Concatenate along a new axis to create a 4D image.
    concat_img = nib.concat_images(list(new_imgs.values()))

    meta = _create_meta(
        meta,
        thresholding={
            'alpha': alpha,
            'thresh_val': thresh_val
        },
        thresholded_from_meta=est_meta,
        thresholding_meta=p_meta,
        volume_labels=list(est_dict.keys())
    )

    if output_path is None:
        output_path = _get_output_path(img_to_thresh, suffix=suffix)
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
    img, img_meta = _check_input_img(img, load_errors=load_errors)

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
        pdb.set_trace()
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

    meta = _create_meta(meta, argmax={
        'thresh_val': below_thresh_val,
        'outside_val': outside_roi_val,
        'no_result_idx': no_result_idx,
        'source_meta': img_meta
    })

    out_img = nib.Nifti1Image(result, affine=img.affine)

    if output_path is None:
        if img.get_filename() is None:
            logger.warning('Input image has no filename and `ouput_path` has not been provided. Cannot derive output path. Not saving output image.')
            output_path = False
        else:
            output_path = _get_output_path(img, suffix=suffix)
    if output_path:
        io_utils.save_image(out_img, output_path, meta=meta)

    return out_img, meta


def apply_over_time(img, func, mask_img=None, meta=None, output_path=None, suffix='apply', load_errors='raise', **func_kwargs):
    
    img, img_meta = _check_input_img(img, load_errors=load_errors)
    if img.ndim != 4:
        raise ValueError(f'img must be 4D, got {img.ndim}D.')
    
    if mask_img is not None:
        mask_img, _ = _check_input_img(mask_img, load_errors=load_errors)
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

    data = img.get_fdata()  # (x, y, z, t)
    data_2d = data[mask_data, :]  # (n_voxels, t)

    # voxel_data = data_2d[367420, :]
    # # Call func directly — same as apply_along_axis would
    # result = func(voxel_data, **func_kwargs)
    # pdb.set_trace()

    result_1d = np.apply_along_axis(func, axis=1, arr=data_2d, **func_kwargs)  # (n_voxels,)
    # Put back into volume
    result_3d = np.full(mask_data.shape, 0.0, dtype=np.float32)
    result_3d[mask_data] = result_1d

    result_img = nib.Nifti1Image(result_3d, img.affine, img.header)

    meta = _create_meta(meta, apply={
        'func_name': func.__name__ if hasattr(func, '__name__') else str(func),
        'func_kwargs': func_kwargs,
        'source_meta': img_meta
    })

    if output_path is None:
        if img.get_filename() is None:
            logger.warning('Input image has no filename and `ouput_path` has not been provided. Cannot derive output path. Not saving output image.')
            output_path = False
        else:
            output_path = _get_output_path(img, suffix=suffix)
    if output_path:
        io_utils.save_image(result_img, output_path, meta=meta)

    return result_img, meta


def wta(data, below_thresh_val=np.nan, outside_val=np.nan, no_result_idx=-1):
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
        outside = np.ones(data.size, dtype=bool)
    else:
        outside = np.isnan(data) if np.isnan(outside_val) else (data == outside_val)
        if outside.all():
            return 0

    below_thresh = np.isnan(data) if np.isnan(below_thresh_val) else (data == below_thresh_val)
    valid = ~outside & ~below_thresh
    if not valid.any():
        return no_result_idx
    
    # Use argmax only on the valid data (inside ROI and above threshold
    # ). Make sure to get the max index from the original data.
    valid_indices = np.where(valid)[0]
    max_valid_idx = np.argmax(data[valid_indices])
    
    return valid_indices[max_valid_idx] + 1  # +1 to reserve 0 for outside ROI


def save_as_segmentation(img, meta=None, template=None, labels=None, output_path=None, suffix='segmentation', load_errors='raise'):
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
        Metadata to propagate. Updated with ``type='segmentation'`` and
        any additional parameters passed via kwargs.
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
    img, img_meta = _check_input_img(img, load_errors=load_errors)

    out_img = nib.Nifti1Image(
        img.get_fdata().astype(np.int16),
        affine=img.affine,
        header=img.header
    )
    out_img.header.set_data_dtype(np.int16)

    if template is None:
        template = nilearn.datasets.load_mni152_template(resolution=1)

    if template:
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

    meta = _create_meta(
        meta,
        segmentation={
            'template': template.get_filename() if template else None,
            'labels': meta_labels
        },
        source_meta=img_meta
    )

    if output_path is None:
        if img.get_filename() is None:
            logger.warning('Input image has no filename and `ouput_path` has not been provided. Cannot derive output path. Not saving output image.')
            output_path = False
        else:
            output_path = _get_output_path(img, suffix=suffix)
    if output_path:
        io_utils.save_image(out_img, output_path, meta=meta)

    if labels is not None:
        labels_output_path = _get_output_path(output_path, suffix='labels', extension='.txt')
        _save_itksnap_label_description(labels, output_path=labels_output_path)

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
        r, g, b = _hex_to_rgb(color)
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


def project_image(img_to_project, contrast=None, meta=None, output_path=None, mesh='pial', standard_surface='fsaverage6', verbose=True, load_errors='raise', inner_mesh='white_matter', radius=4, n_samples=20, **kwargs):
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
        Metadata to propagate. Projection parameters are appended.
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
    **kwargs
        Additional keyword arguments passed to
        ``SurfaceImage.from_volume``.

    Returns
    -------
    surface_image : SurfaceImage
        Projected surface image.
    meta : dict
        Updated metadata including projection parameters.
    """
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

    surface_image = SurfaceImage.from_volume(
        mesh=mesh,
        volume_img=vol_img,
        inner_mesh=inner_mesh,
        radius=radius,
        n_samples=n_samples,
        **kwargs
    )
    surface_image = _remove_zeros(surface_image)

    meta = _create_meta(meta, projection={
        'standard_surface': standard_surface,
        # 'mesh': mesh,
        'contrast': contrast,
        # 'inner_mesh': inner_mesh,
        'radius': radius,
        'n_samples': n_samples,
        **kwargs
    }, projected_from_meta=vol_meta)

    if output_path is None:
        # Make the `surf` folder outside of the `func` folder.
        surf_folder = Path(img_to_project).parent.parent / 'surf'
        output_path = surf_folder / f'{standard_surface}_{surface_type}_{contrast if contrast is not None else "unknown"}.gii'

    if output_path:
        os.makedirs(Path(output_path).parent, exist_ok=True)
        io_utils.save_surface(surface_image, output_path, meta=meta)

    return surface_image, meta


def make_plot(surf_file, meta=None, output_path=None, standard_surface='fsaverage6', mesh='inflated', verbose=False, colorbar_labels=None, **kwargs):
    """
    Create a static surface stat-map plot.

    Parameters
    ----------
    surf_file : path-like
        Path to a surface image file created by :func:`project_img` or
        saved using ``io_utils.save_surface``.
    meta : dict, optional
        Metadata to propagate. Plotting parameters are appended.
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
        Updated metadata including plotting parameters.
    """
    if isinstance(mesh, str):
        with io_utils.optional_silent_print(verbose):
            fsaverage = nilearn.datasets.load_fsaverage(mesh=standard_surface)
            fsaverage_data = nilearn.datasets.load_fsaverage_data(mesh=standard_surface, data_type="sulcal", mesh_type=mesh)
            mesh = fsaverage[mesh]
    else:
        fsaverage_data = None

    surface_image, surf_meta = io_utils.load_surface(surf_file)
    contrast = surf_meta.get('projection', {}).get('contrast', 'unknown_contrast')
    display = nilearn.plotting.plot_surf_stat_map(
        surf_mesh=mesh,
        stat_map=surface_image,
        bg_map=fsaverage_data,
        **kwargs
    )

    if 'engine' in kwargs and kwargs['engine'] == 'plotly':
        # TODO: Handle labels being None.
        n = len(colorbar_labels)

        # TODO: cmin and cmax should be set based on vmin/vmax (see 
        # nilearn.plotting._utils.get_colorbar_and_data_ranges).
        display.figure.update_traces(
            cmin=0.5, cmax=8.5,
            colorbar=dict(
                tickvals=np.arange(1, n + 1),   # [1, 2, 3, ... 8]
                ticktext=colorbar_labels,
                tickfont=dict(size=35),
                tickmode='array',
            )
        )
    else:
        # TODO: Handle labels being None.
        n = len(colorbar_labels)
        cbar_ax = display.axes[-1]
        cbar_ax.set_yticks(np.arange(1, n + 1))
        cbar_ax.set_yticklabels(colorbar_labels)
        cbar_ax.tick_params(labelsize=28)

    meta = _create_meta(meta, plotting={
        'standard_surface': standard_surface,
        # 'surface_type': surface_type,
        'contrast': contrast,
        # **kwargs
    })

    if output_path is None:
        # Make the `plots` folder outside of the `func` folder.
        plot_folder = Path(surf_file).parent.parent / 'plots'
        # output_path = plot_folder / f'{standard_surface}_{surface_type}_{contrast}.png'

    if output_path:
        os.makedirs(Path(output_path).parent, exist_ok=True)
        io_utils.save_figure(display, output_path, meta=meta)

    # if isinstance(display, matplotlib.figure.Figure):
    #     plt.close(display)

    return display, meta


def make_html2(surf_file, meta=None, output_path=None, standard_surface='fsaverage6', mesh='inflated', verbose=False, atlas=None, **kwargs):
    display, meta = make_plot(
        surf_file=surf_file,
        meta=meta,
        output_path=False,  # Don't save the static plot.
        standard_surface=standard_surface,
        mesh=mesh,
        verbose=verbose,
        engine='plotly',
        **kwargs
    )
    if output_path is None:
        # Make the `htmls` folder outside of the `func` folder.
        html_folder = Path(surf_file).parent.parent / 'htmls'
        contrast = meta.get('plotting', {}).get('contrast', 'unknown_contrast')
        # output_path = html_folder / f'{standard_surface}_{surface_type}_{contrast}.html'

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
        Metadata to propagate. View parameters are appended.
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
        Updated metadata including view parameters.
    """
    with io_utils.optional_silent_print(verbose):
        fsaverage = nilearn.datasets.load_fsaverage(mesh=standard_surface)
        fsaverage_data = nilearn.datasets.load_fsaverage_data(mesh=standard_surface, data_type="sulcal", mesh_type=surface_type)

    surface_image, surf_meta = io_utils.load_surface(surf_file)
    contrast = surf_meta.get('projection', {}).get('contrast', 'unknown_contrast')

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
        source_meta=surf_meta,
        **kwargs
    )

    meta = _create_meta(meta, view={
        'standard_surface': standard_surface,
        'surface_type': surface_type,
        'contrast': contrast,
        'hemi': hemi,
        **kwargs
    })

    if output_path is None:
        # Make the `htmls` folder outside of the `func` folder.
        html_folder = Path(surf_file).parent.parent / 'htmls'
        output_path = html_folder / f'{standard_surface}_{surface_type}_{contrast}.html'

    if output_path:
        os.makedirs(Path(output_path).parent, exist_ok=True)
        io_utils.save_view(view, output_path, meta=meta)

    return view, meta


def _transform_surface(coords, xfm_t1w_mni, xfm_fsnative_t1w=None, use_temp=True):
    tmpdir = os.getenv('TMPDIR', '/scratch/user/uqmtoth/code/bodymaps/tmp')
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
        
        cmd = "ml load ants/2.6.0 && " + shlex.join(ants_cmd)
    
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
        surf_mesh[hemi] = nilearn.surface.surface.InMemoryMesh(surf_mni,  faces)

    surf_polymesh  = nilearn.surface.surface.PolyMesh(**surf_mesh)

    meta = _create_meta(
        meta,
        transform={
            'xfm_t1w_mni': xfm_t1w_mni,
            'xfm_fsnative_t1w': xfm_fsnative_t1w
        },
        source={
            'left': left_surf,
            'right': right_surf
        }
    )

    if output_path:
        os.makedirs(Path(output_path).parent, exist_ok=True)
        surf_polymesh.to_filename(output_path)

        json_meta_path = Path(output_path).with_suffix('.json')
        with open(json_meta_path, 'w') as f:
            json.dump(meta, f, indent=2, cls=io_utils.PathEncoder)
    
    return surf_polymesh, meta
