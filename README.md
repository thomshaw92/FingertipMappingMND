# BodyRepresentationsMND

Code for MND body representation studies: experimental tasks, fingertip mapping fMRI, and body map processing.

| Folder | Contents |
|---|---|
| `BehaviouralTasks/FingertipTapping/` | PsychoPy fingertip tapping speed task |
| `BehaviouralTasks/VibrotactileDiscrimination/` | MATLAB out-of-scanner vibrotactile discrimination task with psychometric curve fitting |
| `BehaviouralTasks/BodyLocaliser/` | MATLAB in-scanner body localiser task |
| `BehaviouralTasks/SOP/` | Hand and finger testing battery protocol, and sound card settings for the stimulus PC |
| `FingertipMapping/Task/` | MATLAB vibrotactile fingertip mapping task |
| `FingertipMapping/Columns/` | MATLAB vibrotactile oddball task |
| `FingertipMapping/Preprocessing/` | AFNI preprocessing (despiking, anatomy-to-EPI alignment, motion correction, scaling), used by both fingertip mapping and Columns |
| `BodyMapProcessing/` | Processing of the body localiser fMRI; see its README |

The MATLAB tasks save to a `Data` folder in their own folder (the vibrotactile task uses the current folder, so run it from its own folder). `Data` folders are not tracked.
