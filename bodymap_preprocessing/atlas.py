"""Fetcher for the Glasser 2016 HCP Multi-Modal Parcellation (MMP1.0) atlas."""

import pandas as pd
import nilearn.datasets
from nilearn.datasets._utils import fetch_files, get_dataset_dir
from nilearn.datasets.atlas import Atlas

_DESCRIPTION_GLASSER = """\
Glasser 2016 HCP Multi-Modal Parcellation (MMP1.0)

The Human Connectome Project's group-level multimodal parcellation (MMP;
Glasser et al. [2016] Nature) projected from surface coordinates into
volumetric MNI space using registration fusion.

This is the winner-take-all parcellation derived from probabilistic maps
(p > 0.2) in MNI152NLin2009cAsym space (fMRIPrep's default space).

The atlas contains 180 cortical areas per hemisphere (360 total), numbered
1-180 for the left hemisphere and 201-380 for the right hemisphere.

For more information see:
  Glasser, M.F. et al. (2016). A multi-modal parcellation of human cerebral
  cortex. Nature, 536(7615), 171-178. https://doi.org/10.1038/nature18933

Source: https://figshare.com/articles/dataset/24431146
"""

_DESCRIPTION_HMAT_2006 = """\
Hammersmith Montreal Neurological Institute Atlas (HMAT) 2006

The Hammersmith atlas is a neuroanatomical atlas created from the
MNI152NLin6Asym template and distributed as a volumetric atlas for
brain-region labeling and parcellation. The HMAT 2006 release is a
12-region, deterministic atlas packaged with a README describing label
indices and a corresponding NIfTI spatial map.

For more information see:
  Mayka, M.A., Corcos, D.M., Leurgans, S.E., Vaillancourt, D.E. 2006.
  Three-dimensional locations and boundaries of motor and premotor cortices
  as defined by functional brain imaging: a meta-analysis. Neuroimage.
  31(4):1453-1474.

Source: https://lrnlab.org/wp-content/uploads/2013/09/HMAT.zip
"""


def fetch_atlas_glasser_2016(
    data_dir=None,
    url=None,
    resume=True,
    verbose=1,
    filenames=None,
):
    """Download and return the Glasser 2016 HCP MMP1.0 atlas.

    Downloads the winner-take-all parcellation derived from
    probabilistic maps (p > 0.2) in MNI152NLin2009cAsym space,
    as distributed on Figshare (doi:10.6084/m9.figshare.24431146).
    The atlas contains 180 cortical areas per hemisphere, labelled
    with the prefix ``L_`` or ``R_``, for a total of 360 parcels (0
    is background).

    Parameters
    ----------
    data_dir : str or Path, optional
        Path where the atlas will be stored. By default, files are
        stored in a ``glasser_2016`` sub-folder inside the nilearn
        data directory (``~/nilearn_data`` unless overridden by the
        ``NILEARN_DATA`` or ``NILEARN_SHARED_DATA`` environment
        variables). See :func:`nilearn.datasets.utils.get_data_dirs`
        for details.

    url : dict, optional
        Override the download URLs. Must be a dict with keys
        ``'atlas'`` and ``'labels'``, each mapping to a URL string.

    resume : bool, default=True
        Whether to resume a partially downloaded file.

    verbose : int, default=1
        Verbosity level (0 means no messages).

    filenames : dict, optional
        Override the local filenames used when saving downloaded
        files. Must be a dict with keys ``'atlas'`` and ``'labels'``,
        each mapping to a filename string.

    Returns
    -------
    data : :class:`nilearn.datasets.utils.Atlas`
        Atlas object with the following attributes:

        ``maps`` : str
            Path to the NIfTI file in MNI152NLin2009cAsym space.
            Voxel values are consecutive integers 1-360, where
            1-180 are left-hemisphere parcels (``L_`` prefix) and
            181-360 are right-hemisphere parcels (``R_`` prefix).
            Value 0 is background.

        ``labels`` : list of str
            List of 360 region names in index order (i.e.
            ``labels[i]`` corresponds to voxel value ``i + 1``).
            Names include hemisphere prefix, e.g. ``'L_V1_ROI'``,
            ``'R_V1_ROI'``.

        ``lut`` : :class:`pandas.DataFrame`
            Look-up table with columns ``'index'`` (integer voxel
            value) and ``'name'`` (region name), including a row
            for background (index 0). Formatted following the BIDS
            ``dseg.tsv`` convention.

        ``description`` : str
            Short description of the atlas and its source.

        ``template`` : str
            ``'MNI152NLin2009cAsym'``

        ``atlas_type`` : str
            ``'deterministic'``

    References
    ----------
    Glasser, M. F., Coalson, T. S., Robinson, E. C., Hacker, C. D.,
    Harwell, J., Yacoub, E., ... & Van Essen, D. C. (2016).
    A multi-modal parcellation of human cerebral cortex.
    *Nature*, 536(7615), 171-178.
    https://doi.org/10.1038/nature18933
    """
    atlas_type = "deterministic"

    if url is None:
        url = {
            'labels': "https://ndownloader.figshare.com/files/43041079",
            'atlas': "https://ndownloader.figshare.com/files/43043683"
        }

    if filenames is None:
        filenames = {
            'labels': 'glasser_atlas_labels.txt',
            'atlas': 'glasser_MNI152NLin2009cAsym_labeled_p20.nii.gz'
        }
    
    files = [
        (filenames['labels'], url['labels'], {'move': filenames['labels']}),
        (filenames['atlas'], url['atlas'], {'move': filenames['atlas']}),
    ]
    
    dataset_name = "glasser_2016"
    data_dir = get_dataset_dir(
        dataset_name, data_dir=data_dir, verbose=verbose
    )
    labels_file, atlas_file = fetch_files(data_dir, files, resume=resume, verbose=verbose)
    
    with open(labels_file, 'r') as fh:
        labels = [line.strip() for line in fh if line.strip()]
    
    if len(labels) != 360:
        raise ValueError(
            f"Expected 360 labels (180 per hemisphere), got {len(labels)}. "
            "The labels file may be corrupt or from a different version."
        )
    
    # Ensure that 0 is the background.
    labels_df = [(0, 'Background')] + list(enumerate(labels))
    labels_df = pd.DataFrame(labels_df, columns=['index', 'name'])
    labels_df.loc[1:, 'index'] += 1
    
    return Atlas(
        maps=atlas_file,
        labels=labels,
        description=_DESCRIPTION_GLASSER,
        atlas_type=atlas_type,
        lut=labels_df,
        template="MNI152NLin2009cAsym",
    )


