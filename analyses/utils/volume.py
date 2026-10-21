"""
Volumetric processing of statistical maps: multiple-comparison
correction, thresholding, ROI masking, winner-take-all and
segmentations.
"""
import contextlib
import logging
import tempfile
import warnings
from pathlib import Path

import nibabel as nib
import nilearn.datasets
import nilearn.image
import numpy as np
from statsmodels.stats.multitest import multipletests

import io_utils
import provenance
from _common import (
    _atlas_input,
    _check_input_img,
    _prepare_mask,
    _select_contrast_img,
)

logger = logging.getLogger(__name__)


def _correct_single_img(img, alpha=0.05, method='fdr_bh', mask_data=None):
    """
    Apply multiple-comparison correction to a p-value image.

    NaN voxels and voxels outside the mask are excluded from the
    correction. NaN voxels stay NaN; voxels outside the mask are set to
    ``0``.

    Parameters
    ----------
    img : nib.Nifti1Image
        3D image of uncorrected p-values.
    alpha : float, optional
        Error rate passed to ``multipletests`` (FDR for ``'fdr_*'``
        methods, FWER otherwise). Default is ``0.05``.
    method : str, optional
        Correction method passed to
        ``statsmodels.stats.multitest.multipletests``. Default is
        ``'fdr_bh'`` (Benjamini-Hochberg FDR).
    mask_data : np.ndarray, optional
        Boolean (x, y, z) array; only voxels where it is ``True`` are
        corrected. Default is to use all voxels.

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
        Sidecar of ``file_in``. Required to keep the provenance of
        in-memory images; loaded from disk for paths if not given.
    output_path : path-like or None, optional
        Path at which to save the corrected image. If ``None`` a default
        path is derived from ``file_in`` and ``suffix``. Pass ``False``
        to suppress saving.
    mask_img : path-like or nib.Nifti1Image, optional
        Brain mask. Only voxels inside it are corrected; voxels outside
        are set to ``0``. Resampled to ``file_in`` if needed.
    alpha : float, optional
        Error rate (FDR for ``'fdr_*'`` methods, FWER otherwise).
        Default is ``0.05``.
    method : str, optional
        Correction method passed to ``multipletests``. Default is
        ``'fdr_bh'``.
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
        output_path = io_utils.get_output_path(file_in, suffix=suffix)

    meta = provenance.record_step(
        'volume.correct_single_image',
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
        Path to a 4D image whose volumes are labelled by
        ``volume_labels`` in its sidecar.
    meta : dict, optional
        Sidecar of ``file_in``. Loaded from disk if not given.
    output_path : path-like or None, optional
        Path at which to save the corrected 4D image. If ``None`` a
        default path is derived from ``file_in`` and ``suffix``. Pass
        ``False`` to suppress saving.
    mask_img : path-like or nib.Nifti1Image, optional
        Brain mask. Only voxels inside it are corrected; voxels outside
        are set to ``0``. Resampled to ``file_in`` if needed.
    alpha : float, optional
        Error rate (FDR for ``'fdr_*'`` methods, FWER otherwise).
        Default is ``0.05``.
    method : str, optional
        Correction method passed to ``multipletests``. Default is
        ``'fdr_bh'``.
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
    new_imgs : dict
        Mapping of contrast label to its corrected 3D image.
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
        output_path = io_utils.get_output_path(file_in, suffix=suffix)

    meta = provenance.record_step(
        'volume.correct_images',
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
    name contains ``suffix``) are skipped. Loading errors are logged as
    warnings.

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
        Error rate (FDR for ``'fdr_*'`` methods, FWER otherwise).
        Default is ``0.05``.
    method : str, optional
        Correction method. Default is ``'fdr_bh'``.
    mask_img : path-like or nib.Nifti1Image, optional
        Brain mask used for every file. If not provided, all voxels are
        included in the correction (including voxels outside of the
        brain).
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
    atlas : str or path-like, optional
        nilearn atlas name or path to a NIfTI atlas, see
        :func:`get_roi_mask`. Default is ``'destrieux_2009'``.
    outside_val : float, optional
        Value given to voxels outside the ROI. Default is NaN.

    Returns
    -------
    nib.Nifti1Image
        Image with voxels outside the ROI set to ``outside_val``.
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
            # Either use a temp directory or use None (which defaults
            # to nilearn's caching directory).
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
    atlas : str or path-like, optional
        nilearn atlas name or path to a NIfTI atlas, see
        :func:`get_roi_mask`. Default is ``'destrieux_2009'``.
    output_path : path-like or None, optional
        Path at which to save the masked image. If ``None`` a default
        path is derived from ``input_path`` and ``suffix``. Pass
        ``False`` to suppress saving.
    suffix : str, optional
        Suffix appended to the filename when generating a default output
        path. Default is ``'roi'``.
    load_errors : {'raise', 'warn'}, optional
        How to handle loading errors. Default is ``'raise'``.
    outside_val : float, optional
        Value given to voxels outside the ROI. Default is NaN.

    Returns
    -------
    masked_img : nib.Nifti1Image
        3D image with voxels outside the ROI set to ``outside_val``.
    meta : dict
        Sidecar of the masked image.
    """
    img, img_input = _check_input_img(input_path, meta=meta, load_errors=load_errors)
    img = _select_contrast_img(img, contrast_idx=contrast_idx)
    masked_img = _roi_single_img(img, regions, atlas=atlas, outside_val=outside_val)

    if output_path is None:
        output_path = io_utils.get_output_path(input_path, suffix=suffix)

    atlas_input = _atlas_input(atlas)
    meta = provenance.record_step(
        'volume.roi_single_image',
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
        Path to a 4D image whose volumes are labelled by
        ``volume_labels`` in its sidecar.
    regions : list of str
        Atlas region names to retain.
    meta : dict, optional
        Sidecar of ``input_path``. Loaded from disk if not given.
    atlas : str or path-like, optional
        nilearn atlas name or path to a NIfTI atlas, see
        :func:`get_roi_mask`. Default is ``'destrieux_2009'``.
    output_path : path-like or None, optional
        Path at which to save the masked 4D image. If ``None`` a default
        path is derived from ``input_path`` and ``suffix``. Pass
        ``False`` to suppress saving.
    suffix : str, optional
        Suffix appended to the filename when generating a default output
        path. Default is ``'roi'``.
    load_errors : {'raise', 'warn'}, optional
        How to handle loading errors. Default is ``'raise'``.
    outside_val : float, optional
        Value given to voxels outside the ROI. Default is NaN.

    Returns
    -------
    concat_img : nib.Nifti1Image
        4D masked image with contrasts concatenated in the same order as
        the input.
    meta : dict
        Sidecar of the masked image.
    new_imgs : dict
        Mapping of contrast label to its masked 3D image.
    """
    img, img_meta, img_dict = io_utils.load_contrasts_img(input_path, errors=load_errors)
    img_input = provenance.describe(input_path, meta if meta is not None else img_meta)

    new_imgs = {}
    for contrast, contrast_img in img_dict.items():
        new_imgs[contrast] = _roi_single_img(contrast_img, regions, atlas=atlas, outside_val=outside_val)

    # Concatenate along a new axis to create a 4D image.
    concat_img = nib.concat_images(list(new_imgs.values()))

    if output_path is None:
        output_path = io_utils.get_output_path(input_path, suffix=suffix)

    atlas_input = _atlas_input(atlas)
    meta = provenance.record_step(
        'volume.roi_images',
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

    Voxels where the p-value exceeds ``alpha`` are set to ``thresh_val``
    and voxels outside the mask are set to ``0``.

    Parameters
    ----------
    img : nib.Nifti1Image
        Image to threshold (e.g. a z-score map).
    thresh_img : nib.Nifti1Image
        Corresponding p-value image with the same shape as ``img``.
    alpha : float, optional
        Significance threshold. Default is ``0.05``.
    thresh_val : float, optional
        Value given to voxels above ``alpha``. Default is NaN.
    mask_data : np.ndarray, optional
        Boolean (x, y, z) array; voxels where it is ``False`` are set to
        ``0``. Default is no masking.

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
        Image to threshold (e.g. a z-score map).
    thresh_img : path-like or nib.Nifti1Image
        Corresponding p-value image used as the threshold mask. Its
        sidecar is loaded from disk if it is a path.
    meta : dict, optional
        Sidecar of ``img_to_thresh``. Required to keep the provenance of
        in-memory images; loaded from disk for paths if not given.
    alpha : float, optional
        Significance threshold. Default is ``0.05``.
    contrast_idx : int, optional
        Index of the contrast to threshold when the inputs are 4D.
    output_path : path-like or None, optional
        Path at which to save the thresholded image. If ``None`` a
        default path is derived from ``img_to_thresh`` and ``suffix``.
        Pass ``False`` to suppress saving.
    suffix : str, optional
        Suffix appended to the filename when generating a default output
        path. Default is ``'thresholded'``.
    load_errors : {'raise', 'warn'}, optional
        How to handle loading errors. Default is ``'raise'``.
    thresh_val : float, optional
        Value given to voxels above ``alpha``. Default is NaN.
    mask_img : path-like or nib.Nifti1Image, optional
        Brain mask; voxels outside it are set to ``0``. Resampled to
        ``img_to_thresh`` if needed.

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
        output_path = io_utils.get_output_path(img_to_thresh, suffix=suffix)

    meta = provenance.record_step(
        'volume.threshold_single_image',
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
        Path to a 4D image to threshold (e.g. z-score maps), with
        ``volume_labels`` in its sidecar.
    thresh_img : path-like
        Path to the p-value image used as the threshold mask. May be 3D
        (applied to all contrasts) or 4D (matched per contrast label).
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
    thresh_val : float, optional
        Value given to voxels above ``alpha``. Default is NaN.
    mask_img : path-like or nib.Nifti1Image, optional
        Brain mask; voxels outside it are set to ``0``. Resampled to
        ``img_to_thresh`` if needed.

    Returns
    -------
    concat_img : nib.Nifti1Image
        4D thresholded image with contrasts in the same order as the
        input.
    meta : dict
        Sidecar of the thresholded image.
    new_imgs : dict
        Mapping of contrast label to its thresholded 3D image.

    Raises
    ------
    ValueError
        If both images are 4D but their contrast labels do not match.
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
        output_path = io_utils.get_output_path(img_to_thresh, suffix=suffix)

    meta = provenance.record_step(
        'volume.threshold_images',
        inputs={'img': est_input, 'thresh_img': p_input, 'mask': mask_input},
        parameters={'alpha': alpha, 'thresh_val': thresh_val},
        output_path=output_path,
        fields={'volume_labels': list(new_imgs.keys())}
    )

    if output_path:
        io_utils.save_image(concat_img, output_path, meta=meta)

    return concat_img, meta, new_imgs


def apply_across_volumes(img, func, mask_img=None, meta=None, output_path=None, suffix='apply', load_errors='raise', **func_kwargs):
    """
    Apply a function to the 4th-dimension values of every voxel.

    ``func`` is called once per voxel inside the mask with a 1D array of
    that voxel's values (e.g. one per contrast) and must return a
    scalar. Voxels outside the mask are set to ``0``.

    Parameters
    ----------
    img : path-like or nib.Nifti1Image
        4D input image.
    func : callable
        Function mapping a 1D array to a scalar, e.g. :func:`wta`.
    mask_img : path-like or nib.Nifti1Image, optional
        Brain mask. Resampled to ``img`` if needed. Default is to use
        all voxels.
    meta : dict, optional
        Sidecar of ``img``. Required to keep the provenance of in-memory
        images; loaded from disk for paths if not given.
    output_path : path-like or None, optional
        Path at which to save the result. If ``None`` a default path is
        derived from the filename of ``img`` and ``suffix`` (nothing is
        saved if ``img`` has no filename). Pass ``False`` to suppress
        saving.
    suffix : str, optional
        Suffix appended to the filename when generating a default output
        path. Default is ``'apply'``.
    load_errors : {'raise', 'warn'}, optional
        How to handle loading errors. Default is ``'raise'``.
    **func_kwargs
        Keyword arguments passed to ``func``.

    Returns
    -------
    result_img : nib.Nifti1Image
        3D float32 image of ``func`` results.
    meta : dict
        Sidecar of the result.

    Raises
    ------
    ValueError
        If ``img`` is not 4D.
    """
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
            output_path = io_utils.get_output_path(img, suffix=suffix)

    meta = provenance.record_step(
        'volume.apply_across_volumes',
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
        'volume.concat_images',
        inputs={lab: provenance.describe(img, img_meta) for lab, img, img_meta in zip(labels, imgs, metas)},
        output_path=output_path,
        fields={'volume_labels': list(labels)}
    )

    if output_path:
        io_utils.save_image(concat_img, output_path, meta=meta)

    return concat_img, meta


def wta(data, below_thresh_val=np.nan, outside_val=np.nan, no_result_idx=-1, only_positive=True):
    """
    Winner-take-all function to be applied with
    :func:`apply_across_volumes`.

    Returns the 1-based index of the largest valid value, so that ``0``
    can be used for outside the ROI. A value is valid if it is neither
    ``outside_val`` nor ``below_thresh_val`` and, if ``only_positive``,
    is not negative.

    Parameters
    ----------
    data : 1D array-like
        Values for a single voxel across contrasts.
    below_thresh_val : float, optional
        Sentinel value indicating a below-threshold contrast. NaN by
        default (NaN-aware comparison is used).
    outside_val : float, optional
        Sentinel value indicating an outside-ROI voxel. NaN by default.
        If both sentinels are NaN they cannot be told apart and all NaNs
        are treated as below threshold.
    no_result_idx : int, optional
        Value returned when the voxel is inside the ROI but has no valid
        value. Default is ``-1``.
    only_positive : bool, optional
        If ``True``, negative values are not considered valid. Default
        is ``True``.

    Returns
    -------
    int
        ``0`` if all values are ``outside_val`` or the valid values sum
        to zero (indicates that they are all background voxels),
        ``no_result_idx`` if no value is valid, otherwise the index of
        the largest valid value plus one.
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
    Save an image as an integer segmentation.

    The data are cast to int16 and resampled with nearest-neighbour
    interpolation onto ``template``. If ``labels`` are given they are
    stored in the sidecar and an ITK-SNAP label description file
    (``<output>_labels.txt``) is written next to the image.

    Parameters
    ----------
    img : path-like or nib.Nifti1Image
        Image to save as a segmentation. If a path is given, the image
        is loaded from disk.
    meta : dict, optional
        Sidecar of ``img``. Required to keep the provenance of in-memory
        images.
    template : path-like, nib.Nifti1Image or False, optional
        Image defining the output grid. Defaults to the 1mm MNI152
        template from nilearn. Pass ``False`` to keep the input grid.
    labels : dict or list, optional
        Label names, either a mapping of label value to name or a list
        indexed by label value.
    output_path : path-like or None, optional
        Path at which to save the segmentation image. If ``None`` a
        default path is derived from the filename of ``img`` and
        ``suffix`` (nothing is saved if ``img`` has no filename). Pass
        ``False`` to suppress saving.
    suffix : str, optional
        Suffix appended to the filename when generating a default output
        path. Default is ``'segmentation'``.
    load_errors : {'raise', 'warn'}, optional
        How to handle loading errors. Default is ``'raise'``.
    color_palette : dict or callable, optional
        Colours for the label description file, as a mapping of label
        name to colour or a function of the label name. Colours are hex
        strings or RGBA tuples in 0-1. Labels without a colour get one
        from a default palette.

    Returns
    -------
    out_img : nib.Nifti1Image
        The segmentation image.
    meta : dict
        Sidecar of the segmentation.
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
            output_path = io_utils.get_output_path(img, suffix=suffix)

    labels_output_path = None
    if labels is not None and output_path:
        labels_output_path = io_utils.get_output_path(output_path, suffix='labels', extension='.txt')

    meta = provenance.record_step(
        'volume.save_as_segmentation',
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
    """
    Write an ITK-SNAP label description file.

    Parameters
    ----------
    labels : dict or list
        Mapping of label value to name (or to ``(name, colour)``), or a
        list of names indexed by label value.
    output_path : path-like, optional
        Where to write the file. If not given, nothing is written.
    color_palette : dict or callable, optional
        Colours for labels given without one, as a mapping of label name
        to colour or a function of the label name. Colours are hex
        strings or RGBA tuples in 0-1. Labels without a colour get one
        from a default palette.

    Returns
    -------
    dict
        Mapping of label value to ``(name, colour)``.
    """
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
