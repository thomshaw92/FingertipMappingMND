#!/bin/bash

# Parse arguments.
PARSED=$(getopt --options "" --long sub:,sess:,sessions:,data-dir:,output-dir:,fast-dir:,dry-run,n-threads: --name "$0" -- "$@")
# Terminate script if failed to parse arguments properly.
if [[ $? -ne 0 ]]; then
    echo "Error parsing options" >&2
    exit 1
fi

# Reset the positional parameters to the parsed arguments.
eval set -- "$PARSED"

SUB=""
SESSIONS=()
DATA_DIR="."
FAST_DIR=""
OUTPUT_DIR=""
DRYRUN=false
# Use the max amount of available threads as the default value.
NTHREADS=`nproc`

# Extract values from arguments. `--` indicates the end of arguments.
while true; do
    case "$1" in
        --sub)
            SUB="$2"
            shift 2
            ;;
        --sessions|--sess)
            IFS=',' read -ra SESSIONS <<< "$2"
            shift 2
            ;;
        --data-dir)
            DATA_DIR="$2"
            shift 2
            ;;
        --fast-dir)
            FAST_DIR="$2"
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
        --output-dir)
            OUTPUT_DIR="$2"
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
if [[ -z "$FAST_DIR" ]]; then
    FAST_DIR="${DATA_DIR}/fastsurfer"
fi
if [[ -z "$OUTPUT_DIR" ]]; then
    OUTPUT_DIR="${DATA_DIR}/fastsurfer/output"
fi

# Check that required arguments are present. If not terminate the script.
if [[ -z "$SUB" || -z "$SESSIONS" ]]; then
    echo "Error: Both --sub and --sess/--sessions are required"
    exit 1
fi

# The within-container mount point is defined here so that it can be
# used to construct within-container paths to images.
inside_data_dir="/data"
images=()
ses_ids=()
for ses in "${SESSIONS[@]}"; do
    images+=("$inside_data_dir/$SUB/$ses/anat/${SUB}_${ses}_acq-UNIDEN_run-1_T1w.nii.gz")
    ses_ids+=("${SUB}_${ses}")
done

if [ "$DRYRUN" = true ]; then
    SING_COMMAND="
    singularity exec --nv --no-mount home,cwd -e
                     -B $DATA_DIR:$inside_data_dir
                     -B $FAST_DIR:/fs
                     -B $OUTPUT_DIR:/output
                     --env SUBJECTS_DIR=""
                     $FAST_DIR/fastsurfer-latest.sif
                     /fastsurfer/long_fastsurfer.sh
                     --fs_license /fs/license.txt
                     --tid $SUB
                     --t1s ${images[@]}
                     --tpids ${ses_ids[@]}
                     --sd /output
                     --3T
                     --threads $NTHREADS
    "
    echo "$SING_COMMAND"
else
    singularity exec --nv --no-mount home,cwd -e        \
                     -B $DATA_DIR:$inside_data_dir      \
                     -B $FAST_DIR:/fs                   \
                     -B $OUTPUT_DIR:/output             \
                     --env SUBJECTS_DIR=""              \
                     $FAST_DIR/fastsurfer-latest.sif    \
                     /fastsurfer/long_fastsurfer.sh     \
                     --fs_license /fs/license.txt       \
                     --tid $SUB                         \
                     --t1s "${images[@]}"               \
                     --tpids "${ses_ids[@]}"            \
                     --sd /output                       \
                     --3T                               \
                     --threads $NTHREADS
fi