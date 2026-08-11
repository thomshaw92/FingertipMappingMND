from pathlib import Path
import nibabel as nib
import nilearn
import shutil
import logging
import argparse

import io_utils
import analysis

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

    logging.info('Correcting images')
    p_val_file = base_dir / p_val.format(sub=sub, ses=ses)
    corr_p_val_file = base_dir / corr_p_val.format(sub=sub, ses=ses)
    analysis.correct_images(
        p_val_file,
        alpha=alpha,
        output_path=corr_p_val_file
    )

    logging.info('Thresholding image')
    _, thresh_meta, thresh_dict = analysis.threshold_images(
        file,
        corr_p_val_file,
        meta=None,
        alpha=alpha,
        output_path=False,
        load_errors='raise',
        thresh_val=999
    )

    logging.info('Extracting ROIs')
    roi_imgs = []
    for contr in contrasts:
        img = thresh_dict[contr]

        if contr.startswith('LP'):
            contr_regions = roi_regions['both']
        elif contr.startswith('L'):
            # Should be contralateral to the movement.
            contr_regions = roi_regions['rh']
        else:
            contr_regions = roi_regions['lh']
        
        roi_img, roi_meta = analysis.roi_single_image(
            img,
            meta=thresh_meta,
            regions=contr_regions,
            atlas=atlas_file,
            output_path=False,
            outside_val=-999.0
        )

        roi_imgs.append(roi_img)

    logging.info('Concatenating images')
    imgs = nib.concat_images(roi_imgs)
    if imgs.shape[-1] != len(contrasts):
        raise ValueError(f'Images have not been concatenated along the 4th dimension. The concatenated image shape: {imgs.shape}')
    roid_file = base_dir / roid_tpl.format(sub=sub, ses=ses)
    io_utils.save_image(imgs, roid_file, meta=roi_meta)

    logging.info('Applying WTA')
    wta_file = base_dir / wta_tpl.format(sub=sub, ses=ses)
    wta_img, wta_meta = analysis.apply_over_time(
        img=imgs,
        func=analysis.wta,
        meta={'source_meta': roi_meta},
        outside_val=-999.0,
        below_thresh_val=999,
        no_result_idx=no_result_idx,
        output_path=wta_file
    )

    logging.info('Saving as segmentation')
    labels = {contr_idx+1: contr for contr_idx, contr in enumerate(contrasts)}
    labels[0] = 'Outside ROI'
    labels[no_result_idx] = 'Rest'
    seg_img, seg_meta = analysis.save_as_segmentation(
        img=wta_img,
        meta={'source_meta': wta_meta},
        labels=labels,
        output_path=base_dir / segment_tpl.format(sub=sub, ses=ses)
    )

    logging.info('Transforming surfaces to MNI')
    xfm_t1w_mni = base_dir / xfm_t1w_mni_tpl.format(sub=sub, ses=ses)
    for surf in ('pial', 'white'):
        surf_files = {}
        for hemi in ('left', 'right'):
            tpl = pial_tpl if surf == 'pial' else white_tpl
            s_file = base_dir / tpl.format(sub=sub, ses=ses, hemi='L' if hemi == 'left' else 'R')
            surf_files[f'{hemi}_surf'] = s_file

        output_path = base_dir / mni_surf_tpl.format(sub=sub, ses=ses, surf=surf)
        polymesh, _ = analysis.transform_surface_to_mni(xfm_t1w_mni=xfm_t1w_mni, output_path=output_path, **surf_files)
        if surf == 'pial':
            pial_polymesh = polymesh
        else:
            white_polymesh = polymesh
    
    logging.info('Projecting image')
    projected_file = base_dir / projected_tpl.format(sub=sub, ses=ses)
    proj_img, proj_meta = analysis.project_image(
        wta_file,
        meta=None,
        output_path=projected_file,
        interpolation='nearest_most_frequent',
        kind='depth',
        n_samples=20,
        mesh=pial_polymesh,
        inner_mesh=white_polymesh
    )

    logging.info('Saving as PNG')
    plot, meta = analysis.make_plot(
        projected_file,
        meta=proj_meta,
        output_path=base_dir / plot_tpl.format(sub=sub, ses=ses),
        hemi='both',
        cmap=cmap,
        vmin=0,
        vmax=8,
        symmetric_cbar=False,
        colorbar=True,
        mesh=pial_polymesh,
        colorbar_labels=contrasts,
        view='dorsal',
    )

    logging.info('Saving as HTML')
    display, meta = analysis.make_html2(
        projected_file,
        meta=proj_meta,
        output_path=base_dir / html_tpl.format(sub=sub, ses=ses),
        hemi='both',
        cmap=cmap,
        vmin=0,
        vmax=8,
        symmetric_cbar=False,
        colorbar=True,
        mesh=pial_polymesh,
        colorbar_labels=contrasts
    )

    logging.info('Copying files')
    shutil.copyfile(file, f'./{file.name}')
    shutil.copyfile(atlas_file, f'./{atlas_file.name}')
    shutil.copyfile(base_dir / f'fmriprep/output/{sub}/{ses}/anat/{sub}_{ses}_space-MNI152NLin2009cAsym_desc-preproc_T1w.nii.gz', f'./{sub}_{ses}_space-MNI152NLin2009cAsym_desc-preproc_T1w.nii.gz')

    logging.info('Resampling T1')
    out_img = nilearn.image.resample_to_img(
        source_img=base_dir / t1_tpl.format(sub=sub, ses=ses),
        target_img=wta_file,
        interpolation='nearest',
        force_resample=True,
        copy_header=True,
    )
    nib.save(out_img, base_dir / resampled_t1_tpl.format(sub=sub, ses=ses))
    
    logging.info(f'Done with {sub}/{ses}')


