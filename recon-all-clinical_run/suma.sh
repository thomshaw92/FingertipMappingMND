#!/bin/bash

# Parse arguments.
PARSED=$(getopt --options "" --long sub:,sess:,session:,data-dir:,output-dir:,dry-run,afni-version: --name "$0" -- "$@")
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
OUTPUT_DIR=""
DRYRUN=false
AFNI_VERSION="24.3.00"

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
        --output-dir)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --dry-run)
            DRYRUN=true
            shift
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

# Make sure to use the DATA_DIR value that was specified in the arguments.
if [[ -z "$OUTPUT_DIR" ]]; then
    OUTPUT_DIR="${DATA_DIR}/recon-all-clinical"
fi

# Check that required arguments are present. If not terminate the script.
if [[ -z "$SUB" || -z "$SESSION" ]]; then
    echo "ERROR: Both --sub and --sess/--session are required"
    exit 1
fi

# Setting this env variable is strongly recommended but I don't understand why.
# It works even without it.
# SINGULARITY_BINDPATH=$OUTPUT_DIR,$BASE_DIR,$SINGULARITY_BINDPATH
# echo $SINGULARITY_BINDPATH

MODULE=afni/$AFNI_VERSION
# Provide a better error message if the module does not exist.
if ! module avail $MODULE 2>&1 | grep -q "$MODULE"; then
    echo "ERROR: Module ${MODULE} could not be found. Make sure that it is downloaded
and that you used 'module use <path/to/neurodesk/containers>' before running this."
    exit 1
fi
module load $MODULE

# Where output will be stored.
RESULT_DIR=$OUTPUT_DIR/output/$SUB/$SESSION

# Regions for CSF mask.
CSF_REGIONS="\
Left-Lateral-Ventricle,\
Right-Lateral-Ventricle"

# Regions for WM mask (based on what AFNI selects in @SUMA_Make_Spec_FS).
WM_REGIONS="\
Left-Cerebral-White-Matter,\
Right-Cerebral-White-Matter,\
CC_Posterior,\
CC_Mid_Posterior,\
CC_Central,\
CC_Mid_Anterior,\
CC_Anterior"

if [[ "$DRYRUN" = true ]]; then
    SUMMARY="
    mkdir -p $RESULT_DIR/SUMA
    mkdir -p $RESULT_DIR/orig
    cp $RESULT_DIR/mri/native.mgz $RESULT_DIR/mri/orig.mgz
    @SUMA_Make_Spec_FS -NIFTI -fspath $RESULT_DIR -sid \"${SUB}_${SESSION}\"

    3dcalc -a \"$RESULT_DIR/SUMA/aparc+aseg.nii<${WM_REGIONS}>\" -datum byte -expr 'step(a)' -prefix $RESULT_DIR/SUMA/fs_custom_wm.nii.gz
    3dcalc -a \"$RESULT_DIR/SUMA/aparc+aseg.nii<${CSF_REGIONS}>\" -datum byte -expr 'step(a)' -prefix $RESULT_DIR/SUMA/fs_custom_csf.nii.gz
    "

    echo "$SUMMARY"
else
    # Create all the files needed for SUMA.
    mkdir -p $RESULT_DIR/SUMA
    mkdir -p $RESULT_DIR/orig
    cp $RESULT_DIR/mri/native.mgz $RESULT_DIR/mri/orig.mgz
    @SUMA_Make_Spec_FS -NIFTI -fspath $RESULT_DIR -sid "${SUB}_${SESSION}"

    # @SUMA_Make_Spec_FS creates this file and inserts a table that maps
    # values/label numbers to labels. This makes it possible to select regions
    # based on labels. For the commands used see
    # '3dinfo <path/to/SUMA/folder>/aparc+aseg.nii.gz'.
    if [[ ! -f "$RESULT_DIR/SUMA/aparc+aseg.nii.gz" ]]; then
        echo "ERROR: Segmentation file aparc+aseg.nii.gz does not exist. '@SUMA_Make_Spec_FS' should have created this."
        exit 1
    fi

    # This was largely taken from what AFNI does already - see
    # '3dinfo <path/to/SUMA/folder>/fs_ap_wm.nii.gz'.
    3dcalc -a "$RESULT_DIR/SUMA/aparc+aseg.nii<${WM_REGIONS}>" -datum byte -expr 'step(a)' -prefix $RESULT_DIR/SUMA/fs_custom_wm.nii.gz
    3dcalc -a "$RESULT_DIR/SUMA/aparc+aseg.nii<${CSF_REGIONS}>" -datum byte -expr 'step(a)' -prefix $RESULT_DIR/SUMA/fs_custom_csf.nii.gz
fi
