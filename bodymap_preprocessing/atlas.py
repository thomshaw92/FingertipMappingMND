"""Fetcher for the Glasser 2016 HCP Multi-Modal Parcellation (MMP1.0) atlas."""
 
import pandas as pd
import nilearn.datasets
from nilearn.datasets._utils import fetch_files, get_dataset_dir
from nilearn.datasets.atlas import Atlas
 
_DESCRIPTION = """\
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
        description=_DESCRIPTION,
        atlas_type=atlas_type,
        lut=labels_df,
        template="MNI152NLin2009cAsym",
    )

nilearn.datasets.fetch_atlas_glasser_2016 = fetch_atlas_glasser_2016