config = dict(
    z_score='nilearn/output/{sub}/{ses}/func/{sub}_{ses}_task-bodyloc_run-1_space-MNI152NLin2009cAsym_desc-z_score-unmasked_stats.nii.gz',
    p_val='nilearn/output/{sub}/{ses}/func/{sub}_{ses}_task-bodyloc_run-1_space-MNI152NLin2009cAsym_desc-p_value-unmasked_stats.nii.gz',
    corr_p_val='nilearn/output/{sub}/{ses}/func/{sub}_{ses}_task-bodyloc_run-1_space-MNI152NLin2009cAsym_desc-p_value_corrected-unmasked_stats.nii.gz',
    atlas_tmpl='atlases_mni/output/{sub}/{ses}/{sub}_{ses}_space-MNI152NLin2009cAsym_desc-aparcDKTaseg_dseg.nii.gz',
    t1_tpl='fmriprep/output/{sub}/{ses}/anat/{sub}_{ses}_space-MNI152NLin2009cAsym_desc-preproc_T1w.nii.gz',

    roid_tpl='wta/output/{sub}/{ses}/{sub}_{ses}_task-bodyloc_run-1_space-MNI152NLin2009cAsym_desc-hemi_specific_rois.nii.gz',
    wta_tpl='wta/output/{sub}/{ses}/{sub}_{ses}_task-bodyloc_run-1_space-MNI152NLin2009cAsym_desc-wta.nii.gz',
    segment_tpl='wta/output/{sub}/{ses}/{sub}_{ses}_task-bodyloc_run-1_space-MNI152NLin2009cAsym_desc-wta_segmentation.nii.gz',

    xfm_t1w_mni_tpl='fmriprep/output/{sub}/{ses}/anat/{sub}_{ses}_from-MNI152NLin2009cAsym_to-T1w_mode-image_xfm.h5',
    pial_tpl='fmriprep/output/{sub}/{ses}/anat/{sub}_{ses}_hemi-{hemi}_pial.surf.gii',
    white_tpl='fmriprep/output/{sub}/{ses}/anat/{sub}_{ses}_hemi-{hemi}_white.surf.gii',
    mni_surf_tpl='fmriprep/output/{sub}/{ses}/anat/{sub}_{ses}_space-MNI152NLin2009cAsym_desc-polymesh_{surf}.gii',
    left_surf_tpl='fmriprep/output/{sub}/{ses}/anat/{sub}_{ses}_space-MNI152NLin2009cAsym_desc-polymesh_{surf}_hemi-L.gii',
    right_surf_tpl='fmriprep/output/{sub}/{ses}/anat/{sub}_{ses}_space-MNI152NLin2009cAsym_desc-polymesh_{surf}_hemi-R.gii',

    projected_tpl='wta/output/{sub}/{ses}/{sub}_{ses}_task-bodyloc_run-1_space-MNI152NLin2009cAsym_desc-wta.gii',
    plot_tpl='wta/output/{sub}/{ses}/{sub}_{ses}_task-bodyloc_run-1_space-MNI152NLin2009cAsym_desc-projected_plot.png',
    html_tpl='wta/output/{sub}/{ses}/{sub}_{ses}_task-bodyloc_run-1_space-MNI152NLin2009cAsym_desc-projected_plot.html',
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

    cmap = ListedColormap([
        "#E41A1C",  # red
        "#377EB8",  # blue
        "#4DAF4A",  # green
        "#984EA3",  # purple
        "#FF7F00",  # orange
        "#FFFF33",  # yellow
        "#A65628",  # brown
        "#F781BF",  # pink
        "#17BECF",  # cyan
    ]),

    alpha = 0.001
)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Create body maps from fMRI data.")
    parser.add_argument("-s", "--sub", type=str, help="Subject ID.")
    parser.add_argument("-e", "--ses", type=str, help="Session ID.")
    parser.add_argument("-d", "--base-dir", type=str, help="Base directory where the data is stored. This should be the root of the derivatives folder.")    
    args = parser.parse_args()

    create_bodymap(args.sub, args.ses, config=config, base_dir=args.base_dir)