def fetch_atlas_hmat_2006(
    data_dir=None,
    url=None,
    resume=True,
    verbose=1,
    filenames=None,
):
    """Download and return the HMAT 2006 atlas.

    Downloads the Hammersmith/MNI atlas volumes distributed as the
    HMAT 2006 package from the LRNLab archive. The atlas is stored in
    MNI152NLin6Asym space and packaged with a label README file that
    lists the 12 labelling indices and their region names.

    Parameters
    ----------
    data_dir : str or Path, optional
        Path where the atlas will be stored. By default, files are
        stored in a ``hmat_2006`` sub-folder inside the nilearn data
        directory (``~/nilearn_data`` unless overridden by the
        ``NILEARN_DATA`` or ``NILEARN_SHARED_DATA`` environment
        variables).

    url : str, optional
        Override the download URL. If omitted, the default HMAT archive
        from the LRNLab website is used.

    resume : bool, default=True
        Whether to resume a partially downloaded file.

    verbose : int, default=1
        Verbosity level (0 means no messages).

    filenames : dict, optional
        Override the local filenames used when saving downloaded
        files. Must be a dict with keys ``'labels'`` and ``'atlas'``,
        each mapping to a filename string.

    Returns
    -------
    data : :class:`nilearn.datasets.utils.Atlas`
        Atlas object with the following attributes:

        ``maps`` : str
            Path to the NIfTI file in MNI152NLin6Asym space.

        ``labels`` : list of str
            List of atlas region names in index order.

        ``lut`` : :class:`pandas.DataFrame`
            Look-up table with columns ``'index'`` (integer voxel value)
            and ``'name'`` (region name), including a row for background
            (index 0).

        ``description`` : str
            Short description of the atlas and its source.

        ``template`` : str
            ``'MNI152NLin6Asym'``

        ``atlas_type`` : str
            ``'deterministic'``

    References
    ----------
    Hammersmith/MNI atlas 2006 package distributed from the LRNLab
    HMAT archive.
    """
    atlas_type = "deterministic"

    if url is None:
        url = 'https://lrnlab.org/wp-content/uploads/2013/09/HMAT.zip'

    if filenames is None:
        filenames = {
            'labels': 'HMAT_website/README.txt',  # Contains labels and their indices.
            'atlas': 'HMAT_website/HMAT.nii'
        }

    files = [
        (filenames['labels'], url, {'uncompress': True}),
        (filenames['atlas'], url, {'uncompress': True}),
    ]

    dataset_name = "hmat_2006"
    data_dir = get_dataset_dir(
        dataset_name, data_dir=data_dir, verbose=verbose
    )
    labels_file, atlas_file = fetch_files(data_dir, files, resume=resume, verbose=verbose)

    # Parse the labels from the README file.
    with open(labels_file, 'r') as f:
       contents = f.readlines()

    # Find the line right before the labels and run an extra
    # verification to make sure that the contents are not different
    # than expected.
    target_line = [line_idx for line_idx, line in enumerate(contents) if 'We have used values that range from 1-12' in line]
    if len(target_line) > 1:
        raise ValueError('More than 1 target line for labels was found. The labels files has changed.')
    target_line = target_line[0]
    if contents[target_line + 2].replace('\n', '') != 'KEY':
        raise ValueError('Locating labels in the readme file failed. The file might have changed.')

    # Ensure that 0 is the background.
    labels = [(0, 'Background')]
    for ln in contents[target_line+3:]:
        # Some labels have multiple `\t` between the label and its
        # index.
        lab = ln.replace('\n', '').split('\t')
        labels.append((int(lab[-1]), lab[0]))

    if len(labels) != 13:
        raise ValueError(
            f"Expected 13 labels (including 'Background'), got {len(labels)}. "
            "The labels file may be corrupt or from a different version."
        )

    labels_df = pd.DataFrame(labels, columns=['index', 'name'])

    return Atlas(
        maps=atlas_file,
        labels=[lab[1] for lab in labels],
        description=_DESCRIPTION_HMAT_2006,
        atlas_type=atlas_type,
        lut=labels_df,
        template="MNI152NLin6Asym",
    )

nilearn.datasets.fetch_atlas_glasser_2016 = fetch_atlas_glasser_2016
nilearn.datasets.fetch_atlas_hmat_2006 = fetch_atlas_hmat_2006