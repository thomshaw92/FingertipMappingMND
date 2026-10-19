import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent / 'utils'))

import nibabel as nib
import nilearn
import shutil
import logging
import argparse

import io_utils
import analysis
import provenance

from matplotlib.colors import ListedColormap


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    force=True,
    # handlers=[
    #     logging.FileHandler(logfile),
    # ]
)


def create_bodymap(sub, ses, config, base_dir):
    for key, val in config.items():
        globals()[key] = val

    if not isinstance(base_dir, Path):
        base_dir = Path(base_dir)
    
    file = base_dir / z_score.format(sub=sub, ses=ses)
    atlas_file = base_dir / atlas_tmpl.format(sub=sub, ses=ses)
    mask_file = base_dir / epi_mask.format(sub=sub, ses=ses)

    logging.info('Correcting images')
    p_val_file = base_dir / p_val.format(sub=sub, ses=ses)
    corr_p_val_file = base_dir / corr_p_val.format(sub=sub, ses=ses)
    analysis.correct_images(
        p_val_file,
        alpha=alpha,
        output_path=corr_p_val_file,
        mask_img=mask_file
    )

    logging.info('Thresholding image')
    thresh_img, thresh_meta, _ = analysis.threshold_images(
        file,
        corr_p_val_file,
        alpha=alpha,
        output_path=False,
        load_errors='raise',
        thresh_val=999,
        mask_img=mask_file
    )

    logging.info('Extracting ROIs')
    roi_imgs, roi_metas = [], []
    for contr in contrasts:
        if contr.startswith('LP'):
            contr_regions = roi_regions['both']
        elif contr.startswith('L'):
            # Should be contralateral to the movement.
            contr_regions = roi_regions['rh']
        else:
            contr_regions = roi_regions['lh']
        
        roi_img, roi_meta = analysis.roi_single_image(
            thresh_img,
            meta=thresh_meta,
            contrast_idx=thresh_meta['volume_labels'].index(contr),
            regions=contr_regions,
            atlas=atlas_file,
            output_path=False,
            outside_val=-999.0
        )

        roi_imgs.append(roi_img)
        roi_metas.append(roi_meta)

    logging.info('Concatenating images')
    roid_file = base_dir / roid_tpl.format(sub=sub, ses=ses)
    imgs, imgs_meta = analysis.concat_images(roi_imgs, metas=roi_metas, labels=contrasts, output_path=roid_file)

    logging.info('Applying WTA')
    wta_file = base_dir / wta_tpl.format(sub=sub, ses=ses)
    wta_img, wta_meta = analysis.apply_over_time(
        img=imgs,
        func=analysis.wta,
        meta=imgs_meta,
        outside_val=-999.0,
        below_thresh_val=999,
        no_result_idx=no_result_idx,
        output_path=wta_file,
        mask_img=mask_file,
        only_positive=True
    )

    logging.info('Saving as segmentation')
    labels = {contr_idx+1: contr for contr_idx, contr in enumerate(contrasts)}
    labels[0] = 'Outside ROI'
    labels[no_result_idx] = 'Rest'
    seg_cmap = {lab: cmap[idx] for idx, lab in labels.items()}
    seg_img, seg_meta = analysis.save_as_segmentation(
        img=wta_img,
        meta=wta_meta,
        labels=labels,
        output_path=base_dir / segment_tpl.format(sub=sub, ses=ses),
        template=base_dir / t1_tpl.format(sub=sub, ses=ses),
        color_palette=seg_cmap
    )

    logging.info('Transforming surfaces to MNI')
    xfm_t1w_mni = base_dir / xfm_t1w_mni_tpl.format(sub=sub, ses=ses)
    mni_meshes = {}
    for surf in ('pial', 'white', 'inflated'):
        surf_files = {}
        for hemi in ('left', 'right'):
            if surf == 'pial':
                tpl = pial_tpl
            elif surf == 'white':
                tpl = white_tpl
            elif surf == 'inflated':
                tpl = inflated_tpl
            s_file = base_dir / tpl.format(sub=sub, ses=ses, hemi='L' if hemi == 'left' else 'R')
            surf_files[f'{hemi}_surf'] = s_file

        output_path = base_dir / mni_surf_tpl.format(sub=sub, ses=ses, surf=surf)
        mni_meshes[surf] = analysis.transform_surface_to_mni(xfm_t1w_mni=xfm_t1w_mni, output_path=output_path, **surf_files)
    pial_polymesh, pial_meta = mni_meshes['pial']
    white_polymesh, white_meta = mni_meshes['white']

    logging.info('Projecting image')
    projected_file = base_dir / projected_tpl.format(sub=sub, ses=ses)
    proj_img, proj_meta = analysis.project_image(
        wta_file,
        output_path=projected_file,
        interpolation='nearest_most_frequent',
        kind='depth',
        n_samples=20,
        mesh=pial_polymesh,
        inner_mesh=white_polymesh,
        mesh_meta=pial_meta,
        inner_mesh_meta=white_meta,
        standard_surface='MNI152NLin2009cAsym',
    )

    logging.info('Transforming projected image to fsaverage')
    fsavg_files = {}
    for hemi in ['left', 'right']:
        sphere_file = base_dir / sphere_reg_tpl.format(sub=sub, ses=ses, hemi='L' if hemi == 'left' else 'R')
        output_path = base_dir / fsavg_surf_tpl.format(sub=sub, ses=ses, hemi='L' if hemi == 'left' else 'R')
        analysis.transform_surface_to_fsaverage(
            projected_file,
            sphere_file,
            hemi=hemi,
            output_path=output_path,
            standard_surface='fsaverage',
            meta=proj_meta
        )

        fsavg_files[hemi] = output_path

    logging.info('Saving MNI surf as PNG')
    plot_labels = contrasts + ['Rest']
    plot, meta = analysis.make_plot(
        projected_file,
        meta=proj_meta,
        output_path=base_dir / plot_mni_tpl.format(sub=sub, ses=ses),
        hemi='both',
        cmap=cmap,
        symmetric_cbar=False,
        colorbar=True,
        mesh=pial_polymesh,
        mesh_meta=pial_meta,
        colorbar_labels=plot_labels,
        view='dorsal',
        cmap_bg_first=True,
        vmin=1,
        vmax=len(plot_labels),
        engine='matplotlib',
        avg_method='median'
    )

    logging.info('Saving fsaverage surf as PNG')
    plot_labels = contrasts + ['Rest']
    plot, meta = analysis.make_plot(
        fsavg_files,
        output_path=base_dir / plot_fsavg_tpl.format(sub=sub, ses=ses),
        hemi='both',
        cmap=cmap,
        symmetric_cbar=False,
        colorbar=True,
        colorbar_labels=plot_labels,
        view='dorsal',
        cmap_bg_first=True,
        standard_surface='fsaverage',
        mesh='pial',
        vmin=1,
        vmax=len(plot_labels),
        engine='matplotlib',
        avg_method='median'
    )

    logging.info('Saving fsaverage surf as HTML')
    display, meta = analysis.make_html(
        fsavg_files,
        output_path=base_dir / html_tpl.format(sub=sub, ses=ses),
        hemi='both',
        cmap=cmap,
        symmetric_cbar=False,
        colorbar=True,
        standard_surface='fsaverage',
        mesh='pial',
        colorbar_labels=plot_labels,
        cmap_bg_first=True,
        vmin=1,
        vmax=len(plot_labels)
    )

    logging.info('Copying files')
    shutil.copyfile(file, f'./{file.name}')
    shutil.copyfile(atlas_file, f'./{atlas_file.name}')
    shutil.copyfile(base_dir / f'fmriprep/output/{sub}/{ses}/anat/{sub}_{ses}_space-MNI152NLin2009cAsym_desc-preproc_T1w.nii.gz', f'./{sub}_{ses}_space-MNI152NLin2009cAsym_desc-preproc_T1w.nii.gz')

    logging.info('Resampling T1')
    t1_file = base_dir / t1_tpl.format(sub=sub, ses=ses)
    resampled_t1_file = base_dir / resampled_t1_tpl.format(sub=sub, ses=ses)
    resample_params = dict(interpolation='nearest', force_resample=True, copy_header=True)
    out_img = nilearn.image.resample_to_img(source_img=t1_file, target_img=wta_file, **resample_params)
    resampled_t1_meta = provenance.record_step(
        'nilearn.image.resample_to_img',
        inputs={'source_img': provenance.describe(t1_file), 'target_img': provenance.describe(wta_file)},
        parameters=resample_params,
        output_path=resampled_t1_file
    )
    io_utils.save_image(out_img, resampled_t1_file, meta=resampled_t1_meta)
    
    logging.info(f'Done with {sub}/{ses}')


