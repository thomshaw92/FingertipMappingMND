#!/bin/bash

# Parse arguments.
PARSED=$(getopt --options "" --long output-dir:,dry-run,afni-version:,template:,temp-dir: --name "$0" -- "$@")
# Terminate script if failed to parse arguments properly.
if [[ $? -ne 0 ]]; then
    echo "Error parsing options" >&2
    exit 1
fi

# Reset the positional parameters to the parsed arguments.
eval set -- "$PARSED"

OUTPUT_DIR="."
DRYRUN=false
AFNI_VERSION="24.3.00"
TEMPLATE="MNI152_2009_template_SSW.nii.gz"
TEMP_DIR="/tmp/afni_atlases"

# Extract values from arguments. `--` indicates the end of arguments.
while true; do
    case "$1" in
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
        --template)
            TEMPLATE="$2"
            shift 2
            ;;
        --temp-dir)
            TEMP_DIR="$2"
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

MODULE=afni/$ANTS_VERSION
# Provide a better error message if the module does not exist.
if ! module avail $MODULE 2>&1 | grep -q "$MODULE"; then
    echo "Module ${MODULE} could not be found. Make sure that it is downloaded
and that you used 'module use <path/to/neurodesk/containers>' before running
this."
    exit 1
fi
module load $MODULE

# Extract the extension - also include double extensions
# (e.g., nii.gz).
extension=".${TEMPLATE#*.}"
filename="${TEMPLATE%$extension}"

if [ "$DRYRUN" = true ]; then
    EXTRACT_CMD="
    mkdir -p $TEMP_DIR

    wget https://afni.nimh.nih.gov/pub/dist/atlases/afni_atlases_dist.tgz -O $TEMP_DIR/afni_atlases_dist.tgz
    tar -xzvf $TEMP_DIR/afni_atlases_dist.tgz -C $TEMP_DIR afni_atlases_dist/$TEMPLATE
    3dTcat -prefix \"$OUTPUT_DIR/${filename}_brain${extension}\" $TEMP_DIR/afni_atlases_dist/$TEMPLATE'[0]'
    rm -r $TEMP_DIR
    "
    echo "$EXTRACT_CMD"
else
    mkdir -p $TEMP_DIR

    wget https://afni.nimh.nih.gov/pub/dist/atlases/afni_atlases_dist.tgz -O $TEMP_DIR/afni_atlases_dist.tgz
    tar -xzvf $TEMP_DIR/afni_atlases_dist.tgz -C $TEMP_DIR afni_atlases_dist/$TEMPLATE
    # Extract only the skull-stripped brain - the first component.
    3dTcat -prefix "$OUTPUT_DIR/${filename}_brain${extension}" $TEMP_DIR/afni_atlases_dist/$TEMPLATE'[0]'
    rm -r $TEMP_DIR
fi