"""
Volumetric processing of statistical maps: multiple-comparison
correction, thresholding, ROI masking, winner-take-all and
segmentations.

See ``_common`` for the conventions all public functions follow.
"""
import contextlib
import logging
import os
import tempfile
import warnings
from pathlib import Path

import nibabel as nib
import nilearn.datasets
import nilearn.image
import numpy as np
from scipy import ndimage
from statsmodels.stats.multitest import multipletests

import io_utils
import provenance
from _common import (
    _atlas_input,
    _check_contrasts_img,
    _check_input_img,
    _labels,
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
    data = img.get_fdata(caching='unchanged').copy()
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


def correct_single_image(img, meta=None, output_path=None, mask_img=None, alpha=0.05, method='fdr_bh', contrast_idx=None, load_errors='raise'):
    """
    Correct p-values in a single image for multiple comparisons.

    Parameters
    ----------
    img : path-like or nib.Nifti1Image
        Input p-value image, 3D or 4D (see ``contrast_idx``).
    meta : dict, optional
        Sidecar of ``img``. Required to keep the provenance of in-memory
        images; loaded from disk for paths if not given.
    output_path : path-like, optional
        Path at which to save the corrected image. Not saved if not
        given.
    mask_img : path-like or nib.Nifti1Image, optional
        Brain mask. Only voxels inside it are corrected; voxels outside
        are set to ``0``. Resampled to ``img`` if needed.
    alpha : float, optional
        Error rate (FDR for ``'fdr_*'`` methods, FWER otherwise).
        Default is ``0.05``.
    method : str, optional
        Correction method passed to ``multipletests``. Default is
        ``'fdr_bh'``.
    contrast_idx : int, optional
        Index of the contrast to correct when ``img`` is 4D.
    load_errors : {'raise', 'warn'}, optional
        How to handle loading errors. Default is ``'raise'``.

    Returns
    -------
    corr_img : nib.Nifti1Image
        Corrected p-value image.
    meta : dict
        Sidecar of the corrected image.
    """
    img, img_input = _check_input_img(img, meta=meta, load_errors=load_errors)

    img = _select_contrast_img(img, contrast_idx=contrast_idx)
    mask_data, mask_input = _prepare_mask(img, mask_img=mask_img, load_errors=load_errors)
    corr_img = _correct_single_img(img, alpha=alpha, method=method, mask_data=mask_data)

    meta = provenance.record_step(
        'volume.correct_single_image',
        inputs={'p_values': img_input, 'mask': mask_input},
        parameters={'method': method, 'alpha': alpha, 'contrast_idx': contrast_idx},
        output_path=output_path
    )

    if output_path:
        io_utils.save_image(corr_img, output_path, meta=meta)

    return corr_img, meta


def correct_images(img, meta=None, output_path=None, mask_img=None, alpha=0.05, method='fdr_bh', load_errors='raise'):
    """
    Correct p-values for multiple comparisons across all contrasts in a
    4D image.

    Each contrast volume is corrected independently.

    Parameters
    ----------
    img : path-like or nib.Nifti1Image
        4D p-value image whose volumes are labelled by ``volume_labels``
        in its sidecar.
    meta : dict, optional
        Sidecar of ``img``. Required for in-memory images; loaded from
        disk for paths if not given.
    output_path : path-like, optional
        Path at which to save the corrected 4D image. Not saved if not
        given.
    mask_img : path-like or nib.Nifti1Image, optional
        Brain mask. Only voxels inside it are corrected; voxels outside
        are set to ``0``. Resampled to ``img`` if needed.
    alpha : float, optional
        Error rate (FDR for ``'fdr_*'`` methods, FWER otherwise).
        Default is ``0.05``.
    method : str, optional
        Correction method passed to ``multipletests``. Default is
        ``'fdr_bh'``.
    load_errors : {'raise', 'warn'}, optional
        How to handle loading errors. Default is ``'raise'``.

    Returns
    -------
    corr_img : nib.Nifti1Image
        4D image of corrected p-values, contrasts in the same order as
        the input.
    meta : dict
        Sidecar of the corrected image.
    """
    img_dict, img_input = _check_contrasts_img(img, meta=meta, load_errors=load_errors)

    new_imgs = {}
    for contrast, contrast_img in img_dict.items():
        mask_data, mask_input = _prepare_mask(contrast_img, mask_img=mask_img, load_errors=load_errors)
        new_imgs[contrast] = _correct_single_img(contrast_img, alpha=alpha, method=method, mask_data=mask_data)

    # Concatenate along a new axis to create a 4D image.
    corr_img = nib.concat_images(list(new_imgs.values()))

    meta = provenance.record_step(
        'volume.correct_images',
        inputs={'p_values': img_input, 'mask': mask_input},
        parameters={'method': method, 'alpha': alpha},
        output_path=output_path,
        fields={'volume_labels': list(new_imgs.keys())}
    )

    if output_path:
        io_utils.save_image(corr_img, output_path, meta=meta)

    return corr_img, meta


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

        output_path = io_utils.get_output_path(file, suffix=suffix)
        if nib.load(file).ndim > 3:
            correct_images(file, output_path=output_path, alpha=alpha, method=method, load_errors='warn', mask_img=mask_img)
        else:
            correct_single_image(file, output_path=output_path, alpha=alpha, method=method, load_errors='warn', mask_img=mask_img)

        if verbose:
            logger.info(f'Corrected {file.relative_to(path)} -> {Path(output_path).relative_to(path)}')


def invert_image(img, kind, meta=None, output_path=None, load_errors='raise'):
    """
    Invert z-scores or one-sided p-values, to test the opposite
    direction of a contrast (e.g. deactivation instead of activation).

    nilearn's p-values are one-sided (``p = sf(z)``), so the z-scores
    and the p-values of a contrast both need inverting for the negated
    contrast: z becomes ``-z`` and p becomes ``1 - p``.

    Parameters
    ----------
    img : path-like or nib.Nifti1Image
        3D or 4D image of z-scores or p-values.
    kind : {'z', 'p'}
        ``'z'`` negates the values; ``'p'`` returns ``1 - p``.
    meta : dict, optional
        Sidecar of ``img``. Required to keep the provenance of in-memory
        images; loaded from disk for paths if not given.
    output_path : path-like, optional
        Path at which to save the inverted image. Not saved if not
        given.
    load_errors : {'raise', 'warn'}, optional
        How to handle loading errors. Default is ``'raise'``.

    Returns
    -------
    inverted_img : nib.Nifti1Image
        The inverted image.
    meta : dict
        Its sidecar. ``volume_labels`` recorded for ``img`` are carried
        over.

    Raises
    ------
    ValueError
        If ``kind`` is not ``'z'`` or ``'p'``.
    """
    if kind not in ('z', 'p'):
        raise ValueError(f"`kind` must be 'z' or 'p', got {kind!r}.")
    img, img_input = _check_input_img(img, meta=meta, load_errors=load_errors)

    data = img.get_fdata(caching='unchanged')
    inverted_data = -data if kind == 'z' else 1.0 - data
    inverted_img = nib.Nifti1Image(inverted_data, affine=img.affine)

    meta = provenance.record_step(
        'volume.invert_image',
        inputs={'img': img_input},
        parameters={'kind': kind},
        output_path=output_path,
        fields={'volume_labels': (img_input[1] or {}).get('volume_labels')}
    )

    if output_path:
        io_utils.save_image(inverted_img, output_path, meta=meta)

    return inverted_img, meta


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
    img_data = img.get_fdata(caching='unchanged')
    mask_data = mask.get_fdata(caching='unchanged')
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


def roi_single_image(img, regions, meta=None, contrast_idx=None, atlas='destrieux_2009', output_path=None, load_errors='raise', outside_val=np.nan):
    """
    Apply an atlas-based ROI mask to a single image.

    Parameters
    ----------
    img : path-like or nib.Nifti1Image
        Input image to mask, 3D or 4D (see ``contrast_idx``).
    regions : list of str
        Atlas region names to retain.
    meta : dict, optional
        Sidecar of ``img``. Required to keep the provenance of in-memory
        images; loaded from disk for paths if not given.
    contrast_idx : int, optional
        Index of the contrast to mask when ``img`` is 4D.
    atlas : str or path-like, optional
        nilearn atlas name or path to a NIfTI atlas, see
        :func:`get_roi_mask`. Default is ``'destrieux_2009'``.
    output_path : path-like, optional
        Path at which to save the masked image. Not saved if not given.
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
    img, img_input = _check_input_img(img, meta=meta, load_errors=load_errors)
    img = _select_contrast_img(img, contrast_idx=contrast_idx)
    masked_img = _roi_single_img(img, regions, atlas=atlas, outside_val=outside_val)

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


def roi_images(img, regions, meta=None, atlas='destrieux_2009', output_path=None, load_errors='raise', outside_val=np.nan):
    """
    Apply the same atlas-based ROI mask to all contrasts in a 4D image.

    See :func:`roi_per_contrast` for a different ROI per contrast.

    Parameters
    ----------
    img : path-like or nib.Nifti1Image
        4D image whose volumes are labelled by ``volume_labels`` in its
        sidecar.
    regions : list of str
        Atlas region names to retain.
    meta : dict, optional
        Sidecar of ``img``. Required for in-memory images; loaded from
        disk for paths if not given.
    atlas : str or path-like, optional
        nilearn atlas name or path to a NIfTI atlas, see
        :func:`get_roi_mask`. Default is ``'destrieux_2009'``.
    output_path : path-like, optional
        Path at which to save the masked 4D image. Not saved if not
        given.
    load_errors : {'raise', 'warn'}, optional
        How to handle loading errors. Default is ``'raise'``.
    outside_val : float, optional
        Value given to voxels outside the ROI. Default is NaN.

    Returns
    -------
    masked_img : nib.Nifti1Image
        4D masked image with contrasts in the same order as the input.
    meta : dict
        Sidecar of the masked image.
    """
    img_dict, img_input = _check_contrasts_img(img, meta=meta, load_errors=load_errors)

    new_imgs = {}
    for contrast, contrast_img in img_dict.items():
        new_imgs[contrast] = _roi_single_img(contrast_img, regions, atlas=atlas, outside_val=outside_val)

    # Concatenate along a new axis to create a 4D image.
    masked_img = nib.concat_images(list(new_imgs.values()))

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
        io_utils.save_image(masked_img, output_path, meta=meta)

    return masked_img, meta


def roi_per_contrast(img, contrast_regions, atlas, meta=None, output_path=None, load_errors='raise', outside_val=np.nan):
    """
    Mask selected contrasts of a 4D image, each with its own atlas
    regions, and stack them into a new 4D image.

    Parameters
    ----------
    img : path-like or nib.Nifti1Image
        4D image whose volumes are labelled by ``volume_labels`` in its
        sidecar.
    contrast_regions : dict
        Mapping of contrast label to the atlas region names to retain
        for it. Only these contrasts are kept, in this order.
    atlas : str or path-like
        nilearn atlas name or path to a NIfTI atlas, see
        :func:`get_roi_mask`.
    meta : dict, optional
        Sidecar of ``img``. Required for in-memory images; loaded from
        disk for paths if not given.
    output_path : path-like, optional
        Path at which to save the 4D image. Not saved if not given.
    load_errors : {'raise', 'warn'}, optional
        How to handle loading errors. Default is ``'raise'``.
    outside_val : float, optional
        Value given to voxels outside each contrast's regions. Default
        is NaN.

    Returns
    -------
    masked_img : nib.Nifti1Image
        4D image with one volume per contrast in ``contrast_regions``.
    meta : dict
        Its sidecar, with the contrasts as ``volume_labels``.
    """
    img, img_input = _check_input_img(img, meta=meta, load_errors=load_errors)
    labels = img_input[1]['volume_labels']
    masked = [
        roi_single_image(img, regions=regions, meta=img_input[1], contrast_idx=labels.index(contrast),
                         atlas=atlas, outside_val=outside_val)
        for contrast, regions in contrast_regions.items()
    ]
    return concat_images([m[0] for m in masked], metas=[m[1] for m in masked],
                         labels=list(contrast_regions), output_path=output_path)


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
    img_data = img.get_fdata(caching='unchanged')
    thresh_data = thresh_img.get_fdata(caching='unchanged')
    mask = thresh_data <= alpha
    masked_data = np.where(mask, img_data, thresh_val)
    if mask_data is not None:
        masked_data[np.invert(mask_data)] = 0.0  # Set voxels outside the mask to a background value.
    return nib.Nifti1Image(masked_data, affine=img.affine)


def _threshold_top_percent_img(img, top_percent, thresh_val=np.nan, mask_data=None):
    """
    Threshold an image by keeping its largest values.

    The cutoff is the ``100 - top_percent`` percentile of the image's
    finite values inside the mask. Voxels at or above it keep their
    value (with ties at the cutoff slightly more than ``top_percent``
    can be kept); the others are set to ``thresh_val``, and voxels
    outside the mask to ``0``.

    Parameters
    ----------
    img : nib.Nifti1Image
        Image to threshold (e.g. a z-score map).
    top_percent : float
        Percentage of voxels to keep, in (0, 100].
    thresh_val : float, optional
        Value given to voxels below the cutoff. Default is NaN.
    mask_data : np.ndarray, optional
        Boolean (x, y, z) array; only voxels where it is ``True`` count
        towards the percentage, and the others are set to ``0``. Default
        is to use all voxels.

    Returns
    -------
    thresholded_img : nib.Nifti1Image
        Thresholded image with the same affine as ``img``.
    cutoff : float
        The value at the cutoff.

    Raises
    ------
    ValueError
        If ``top_percent`` is not in (0, 100], or there are no finite
        values inside the mask.
    """
    if not 0 < top_percent <= 100:
        raise ValueError(f'`top_percent` must be in (0, 100], got {top_percent}.')
    img_data = img.get_fdata(caching='unchanged')
    inside = np.isfinite(img_data)
    if mask_data is not None:
        inside &= mask_data
    if not inside.any():
        raise ValueError('No finite values inside the mask to threshold.')

    cutoff = float(np.percentile(img_data[inside], 100 - top_percent))
    keep = inside & (img_data >= cutoff)
    masked_data = np.where(keep, img_data, thresh_val)
    if mask_data is not None:
        masked_data[np.invert(mask_data)] = 0.0  # Set voxels outside the mask to a background value.
    return nib.Nifti1Image(masked_data, affine=img.affine), cutoff


def _check_threshold_method(thresh_img, top_percent):
    """Raise ``ValueError`` unless exactly one of the two is given."""
    if (thresh_img is None) == (top_percent is None):
        raise ValueError('Give either `thresh_img` (p-values, with `alpha`) or `top_percent`, not both or neither.')


def threshold_single_image(img, thresh_img=None, meta=None, thresh_img_meta=None, alpha=0.05, contrast_idx=None, output_path=None, load_errors='raise', thresh_val=np.nan, mask_img=None, top_percent=None):
    """
    Threshold a single image, either with a p-value map or by keeping
    its largest values.

    Give either ``thresh_img`` (voxels with p-values above ``alpha``
    are removed) or ``top_percent`` (only the largest ``top_percent``
    percent of values are kept, see :func:`_threshold_top_percent_img`).

    Parameters
    ----------
    img : path-like or nib.Nifti1Image
        Image to threshold (e.g. a z-score map), 3D or 4D (see
        ``contrast_idx``).
    thresh_img : path-like or nib.Nifti1Image, optional
        Corresponding p-value image used as the threshold mask.
    meta : dict, optional
        Sidecar of ``img``. Required to keep the provenance of in-memory
        images; loaded from disk for paths if not given.
    thresh_img_meta : dict, optional
        Sidecar of ``thresh_img``, as for ``meta``.
    alpha : float, optional
        Significance threshold, used with ``thresh_img``. Default is
        ``0.05``.
    contrast_idx : int, optional
        Index of the contrast to threshold when the inputs are 4D.
    output_path : path-like, optional
        Path at which to save the thresholded image. Not saved if not
        given.
    load_errors : {'raise', 'warn'}, optional
        How to handle loading errors. Default is ``'raise'``.
    thresh_val : float, optional
        Value given to the voxels that are removed. Default is NaN.
    mask_img : path-like or nib.Nifti1Image, optional
        Brain mask; voxels outside it are set to ``0`` and, with
        ``top_percent``, do not count towards the percentage. Resampled
        to ``img`` if needed.
    top_percent : float, optional
        Percentage of voxels (inside the mask) with the largest values
        to keep, in (0, 100], e.g. ``5`` for the top 5%.

    Returns
    -------
    masked_img : nib.Nifti1Image
        Thresholded image.
    meta : dict
        Sidecar of the thresholded image. With ``top_percent``, the
        value at the cutoff is recorded as ``top_percent_cutoff``.

    Raises
    ------
    ValueError
        If both or neither of ``thresh_img`` and ``top_percent`` are
        given, or ``top_percent`` is not in (0, 100].
    """
    _check_threshold_method(thresh_img, top_percent)
    est_img, est_input = _check_input_img(img, meta=meta, load_errors=load_errors)
    est_img = _select_contrast_img(est_img, contrast_idx=contrast_idx)
    mask_data, mask_input = _prepare_mask(est_img, mask_img=mask_img, load_errors=load_errors)

    fields = {}
    if top_percent is not None:
        p_input = None
        masked_img, cutoff = _threshold_top_percent_img(est_img, top_percent, thresh_val=thresh_val, mask_data=mask_data)
        fields['top_percent_cutoff'] = cutoff
    else:
        p_img, p_input = _check_input_img(thresh_img, meta=thresh_img_meta, load_errors=load_errors)
        p_img = _select_contrast_img(p_img, contrast_idx=contrast_idx)
        masked_img = _threshold_single_img(est_img, p_img, alpha=alpha, thresh_val=thresh_val, mask_data=mask_data)

    meta = provenance.record_step(
        'volume.threshold_single_image',
        inputs={'img': est_input, 'thresh_img': p_input, 'mask': mask_input},
        parameters={
            'alpha': alpha if top_percent is None else None,
            'top_percent': top_percent,
            'contrast_idx': contrast_idx,
            'thresh_val': thresh_val
        },
        output_path=output_path,
        fields=fields
    )

    if output_path:
        io_utils.save_image(masked_img, output_path, meta=meta)

    return masked_img, meta


def threshold_images(img, thresh_img=None, meta=None, thresh_img_meta=None, alpha=0.05, output_path=None, load_errors='raise', thresh_val=np.nan, mask_img=None, top_percent=None):
    """
    Threshold a 4D image contrast by contrast, either with a p-value
    image or by keeping each contrast's largest values.

    Give either ``thresh_img`` or ``top_percent``:

    * ``thresh_img``: voxels with p-values above ``alpha`` are removed.
      If ``thresh_img`` is 4D, its contrasts must match those of
      ``img``; if it is 3D, the same p-values are used for every
      contrast.
    * ``top_percent``: for each contrast separately, only the largest
      ``top_percent`` percent of its values are kept (see
      :func:`_threshold_top_percent_img`).

    Parameters
    ----------
    img : path-like or nib.Nifti1Image
        4D image to threshold (e.g. z-score maps), with
        ``volume_labels`` in its sidecar.
    thresh_img : path-like or nib.Nifti1Image, optional
        p-value image used as the threshold mask. May be 3D (applied to
        all contrasts) or 4D (matched per contrast label).
    meta : dict, optional
        Sidecar of ``img``. Required for in-memory images; loaded from
        disk for paths if not given.
    thresh_img_meta : dict, optional
        Sidecar of ``thresh_img``, as for ``meta``. Required for an
        in-memory 4D ``thresh_img``.
    alpha : float, optional
        Significance threshold, used with ``thresh_img``. Default is
        ``0.05``.
    output_path : path-like, optional
        Path at which to save the thresholded 4D image. Not saved if not
        given.
    load_errors : {'raise', 'warn'}, optional
        How to handle loading errors. Default is ``'raise'``.
    thresh_val : float, optional
        Value given to the voxels that are removed. Default is NaN.
    mask_img : path-like or nib.Nifti1Image, optional
        Brain mask; voxels outside it are set to ``0`` and, with
        ``top_percent``, do not count towards the percentage. Resampled
        to ``img`` if needed.
    top_percent : float, optional
        Percentage of voxels (inside the mask) with the largest values
        to keep in each contrast, in (0, 100], e.g. ``5`` for the top
        5%.

    Returns
    -------
    thresholded_img : nib.Nifti1Image
        4D thresholded image with contrasts in the same order as the
        input.
    meta : dict
        Sidecar of the thresholded image. With ``top_percent``, the
        value at each contrast's cutoff is recorded as
        ``top_percent_cutoffs``.

    Raises
    ------
    ValueError
        If both or neither of ``thresh_img`` and ``top_percent`` are
        given, ``top_percent`` is not in (0, 100], or both images are
        4D but their contrast labels do not match.
    """
    _check_threshold_method(thresh_img, top_percent)
    est_dict, est_input = _check_contrasts_img(img, meta=meta, load_errors=load_errors)

    new_imgs = {}
    fields = {}
    if top_percent is not None:
        p_input = None
        cutoffs = {}
        for contrast, est_contrast_img in est_dict.items():
            mask_data, mask_input = _prepare_mask(est_contrast_img, mask_img=mask_img, load_errors=load_errors)
            new_imgs[contrast], cutoffs[contrast] = _threshold_top_percent_img(
                est_contrast_img, top_percent, thresh_val=thresh_val, mask_data=mask_data)
        fields['top_percent_cutoffs'] = cutoffs
    else:
        p_img, p_input = _check_input_img(thresh_img, meta=thresh_img_meta, load_errors=load_errors)
        if p_img.ndim == 4:
            p_dict, p_input = _check_contrasts_img(p_img, meta=p_input[1], load_errors=load_errors)
            if set(p_dict.keys()) != set(est_dict.keys()):
                raise ValueError('Threshold image contrasts do not match target image contrasts.')
        else:
            logger.warning('Thresholding image is 3D. Applying the same threshold to all contrasts.')
            p_dict = {contrast: p_img for contrast in est_dict.keys()}

        for contrast, est_contrast_img in est_dict.items():
            mask_data, mask_input = _prepare_mask(est_contrast_img, mask_img=mask_img, load_errors=load_errors)
            new_imgs[contrast] = _threshold_single_img(est_contrast_img, p_dict[contrast], alpha=alpha, thresh_val=thresh_val, mask_data=mask_data)

    # Concatenate along a new axis to create a 4D image.
    thresholded_img = nib.concat_images(list(new_imgs.values()))

    meta = provenance.record_step(
        'volume.threshold_images',
        inputs={'img': est_input, 'thresh_img': p_input, 'mask': mask_input},
        parameters={
            'alpha': alpha if top_percent is None else None,
            'top_percent': top_percent,
            'thresh_val': thresh_val
        },
        output_path=output_path,
        fields={'volume_labels': list(new_imgs.keys()), **fields}
    )

    if output_path:
        io_utils.save_image(thresholded_img, output_path, meta=meta)

    return thresholded_img, meta


def _apply_across_volumes(img, func, mask_data, **func_kwargs):
    """
    Apply ``func`` to the 4th-dimension values of every voxel in
    ``mask_data``; see :func:`apply_across_volumes`.

    Returns
    -------
    nib.Nifti1Image
        3D float32 image of ``func`` results, ``0`` outside the mask.
    """
    data = img.get_fdata(caching='unchanged')  # (x, y, z, t)
    data_2d = data[mask_data, :]  # (n_voxels, t)

    result_1d = np.apply_along_axis(func, axis=1, arr=data_2d, **func_kwargs)  # (n_voxels,)
    # Put back into volume but use 3D.
    result_3d = np.full(img.shape[:3], 0.0, dtype=np.float32)
    result_3d[mask_data] = result_1d

    return nib.Nifti1Image(result_3d, img.affine, img.header)


def apply_across_volumes(img, func, mask_img=None, meta=None, output_path=None, load_errors='raise', **func_kwargs):
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
    output_path : path-like, optional
        Path at which to save the result. Not saved if not given.
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
    result_img = _apply_across_volumes(img, func, mask_data, **func_kwargs)

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
        can be used as a 4D image of contrasts.
    output_path : path-like, optional
        Path at which to save the 4D image. Not saved if not given.

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


def wta(data, below_thresh_val=np.nan, outside_val=np.nan, no_result_idx=None, only_positive=True):
    """
    Winner-take-all function to be applied with
    :func:`apply_across_volumes` (or see :func:`winner_take_all`).

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
        value. Default is one more than the number of contrasts.
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
    if no_result_idx is None:
        no_result_idx = data.size + 1

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


def winner_take_all(img, mask_img=None, meta=None, output_path=None, below_thresh_val=np.nan, outside_val=np.nan, only_positive=True, outside_label='Outside ROI', no_result_label='Rest', load_errors='raise'):
    """
    Label every voxel with the contrast that has the largest value.

    Applies :func:`wta` to every voxel of a 4D image of contrasts. The
    result has ``0`` outside the ROI, ``1..n`` for the n contrasts, and
    ``n + 1`` for voxels inside the ROI where no contrast is valid. The
    names of these labels are recorded as ``labels`` in the sidecar, so
    that later steps (segmentations, plots) can use them.

    Parameters
    ----------
    img : path-like or nib.Nifti1Image
        4D image whose volumes are labelled by ``volume_labels`` in its
        sidecar (e.g. from :func:`roi_per_contrast`).
    mask_img : path-like or nib.Nifti1Image, optional
        Brain mask. Resampled to ``img`` if needed. Voxels outside are
        set to ``0``. Default is to use all voxels.
    meta : dict, optional
        Sidecar of ``img``. Required for in-memory images; loaded from
        disk for paths if not given.
    output_path : path-like, optional
        Path at which to save the label image. Not saved if not given.
    below_thresh_val, outside_val, only_positive
        See :func:`wta`.
    outside_label : str, optional
        Name of label ``0``. Default is ``'Outside ROI'``.
    no_result_label : str, optional
        Name of label ``n + 1``. Default is ``'Rest'``.
    load_errors : {'raise', 'warn'}, optional
        How to handle loading errors. Default is ``'raise'``.

    Returns
    -------
    wta_img : nib.Nifti1Image
        3D float32 label image.
    meta : dict
        Its sidecar, with the label names as ``labels``.
    """
    img, img_input = _check_input_img(img, meta=meta, load_errors=load_errors)
    img_dict, _ = _check_contrasts_img(img, meta=img_input[1], load_errors=load_errors)
    contrasts = list(img_dict)
    no_result_idx = len(contrasts) + 1

    mask_data, mask_input = _prepare_mask(img, mask_img, load_errors=load_errors)
    wta_img = _apply_across_volumes(
        img, wta, mask_data, below_thresh_val=below_thresh_val, outside_val=outside_val,
        no_result_idx=no_result_idx, only_positive=only_positive
    )

    labels = {'0': outside_label, **{str(idx + 1): c for idx, c in enumerate(contrasts)},
              str(no_result_idx): no_result_label}
    meta = provenance.record_step(
        'volume.winner_take_all',
        inputs={'img': img_input, 'mask': mask_input},
        parameters={'below_thresh_val': below_thresh_val, 'outside_val': outside_val,
                    'only_positive': only_positive},
        output_path=output_path,
        fields={'labels': labels}
    )

    if output_path:
        io_utils.save_image(wta_img, output_path, meta=meta)

    return wta_img, meta


def largest_components(img, n_components, meta=None, output_path=None, connectivity=1, fill_label=None, load_errors='raise'):
    """
    Keep only the largest connected components of selected labels in a
    label image (e.g. from :func:`winner_take_all`).

    For each label in ``n_components``, the voxels with that label are
    split into connected components (``scipy.ndimage.label``) and only
    the given number of largest components is kept; the label's other
    voxels are set to ``fill_label``. Labels not in ``n_components`` are
    left unchanged. Components of equal size are ranked in the order
    ``scipy.ndimage.label`` finds them.

    Parameters
    ----------
    img : path-like or nib.Nifti1Image
        3D label image whose sidecar records the label names as
        ``labels`` (as :func:`winner_take_all` does).
    n_components : dict
        Mapping of label name to the number of largest components to
        keep, e.g. ``{'LPvsOthers': 2, 'LHvsOthers': 1}``. ``0`` removes
        the label entirely.
    meta : dict, optional
        Sidecar of ``img``. Required for in-memory images; loaded from
        disk for paths if not given.
    output_path : path-like, optional
        Path at which to save the result. Not saved if not given.
    connectivity : {1, 2, 3}, optional
        Which neighbouring voxels count as connected: ``1`` voxels
        sharing a face (6-connectivity), ``2`` also an edge (18), ``3``
        also a corner (26). Default is ``1``.
    fill_label : str, optional
        Name of the label given to removed voxels, e.g. ``'Rest'``.
        Default is ``0`` (outside the ROI / background).
    load_errors : {'raise', 'warn'}, optional
        How to handle loading errors. Default is ``'raise'``.

    Returns
    -------
    out_img : nib.Nifti1Image
        Label image with the smaller components removed.
    meta : dict
        Its sidecar. The labels are carried over, and ``components``
        records, per processed label, the number of components found,
        the sizes (in voxels) of those kept, and the number of voxels
        removed.

    Raises
    ------
    ValueError
        If the sidecar records no label names, or a label in
        ``n_components`` or ``fill_label`` is not one of them.
    """
    img, img_input = _check_input_img(img, meta=meta, load_errors=load_errors)
    labels = _labels(img_input[1])
    if not labels:
        raise ValueError('The sidecar of `img` must record the label names as `labels`.')
    value_of = {name: int(value) for value, name in labels.items()}
    unknown = [name for name in [*n_components, *([fill_label] if fill_label else [])] if name not in value_of]
    if unknown:
        raise ValueError(f'Unknown label(s) {unknown}; the image has {list(value_of)}.')
    fill_value = value_of[fill_label] if fill_label else 0

    data = img.get_fdata(caching='unchanged')
    out = data.copy()
    structure = ndimage.generate_binary_structure(3, connectivity)
    components = {}
    for name, n_keep in n_components.items():
        mask = data == value_of[name]
        labelled, n_found = ndimage.label(mask, structure=structure)
        sizes = ndimage.sum_labels(mask, labelled, index=np.arange(1, n_found + 1))
        # Largest first; equal sizes keep the order they were found in.
        keep = np.argsort(-sizes, kind='stable')[:n_keep] + 1
        remove = mask & ~np.isin(labelled, keep)
        out[remove] = fill_value
        components[name] = {
            'n_found': int(n_found),
            'kept_sizes': [int(sizes[k - 1]) for k in keep],
            'removed_voxels': int(remove.sum()),
        }

    out_img = nib.Nifti1Image(out.astype(data.dtype), img.affine, img.header)

    meta = provenance.record_step(
        'volume.largest_components',
        inputs={'img': img_input},
        parameters={'n_components': n_components, 'connectivity': connectivity, 'fill_label': fill_label},
        output_path=output_path,
        fields={'labels': labels, 'components': components}
    )

    if output_path:
        io_utils.save_image(out_img, output_path, meta=meta)

    return out_img, meta


def resample_image(img, target_img, meta=None, target_img_meta=None, output_path=None, interpolation='continuous', load_errors='raise'):
    """
    Resample an image onto the grid of another image.

    Parameters
    ----------
    img : path-like or nib.Nifti1Image
        Image to resample (e.g. a T1w image).
    target_img : path-like or nib.Nifti1Image
        Image defining the output grid (space and resolution).
    meta : dict, optional
        Sidecar of ``img``. Required to keep the provenance of in-memory
        images; loaded from disk for paths if not given.
    target_img_meta : dict, optional
        Sidecar of ``target_img``, as for ``meta``.
    output_path : path-like, optional
        Path at which to save the resampled image. Not saved if not
        given.
    interpolation : {'continuous', 'linear', 'nearest'}, optional
        Interpolation passed to ``nilearn.image.resample_to_img``; use
        ``'nearest'`` for label images. Default is ``'continuous'``.
    load_errors : {'raise', 'warn'}, optional
        How to handle loading errors. Default is ``'raise'``.

    Returns
    -------
    resampled_img : nib.Nifti1Image
        The resampled image.
    meta : dict
        Its sidecar. ``labels`` recorded for ``img`` are carried over.
    """
    img, img_input = _check_input_img(img, meta=meta, load_errors=load_errors)
    target_img, target_input = _check_input_img(target_img, meta=target_img_meta, load_errors=load_errors)

    resampled_img = nilearn.image.resample_to_img(
        img, target_img, interpolation=interpolation, force_resample=True, copy_header=True
    )

    meta = provenance.record_step(
        'volume.resample_image',
        inputs={'img': img_input, 'target_img': target_input},
        parameters={'interpolation': interpolation},
        output_path=output_path,
        fields={'labels': _labels(img_input[1])}
    )

    if output_path:
        io_utils.save_image(resampled_img, output_path, meta=meta)

    return resampled_img, meta


def save_as_segmentation(img, meta=None, template=None, labels=None, output_path=None, load_errors='raise', color_palette=None):
    """
    Convert an image into an integer segmentation.

    The data are cast to int16 and resampled with nearest-neighbour
    interpolation onto ``template``. The label names are stored in the
    sidecar and, if the segmentation is saved, an ITK-SNAP label
    description file (``<output>_labels.txt``) is written next to it.

    Parameters
    ----------
    img : path-like or nib.Nifti1Image
        Label image (e.g. from :func:`winner_take_all`).
    meta : dict, optional
        Sidecar of ``img``. Required to keep the provenance of in-memory
        images; loaded from disk for paths if not given.
    template : path-like, nib.Nifti1Image or False, optional
        Image defining the output grid. Defaults to the 1mm MNI152
        template from nilearn. Pass ``False`` to keep the input grid.
    labels : dict or list, optional
        Label names, either a mapping of label value to name or a list
        indexed by label value. Defaults to the ``labels`` recorded in
        the sidecar of ``img``.
    output_path : path-like, optional
        Path at which to save the segmentation image. Not saved if not
        given.
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
    if labels is None and _labels(img_input[1]) is not None:
        labels = {int(k): v for k, v in _labels(img_input[1]).items()}

    out_img = nib.Nifti1Image(
        img.get_fdata(caching='unchanged').astype(np.int16),
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
        if isinstance(template, os.PathLike):
            # nilearn only takes str and pathlib paths.
            template = os.fspath(template)

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
