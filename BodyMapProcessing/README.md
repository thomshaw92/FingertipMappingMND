# BodyMapProcessing

Processing code for the body localiser fMRI (`task-bodyloc`), whose stimulus script is in
`BehaviouralTasks/BodyLocaliser/`. The scripts read BIDS data and write derivatives. Most shell
scripts take `--sub` and `--session`, and `--dry-run` prints the commands without running them.

## preprocessing/

Surface reconstruction, fMRIPrep and first-level model:

| Script | What it does |
|---|---|
| `run-long-fastsurfer.sh` | Longitudinal FastSurfer reconstruction across a subject's sessions |
| `run-fastsurfer.sh` | Single-session FastSurfer reconstruction |
| `run-fmriprep.sh` | fMRIPrep with the FastSurfer output as its FreeSurfer subjects directory, output in MNI152NLin2009cAsym |
| `run-regression.py` | First-level GLM in nilearn on the fMRIPrep output; contrasts, motion censoring, smoothing and masking are set in `regress_config_mask.json` or `regress_config_nomask.json` |
| `atlas.py` | Adds Glasser 2016 and HMAT 2006 atlas fetchers to `nilearn.datasets`; imported by `run-regression.py` |

FreeSurfer `recon-all-clinical` and AFNI:

| Script | What it does |
|---|---|
| `recon-all-clinical-master.sh` | Runs the three scripts below for every subject and session; run it from inside `preprocessing/` |
| `run-recon-all-clinical.sh` | FreeSurfer `recon-all-clinical` |
| `run-suma.sh` | SUMA surface files plus white matter and CSF masks from the FreeSurfer segmentation |
| `cleanup.sh` | Zips a session's output into `contents.zip` and keeps only the files in a keep list such as `bodymap-keep-files.txt` |
| `repack.sh` | Restores selected files from `contents.zip` |
| `run-afni-pipeline.sh` | `afni_proc.py` preprocessing |
| `run-ants-registration.sh` | ANTs SyN registration to the MNI template |
| `extract-mni-template.sh` | Extracts that MNI template from the AFNI atlas distribution |
