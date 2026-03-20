import os
from pathlib import Path
from collections import defaultdict
import json
import tempfile
import argparse

import pandas as pd
import numpy as np

import nilearn
import nibabel as nib
from nilearn.glm.first_level import make_first_level_design_matrix, FirstLevelModel
from nilearn.glm import threshold_stats_img


def save_stats(stats_data, filename):
    """
    Stack stats images along the 4th dimension. Save labels for each
    volume on the 4th dimension into a sidecar JSON.
    """
    data_4d = np.stack([img.get_fdata() for img in stats_data.values()], axis=-1)
    # Use the affine from any of the images.
    affine = next(iter(stats_data.values())).affine
    stats_img = nib.Nifti1Image(data_4d, affine)

    labels = list(stats_data.keys())
    stats_img.header['descrip'] = ' | '.join(labels)
    # Make this work with AFNI as well.
    stats_img.header.extensions = nib.nifti1.Nifti1Extensions([
        nib.nifti1.Nifti1Extension(
            code=4,
            content=(
                '<?xml version=\'1.0\' ?>\n'
                '<AFNI_attributes\n'
                'self_idcode="XYZ_kH4GTzsl_aMIjB6R6NDJ1w"\n'
                'NIfTI_nums="129,153,129,1,43,16"\n'
                'ni_form="ni_group" >\n'
                    '<AFNI_atr\n'
                    'ni_type="String"\n'
                    'ni_dimen="1"\n'
                    'atr_name="BRICK_LABS" >\n'
                    f'{"~".join(labels)}\n'
                    '</AFNI_atr>\n'
                '</AFNI_attributes>\n'.encode()
            )
        )
    ])
    nib.save(stats_img, filename)
    
    # Save labels as JSON sidecar.
    # Accomodate both compressed and uncompressed NIFTIs.
    json_filename = filename.replace('.nii.gz', '.json').replace('.nii', '.json')
    with open(json_filename, "w") as f:
        json.dump({"volume_labels": labels}, f, indent=2)

    return filename, json_filename

def get_roi_mask(atlas='destrieux_2009', img=None, regions=None):
    """
    Get a mask based on regions from an atlas.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        getter = getattr(nilearn.datasets, f'fetch_atlas_{atlas}')
        dest = getter(data_dir=tmpdir)
        atlas_img = nib.load(dest['maps'])
        labels = dest['labels']
    
        region_indices = [labels.index(rg) for rg in regions]

        # Create binary mask.
        mask = nilearn.image.math_img(" + ".join([f"(img == {i})" for i in region_indices]), img=atlas_img)
    
    mask_resampled = nilearn.image.resample_to_img(mask, img, interpolation='nearest', copy_header=True)

    return mask_resampled


def load_config(json_path):
    def expand(item):
        """
        Expand shell variables (e.g., ${VAR}, $VAR) into their values.
        """
        if isinstance(item, str):
            return os.path.expandvars(item)
        elif isinstance(item, dict):
            return {k: expand(v) for k, v in item.items()}
        elif isinstance(item, list):
            return [expand(elem) for elem in item]
        else:
            return item

    with open(json_path, 'r') as f:
        config = json.load(f)

    return expand(config)


def save_config(json_path, config):
    with open(json_path, 'w') as f:
        json.dump(config, f)


def run_glm(config, sub, ses):
    """
    Run GLM with motion censoring, motion regressors, and nuisance
    regressors (CSF & WM PCs). All contrasts will be saved into one 4D
    image and stat types will be saved in different files.
    """
    epi_path = Path(config['data_path']) / Path(config['epi_path'].format(sub=sub, ses=ses))
    events_path = Path(config['data_path']) / Path(config['events_path'].format(sub=sub, ses=ses))
    confounds_path = Path(config['data_path']) / Path(config['confounds_path'].format(sub=sub, ses=ses))
        
    img = nilearn.image.load_img(epi_path)
    # Timepoints in seconds from the start.
    timepoints = np.arange(img.shape[-1]) * config['TR']
    
    events = pd.read_csv(events_path, delimiter='\t')
    # Exclude any rest events.
    nonrest_idx = np.invert(events['trial_type'].str.contains('rest'))
    events = events.loc[nonrest_idx, :]

    # Nuisance regressors.
    confounds_df = pd.read_csv(confounds_path, delimiter='\t')
    motion_censor = [c for c in confounds_df.columns if 'motion_outlier' in c]
    motion = ['trans_x', 'trans_y', 'trans_z', 'rot_x', 'rot_y', 'rot_z']
    # CSF and WM CompCor principal components.
    pcs = [f'{tissue}_comp_cor_{ii:02d}' for ii in range(config['n_PCs']) for tissue in ['c', 'w']]
    
    additional = motion_censor + motion + pcs
    add_regs = confounds_df[additional].values
    add_reg_names = additional
    
    # AFNI uses 1 polynomial order per 150 seconds of data.
    design_mat = make_first_level_design_matrix(
        timepoints,
        events,
        hrf_model='spm',
        drift_model='polynomial',
        drift_order=3,
        add_regs=add_regs,
        add_reg_names=add_reg_names
    )
    
    if config['mask_atlas']:
        mask = get_roi_mask(atlas=config['mask_atlas'], regions=config['mask_regions'], img=img)
    else:
        mask = None
    
    glm = FirstLevelModel(
        n_jobs=config['n_jobs'],
        mask_img=mask,
        verbose=3
    )
    glm = glm.fit(img, design_matrices=design_mat)
    stats = defaultdict(dict)
    for contr_label, contr in config['contrasts'].items():
        t_map = glm.compute_contrast(contr, output_type='stat')
        z_map = glm.compute_contrast(contr, output_type='z_score')
        p_map = glm.compute_contrast(contr, output_type='p_value')
        (corrected_t, crit_t) = threshold_stats_img(t_map, mask_img=mask, height_control='fdr')
        beta_map = glm.compute_contrast(contr, output_type='effect_size')
        beta_var_map = glm.compute_contrast(contr, output_type='effect_variance')
    
        stats['stat'][contr_label] = t_map
        stats['z_score'][contr_label] = z_map
        stats['p_value'][contr_label] = p_map
        stats['stat_fdr_q001'][contr_label] = corrected_t
        stats['betas'][contr_label] = beta_map
        stats['betas_var'][contr_label] = beta_var_map
    
    for stat_type, stat_values in stats.items():
        # Allow setting completely custom path if it is an absolute
        # path.
        filename = config['results_path'].format(sub=sub, ses=ses, stat_type=stat_type)
        if not filename.startswith('/'):
            filename = str(Path(config['data_path']) / res_path)

        # All contrasts will be packaged into one file. Separate files
        # will be made for different stat types (e.g., one file for
        # betas, one file for t-stats, etc.).
        save_stats(stat_values, filename)

    return glm


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Run first-level regression.")
    parser.add_argument("-c", "--config", help="Path to the config JSON file.")
    parser.add_argument("--sub", help="Subject number")
    parser.add_argument("--ses", help="Session number")
    args = parser.parse_args()

    config = load_config(args.config)
    glm = run_glm(config, args.sub, args.ses)
        