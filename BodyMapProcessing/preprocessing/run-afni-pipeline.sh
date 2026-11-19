#!/bin/bash

# Parse arguments.
PARSED=$(getopt --options "" --long sub:,sess:,session:,data-dir:,der-dir:,output-dir:,dry-run,n-threads:,afni-version: --name "$0" -- "$@")
# Terminate script if failed to parse arguments properly.
if [[ $? -ne 0 ]]; then
    echo "Error parsing options" >&2
    exit 1
fi

# Reset the positional parameters to the parsed arguments.
eval set -- "$PARSED"

SUB=""
SESSION=""
DATA_DIR="."
DER_DIR=""
OUTPUT_DIR=""
DRYRUN=false
AFNI_VERSION="24.3.00"
# Use the max amount of available threads as the default value.
NTHREADS=`nproc`

# Extract values from arguments. `--` indicates the end of arguments.
while true; do
    case "$1" in
        --sub)
            SUB="$2"
            shift 2
            ;;
        --session|--sess)
            SESSION="$2"
            shift 2
            ;;
        --data-dir)
            DATA_DIR="$2"
            shift 2
            ;;
        --der-dir)
            DER_DIR="$2"
            shift 2
            ;;
		--output-dir)
			OUTPUT_DIR="$2"
			shift 2
			;;
        --dry-run)
            DRYRUN=true
            shift
            ;;
        --n-threads)
            NTHREADS="$2"
            shift 2
            ;;
		--afni-version)
			AFNI_VERSION="$2"
			shift 2
			;;
        --)
            shift
            break
            ;;
        *)
            echo "Unexpected option: $1"
            exit 1
            ;;
    esac
done

# Make sure to use the DATA_DIR value that was sepcified in the arguments.
if [[ -z "$DER_DIR" ]]; then
    DER_DIR="${DATA_DIR}/derivatives"
fi
if [[ -z "$OUTPUT_DIR" ]]; then
    OUTPUT_DIR="${DER_DIR}/afni/output"
fi

# Check that required arguments are present. If not terminate the script.
if [[ -z "$SUB" || -z "$SESSION" ]]; then
    echo "Error: Both --sub and --sess/--session are required"
    exit 1
fi

MODULE=afni/$AFNI_VERSION
# Provide a better error message if the module does not exist.
if ! module avail $MODULE 2>&1 | grep -q "$MODULE"; then
    echo "Module ${MODULE} could not be found. Make sure that it is downloaded
and that you used 'module use <path/to/neurodesk/containers>' before running
this."
    exit 1
fi
module load $MODULE

# Set up directories
DATA_BASE_DIR=$DATA_DIR/$SUB/$SESSION

# This must use .nii.gz extension. Otherwise you get an error that it does not
# exist.
ANAT_SS=$DER_DIR/fastsurfer/output/$SUB/$SESSION/mri/brain.nii.gz
FSCSF=$DER_DIR/fastsurfer/output/$SUB/$SESSION/SUMA/fs_custom_csf.nii.gz
FSWM=$DER_DIR/fastsurfer/output/$SUB/$SESSION/SUMA/fs_custom_wm.nii.gz
# Get also anatomical for skull so we can have it warped the same as the
# skull-stripped version.
ANAT_RAW=$DER_DIR/fastsurfer/output/$SUB/$SESSION/mri/orig.nii.gz

FUNC_DIR=$DATA_BASE_DIR/func
FUNC_BASE="$FUNC_DIR/${SUB}_${SESSION}_task-BODYLOC_run-1_bold.nii.gz"
STIM_DATA="$FUNC_DIR/${SUB}_${SESSION}_task-BODYLOC_run-1_events.tsv"

# Set blur
BLUR_SIZE=3

# This directory cannot exist otherwise AFNI will complain and won't run.
AFNI_DIR=$OUTPUT_DIR/$SUB/$SESSION

# Stimuli for regression. Parse BIDS into what AFNI needs.
# AFNI copies the stimulus onset files into the results by default therefore, no
# need have them persist when creating with 'timing_tool.py'.
AFNI_STIM_DIR=$(mktemp -d --tmpdir="$OUTPUT_DIR")
trap 'rm -rf "$AFNI_STIM_DIR"' EXIT
timing_tool.py -tsv_labels onset duration trial_type -multi_timing_ncol_tsv $STIM_DATA -write_multi_timing $AFNI_STIM_DIR/${SUB}_${SESSION}_task-BODYLOC_run-1_
if [ $? -ne 0 ]; then
	echo "Error converting the timing file to AFNI timing files in ${SUB}/${SESSION}. Does the file exist?"
	exit 1