config = dict(
    z_score='nilearn/output/{sub}/{ses}/func/{sub}_{ses}_task-bodyloc_run-1_space-MNI152NLin2009cAsym_desc-z_score-unmasked_stats.nii.gz',
    p_val='nilearn/output/{sub}/{ses}/func/{sub}_{ses}_task-bodyloc_run-1_space-MNI152NLin2009cAsym_desc-p_value-unmasked_stats.nii.gz',
    corr_p_val='nilearn/output/{sub}/{ses}/func/{sub}_{ses}_task-bodyloc_run-1_space-MNI152NLin2009cAsym_desc-p_value_corrected-unmasked_stats.nii.gz',
    atlas_tmpl='atlases_mni/output/{sub}/{ses}/{sub}_{ses}_space-MNI152NLin2009cAsym_desc-aparcDKTaseg_dseg.nii.gz',
    t1_tpl='fmriprep/output/{sub}/{ses}/anat/{sub}_{ses}_space-MNI152NLin2009cAsym_desc-preproc_T1w.nii.gz',
    epi_mask = 'fmriprep/output/{sub}/{ses}/func/{sub}_{ses}_task-bodyloc_run-1_space-MNI152NLin2009cAsym_desc-brain_mask.nii.gz',

    roid_tpl='wta/output/{sub}/{ses}/{sub}_{ses}_task-bodyloc_run-1_space-MNI152NLin2009cAsym_desc-hemi_specific_rois.nii.gz',
    wta_tpl='wta/output/{sub}/{ses}/{sub}_{ses}_task-bodyloc_run-1_space-MNI152NLin2009cAsym_desc-wta.nii.gz',
    segment_tpl='wta/output/{sub}/{ses}/{sub}_{ses}_task-bodyloc_run-1_space-MNI152NLin2009cAsym_desc-wta_segmentation.nii.gz',

    xfm_t1w_mni_tpl='fmriprep/output/{sub}/{ses}/anat/{sub}_{ses}_from-MNI152NLin2009cAsym_to-T1w_mode-image_xfm.h5',
    pial_tpl='fmriprep/output/{sub}/{ses}/anat/{sub}_{ses}_hemi-{hemi}_pial.surf.gii',
    white_tpl='fmriprep/output/{sub}/{ses}/anat/{sub}_{ses}_hemi-{hemi}_white.surf.gii',
    inflated_tpl='fmriprep/output/{sub}/{ses}/anat/{sub}_{ses}_hemi-{hemi}_inflated.surf.gii',
    mni_surf_tpl='fmriprep/output/{sub}/{ses}/anat/{sub}_{ses}_space-MNI152NLin2009cAsym_desc-polymesh_{surf}.gii',
    left_surf_tpl='fmriprep/output/{sub}/{ses}/anat/{sub}_{ses}_space-MNI152NLin2009cAsym_desc-polymesh_{surf}_hemi-L.gii',
    right_surf_tpl='fmriprep/output/{sub}/{ses}/anat/{sub}_{ses}_space-MNI152NLin2009cAsym_desc-polymesh_{surf}_hemi-R.gii',
    sphere_reg_tpl='fmriprep/output/{sub}/{ses}/anat/{sub}_{ses}_hemi-{hemi}_space-fsaverage_desc-reg_sphere.surf.gii',

    projected_tpl='wta/output/{sub}/{ses}/{sub}_{ses}_task-bodyloc_run-1_space-MNI152NLin2009cAsym_desc-surf_wta.gii',
    fsavg_surf_tpl = 'wta/output/{sub}/{ses}/{sub}_{ses}_task-bodyloc_run-1_space-fsaverage_desc-surf_wta_hemi-{hemi}.func.gii',
    plot_mni_tpl='wta/output/{sub}/{ses}/{sub}_{ses}_task-bodyloc_run-1_space-MNI152NLin2009cAsym_desc-projected_plot.png',
    plot_fsavg_tpl='wta/output/{sub}/{ses}/{sub}_{ses}_task-bodyloc_run-1_space-fsaverage_desc-projected_plot.png',
    html_tpl='wta/output/{sub}/{ses}/{sub}_{ses}_task-bodyloc_run-1_space-fsaverage_desc-projected_interactive.html',
    resampled_t1_tpl='wta/output/{sub}/{ses}/{sub}_{ses}_space-MNI152NLin2009cAsym_desc-preproc_resampled_T1w.nii.gz',

    contrasts=[
        "LAvsOthers",
        "LFvsOthers",
        "LHvsOthers",
        "LPvsOthers",
        "RAvsOthers",
        "RFvsOthers",
        "RHvsOthers"
    ],
    roi_regions={
        'both': [
            'ctx-lh-precentral',
            'ctx-rh-precentral',
            'ctx-lh-paracentral',
            'ctx-rh-paracentral'
        ],
        'lh': [
            'ctx-lh-precentral',
            'ctx-lh-paracentral'
        ],
        'rh': [
            'ctx-rh-precentral',
            'ctx-rh-paracentral'
        ]
    },

    no_result_idx=8,

    cmap = [
        "#000000",  # Background (must be included even if it's not shown)
        '#543005',  # LA
        '#8c510a',  # LF
        '#dfc27d',  # LH
        '#b2182b',  # LP
        '#003c30',  # RA
        '#01665e',  # RF
        '#80cdc1',  # RH
        '#f5f5f5'   # Rest
    ],

    alpha = 0.001
)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Create body maps from fMRI data.")
    parser.add_argument("-s", "--sub", type=str, help="Subject ID.")
    parser.add_argument("-e", "--ses", type=str, help="Session ID.")
    parser.add_argument("-d", "--base-dir", type=str, help="Base directory where the data is stored. This should be the root of the derivatives folder.")    
    args = parser.parse_args()

    create_bodymap(args.sub, args.ses, config=config, base_dir=args.base_dir)