fi
STIM1_LA=$AFNI_STIM_DIR/${SUB}_${SESSION}_task-BODYLOC_run-1_times.left_arm.txt
STIM2_LF=$AFNI_STIM_DIR/${SUB}_${SESSION}_task-BODYLOC_run-1_times.left_foot.txt
STIM3_LH=$AFNI_STIM_DIR/${SUB}_${SESSION}_task-BODYLOC_run-1_times.left_hand.txt
STIM4_LP=$AFNI_STIM_DIR/${SUB}_${SESSION}_task-BODYLOC_run-1_times.lips.txt
STIM5_RA=$AFNI_STIM_DIR/${SUB}_${SESSION}_task-BODYLOC_run-1_times.right_arm.txt
STIM6_RF=$AFNI_STIM_DIR/${SUB}_${SESSION}_task-BODYLOC_run-1_times.right_foot.txt
STIM7_RH=$AFNI_STIM_DIR/${SUB}_${SESSION}_task-BODYLOC_run-1_times.right_hand.txt

# Script
if [ "$DRYRUN" = true ]; then
	AFNI_CMD="
	afni_proc.py
		-subj_id					${SUB}_${SESSION}
		-out_dir					$AFNI_DIR
		-dsets						$FUNC_BASE
		-blocks						tcat despike align tlrc volreg mask blur scale regress
		-radial_correlate_blocks	tcat volreg regress
		-copy_anat					$ANAT_SS
		-anat_has_skull				no
		-anat_follower				orig_anat_w_skull anat $ANAT_RAW
		-anat_follower_ROI			FSCSFe epi $FSCSF
		-anat_follower_ROI			FSWMe epi $FSWM
		-anat_follower_erode		FSCSFe FSWMe
		-tcat_remove_first_trs		0
		-align_opts_aea				-giant_move
									-partial_coverage
									-cost lpc+ZZ
		-align_unifize_epi			local
		-tlrc_base					MNI152_2009_template_SSW.nii.gz
		-tlrc_no_ss
		-tlrc_NL_warp
		-volreg_align_e2a
		-volreg_align_to			MIN_OUTLIER
		-volreg_allin_warp			affine_general
		-volreg_tlrc_warp
		-volreg_post_vr_allin		yes
		-volreg_pvra_base_index		MIN_OUTLIER
		-volreg_interp				-Fourier
		-volreg_warp_final_interp	wsinc5
		-volreg_compute_tsnr		yes
		-blur_size					$BLUR_SIZE
		-regress_local_times
		-regress_stim_times
									$STIM1_LA
									$STIM2_LF
									$STIM3_LH
									$STIM4_LP
									$STIM5_RA
									$STIM6_RF
									$STIM7_RH
		-regress_stim_labels		LA
									LF
									LH
									LP
									RA
									RF
									RH
		-regress_basis				'BLOCK(9.9,1)'
		-regress_opts_3dD			-bout
									-gltsym 'SYM: LA -0.16667*LF -0.16667*LH -0.16667*LP -0.16667*RA -0.16667*RF -0.16667*RH'
									-glt_label 1 LA-others
									-gltsym 'SYM: LF -0.16667*LA -0.16667*LH -0.16667*LP -0.16667*RA -0.16667*RF -0.16667*RH'
									-glt_label 2 LF-others
									-gltsym 'SYM: LH -0.16667*LA -0.16667*LF -0.16667*LP -0.16667*RA -0.16667*RF -0.16667*RH'
									-glt_label 3 LH-others
									-gltsym 'SYM: LP -0.16667*LA -0.16667*LF -0.16667*LH -0.16667*RA -0.16667*RF -0.16667*RH'
									-glt_label 4 LP-others
									-gltsym 'SYM: RA -0.16667*LA -0.16667*LF -0.16667*LH -0.16667*LP -0.16667*RF -0.16667*RH'
									-glt_label 5 RA-others
									-gltsym 'SYM: RF -0.16667*LA -0.16667*LF -0.16667*LH -0.16667*LP -0.16667*RA -0.16667*RH'
									-glt_label 6 RF-others
									-gltsym 'SYM: RH -0.16667*LA -0.16667*LF -0.16667*LH -0.16667*LP -0.16667*RA -0.16667*RF'
									-glt_label 7 RH-others
									-jobs $NTHREADS
		-regress_censor_motion		0.3
		-regress_censor_outliers	0.05
		-regress_make_ideal_sum		sum_ideal.1D
		-regress_anaticor_fast
		-regress_anaticor_label		FSWMe
		-regress_ROI_PC				FSCSFe 3
		-regress_3dD_stop
		-regress_reml_exec
		-regress_est_blur_epits
		-regress_est_blur_errts
		-html_review_style			pythonic
		-execute
	"
	echo "$AFNI_CMD"
else
	afni_proc.py 																												\
		-subj_id 					${SUB}_${SESSION} 																			\
		-out_dir					$AFNI_DIR																					\
		-dsets 						$FUNC_BASE						 															\
		-blocks                   	tcat despike align tlrc volreg mask blur scale regress										\
		-radial_correlate_blocks  	tcat volreg regress																			\
		-copy_anat 					$ANAT_SS																					\
		-anat_has_skull 			no 																							\
		-anat_follower 				orig_anat_w_skull anat $ANAT_RAW						 									\
		-anat_follower_ROI        	FSCSFe epi $FSCSF																			\
		-anat_follower_ROI        	FSWMe epi $FSWM																				\
		-anat_follower_erode      	FSCSFe FSWMe																				\
		-tcat_remove_first_trs 		0 																							\
		-align_opts_aea 			-giant_move 																				\
									-partial_coverage 																			\
									-cost lpc+ZZ 																				\
		-align_unifize_epi 			local 																						\
		-tlrc_base                  MNI152_2009_template_SSW.nii.gz 															\
		-tlrc_no_ss 																											\
		-tlrc_NL_warp 																											\
		-volreg_align_e2a 																										\
		-volreg_align_to 			MIN_OUTLIER 																				\
        -volreg_allin_warp          affine_general                                                                              \
		-volreg_tlrc_warp 																										\
		-volreg_post_vr_allin 		yes 																						\
		-volreg_pvra_base_index  	MIN_OUTLIER 																				\
		-volreg_interp 				-Fourier 																					\
		-volreg_warp_final_interp  	wsinc5 																						\
		-volreg_compute_tsnr 		yes 																						\
		-mask_epi_anat            	yes																							\
		-blur_size 					$BLUR_SIZE 																					\
		-regress_local_times																									\
		-regress_stim_times 																									\
									$STIM1_LA																					\
									$STIM2_LF																					\
									$STIM3_LH																					\
									$STIM4_LP																					\
									$STIM5_RA																					\
									$STIM6_RF																					\
									$STIM7_RH																					\
		-regress_stim_labels		LA																							\
									LF																							\
									LH																							\
									LP																							\
									RA																							\
									RF																							\
									RH																							\
		-regress_basis				'BLOCK(9.9,1)'																				\
		-regress_opts_3dD			-bout 																						\
									-gltsym 'SYM: LA -0.16667*LF -0.16667*LH -0.16667*LP -0.16667*RA -0.16667*RF -0.16667*RH'	\
									-glt_label 1 LA-others																		\
									-gltsym 'SYM: LF -0.16667*LA -0.16667*LH -0.16667*LP -0.16667*RA -0.16667*RF -0.16667*RH'	\
									-glt_label 2 LF-others																		\
									-gltsym 'SYM: LH -0.16667*LA -0.16667*LF -0.16667*LP -0.16667*RA -0.16667*RF -0.16667*RH'	\
									-glt_label 3 LH-others																		\
									-gltsym 'SYM: LP -0.16667*LA -0.16667*LF -0.16667*LH -0.16667*RA -0.16667*RF -0.16667*RH'	\
									-glt_label 4 LP-others																		\
									-gltsym 'SYM: RA -0.16667*LA -0.16667*LF -0.16667*LH -0.16667*LP -0.16667*RF -0.16667*RH'	\
									-glt_label 5 RA-others																		\
									-gltsym 'SYM: RF -0.16667*LA -0.16667*LF -0.16667*LH -0.16667*LP -0.16667*RA -0.16667*RH'	\
									-glt_label 6 RF-others																		\
									-gltsym 'SYM: RH -0.16667*LA -0.16667*LF -0.16667*LH -0.16667*LP -0.16667*RA -0.16667*RF'	\
									-glt_label 7 RH-others																		\
									-jobs $NTHREADS																				\
		-regress_censor_motion		0.3																							\
		-regress_censor_outliers	0.05																						\
		-regress_make_ideal_sum		sum_ideal.1D																				\
		-regress_anaticor_fast 																									\
		-regress_anaticor_label 	FSWMe 																						\
		-regress_ROI_PC         	FSCSFe 3 																					\
		-regress_3dD_stop														                                                \
		-regress_reml_exec																										\
		-regress_est_blur_epits															                                        \
		-regress_est_blur_errts																									\
		-html_review_style 			pythonic																					\
		-execute
fi