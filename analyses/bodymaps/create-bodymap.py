"""
Create body maps (winner-take-all maps of body-part contrasts) for one
subject and session, in the volume and on the surface.

Paths, contrasts and the steps to run come from a YAML config (by
default ``bodymap.yaml`` next to this script). Steps run in the order
they are listed. Every step names its inputs and outputs (entries of
``paths``), so the config defines how steps are chained, and the same
step type can be listed several times with different settings. A step
with ``enabled: false`` is skipped; steps reading its outputs then use
the files already on disk.
"""
import sys
from collections import namedtuple
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent / 'utils'))

import argparse
import inspect
import logging
import shutil

import nilearn.image
import nilearn.surface
import yaml

import io_utils
import plotting
import provenance
import surface
import volume


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    force=True,
    # handlers=[
    #     logging.FileHandler(logfile),
    # ]
)

DEFAULT_CONFIG = Path(__file__).with_name('bodymap.yaml')

# Values marking voxels below threshold and outside the ROI. They only
# need to differ from each other and from real z-scores.
BELOW_THRESH = 999
OUTSIDE_ROI = -999.0

HEMIS = {'left': 'L', 'right': 'R'}


class Context:
    """
    Subject, session, base directory and config of a run, with values
    derived from the config.
    """
    def __init__(self, sub, ses, base_dir, config):
        self.sub = sub
        self.ses = ses
        self.base_dir = Path(base_dir)
        self.config = config
        self.contrasts = list(config['contrasts'])
        # Label 0 is outside the ROI, contrasts are 1..n, then Rest.
        self.no_result_idx = len(self.contrasts) + 1
        self.plot_labels = self.contrasts + ['Rest']
        # One colour per label, starting with the background.
        self.colors = (
            [config['background_color']]
            + [spec['color'] for spec in config['contrasts'].values()]
            + [config['rest_color']]
        )
        self.fsaverage = config['fsaverage']

    def path(self, name, **fields):
        """Path of the config path template ``name``."""
        fields = {'sub': self.sub, 'ses': self.ses, **fields}
        variables = {key: value.format(**fields) for key, value in self.config.get('variables', {}).items()}
        return self.base_dir / self.config['paths'][name].format(**fields, **variables)

    def regions(self, name):
        """Atlas regions of the region set ``name``."""
        return self.config['regions'][name]

    def label_plot_kwargs(self):
        """Arguments shared by all plots of the WTA labels."""
        return dict(
            cmap=self.colors,
            cmap_bg_first=True,
            colorbar=True,
            colorbar_labels=self.plot_labels,
            vmin=1,
            vmax=len(self.plot_labels),
        )


class Step:
    """
    One entry of the ``steps`` list in the config, with access to the
    paths of its input and output roles.
    """
    def __init__(self, ctx, spec):
        self.ctx = ctx
        self.type = spec['type']
        self.name = spec.get('name', self.type)
        self.enabled = spec.get('enabled', True)
        self.inputs = spec['inputs']
        self.outputs = spec['outputs']
        self.params = dict(spec.get('params') or {})

    def input(self, role, **fields):
        """
        Path of an input role. Checks that the file exists, so that a
        missing output of a disabled step gives a clear error.

        Surface images saved with ``io_utils.save_surface`` have no file
        at their base path (only per-hemisphere files and a sidecar), so
        for ``.gii`` paths an existing sidecar also counts.
        """
        path = self.ctx.path(self.inputs[role], **fields)
        is_saved_surface = path.suffix == '.gii' and io_utils.load_sidecar(path, errors='ignore') is not None
        if not path.exists() and not is_saved_surface:
            raise FileNotFoundError(
                f'Step `{self.name}`: input `{role}` (path `{self.inputs[role]}`) '
                f'not found: {path}. If the step that creates it is disabled, '
                'it must already exist on disk.'
            )
        return path

    def hemi_inputs(self, role, **fields):
        """
        Input paths of a per-hemisphere role as
        ``{'left': ..., 'right': ...}``.
        """
        return {hemi: self.input(role, hemi=h, **fields) for hemi, h in HEMIS.items()}

    def output(self, role, **fields):
        """Path of an output role. Creates the parent folder."""
        path = self.ctx.path(self.outputs[role], **fields)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def hemi_outputs(self, role, **fields):
        """
        Output paths of a per-hemisphere role as
        ``{'left': ..., 'right': ...}``.
        """
        return {hemi: self.output(role, hemi=h, **fields) for hemi, h in HEMIS.items()}

    def mesh(self, role):
        """
        Load a surface saved by an ``mni_surfaces`` step. The role name
        (``pial`` or ``white``) fills ``{surf}`` in its path.

        Returns
        -------
        mesh : nilearn.surface.PolyMesh
            The mesh.
        meta : dict
            Its sidecar.
        """
        base = self.ctx.path(self.inputs[role], surf=role)
        # PolyMesh.to_filename saves each hemisphere as <name>_hemi-L/R.
        parts = {hemi: base.with_name(f'{base.stem}_hemi-{h}{base.suffix}') for hemi, h in HEMIS.items()}
        for part in parts.values():
            if not part.exists():
                raise FileNotFoundError(
                    f'Step `{self.name}`: input `{role}` (path `{self.inputs[role]}`) '
                    f'not found: {part}. If the step that creates it is disabled, '
                    'it must already exist on disk.'
                )
        return nilearn.surface.PolyMesh(**parts), io_utils.load_sidecar(base)


def run_correction(step, ctx):
    volume.correct_images(
        step.input('p_values'),
        output_path=step.output('corrected'),
        mask_img=step.input('mask'),
        **step.params
    )


def run_thresholding(step, ctx):
    volume.threshold_images(
        step.input('z_score'),
        step.input('p_values'),
        output_path=step.output('thresholded'),
        thresh_val=BELOW_THRESH,
        mask_img=step.input('mask'),
        **step.params
    )


def run_roi(step, ctx):
    img, meta = io_utils.load_image(step.input('stats'))
    roi_imgs, roi_metas = [], []
    for contrast, spec in ctx.config['contrasts'].items():
        roi_img, roi_meta = volume.roi_single_image(
            img,
            meta=meta,
            contrast_idx=meta['volume_labels'].index(contrast),
            regions=ctx.regions(spec['regions']),
            atlas=step.input('atlas'),
            output_path=False,
            outside_val=OUTSIDE_ROI,
            **step.params
        )
        roi_imgs.append(roi_img)
        roi_metas.append(roi_meta)
    volume.concat_images(roi_imgs, metas=roi_metas, labels=ctx.contrasts, output_path=step.output('rois'))


def run_wta(step, ctx):
    volume.apply_across_volumes(
        img=step.input('rois'),
        func=volume.wta,
        mask_img=step.input('mask'),
        output_path=step.output('wta'),
        outside_val=OUTSIDE_ROI,
        below_thresh_val=BELOW_THRESH,
        no_result_idx=ctx.no_result_idx,
        **step.params
    )


def run_segmentation(step, ctx):
    labels = {0: 'Outside ROI', **{idx + 1: contrast for idx, contrast in enumerate(ctx.contrasts)}}
    labels[ctx.no_result_idx] = 'Rest'
    volume.save_as_segmentation(
        img=step.input('wta'),
        labels=labels,
        output_path=step.output('segmentation'),
        template=step.input('template'),
        color_palette={label: ctx.colors[idx] for idx, label in labels.items()},
        **step.params
    )


def run_mni_surfaces(step, ctx):
    params = dict(step.params)
    for surf in params.pop('surfaces'):
        native = step.hemi_inputs('native_surface', surf=surf)
        surface.transform_surface_to_mni(
            left_surf=native['left'],
            right_surf=native['right'],
            xfm_t1w_mni=step.input('xfm'),
            output_path=step.output('mni_surface', surf=surf),
            **params
        )


def run_projection(step, ctx):
    params = dict(step.params)
    hemi_regions = {hemi: ctx.regions(name) for hemi, name in params.pop('hemi_regions').items()}
    pial, pial_meta = step.mesh('pial')
    white, white_meta = step.mesh('white')
    surface.project_image(
        step.input('volume'),
        output_path=step.output('projected'),
        mesh=pial,
        inner_mesh=white,
        mesh_meta=pial_meta,
        inner_mesh_meta=white_meta,
        hemi_regions=hemi_regions,
        atlas=step.input('atlas'),
        **params
    )


def run_fsaverage(step, ctx):
    sphere = step.hemi_inputs('sphere')
    midthickness = step.hemi_inputs('midthickness')
    surface.transform_surface_to_fsaverage(
        step.input('projected'),
        left_sphere=sphere['left'],
        right_sphere=sphere['right'],
        left_midthickness=midthickness['left'],
        right_midthickness=midthickness['right'],
        standard_surface=ctx.fsaverage,
        output_path=step.output('fsaverage_labels'),
        **step.params
    )


def run_plot_mni(step, ctx):
    pial, pial_meta = step.mesh('pial')
    plotting.make_plot(
        step.input('projected'),
        output_path=step.output('plot'),
        mesh=pial,
        mesh_meta=pial_meta,
        engine='matplotlib',
        **ctx.label_plot_kwargs(),
        **step.params
    )


def run_plot_fsaverage(step, ctx):
    plotting.make_plot(
        step.input('labels'),
        output_path=step.output('plot'),
        standard_surface=ctx.fsaverage,
        mesh='pial',
        engine='matplotlib',
        **ctx.label_plot_kwargs(),
        **step.params
    )


def run_views_mni(step, ctx):
    pial, pial_meta = step.mesh('pial')
    plotting.plot_lateral_medial(
        step.input('projected'),
        output_path=step.output('plot'),
        labels=ctx.plot_labels,
        colors=ctx.colors,
        mesh=pial,
        mesh_meta=pial_meta,
        **step.params
    )


def run_views_fsaverage(step, ctx):
    plotting.plot_lateral_medial(
        step.input('labels'),
        output_path=step.output('plot'),
        labels=ctx.plot_labels,
        colors=ctx.colors,
        standard_surface=ctx.fsaverage,
        mesh='pial',
        **step.params
    )


def run_html(step, ctx):
    plotting.make_html(
        step.input('fsaverage_labels'),
        output_path=step.output('html'),
        standard_surface=ctx.fsaverage,
        mesh='pial',
        **ctx.label_plot_kwargs(),
        **step.params
    )


def run_resampled_t1(step, ctx):
    t1_file = step.input('t1')
    reference_file = step.input('reference')
    resampled_t1_file = step.output('resampled_t1')
    out_img = nilearn.image.resample_to_img(source_img=t1_file, target_img=reference_file, **step.params)
    meta = provenance.record_step(
        'nilearn.image.resample_to_img',
        inputs={'source_img': provenance.describe(t1_file), 'target_img': provenance.describe(reference_file)},
        parameters=step.params,
        output_path=resampled_t1_file
    )
    io_utils.save_image(out_img, resampled_t1_file, meta=meta)


def run_copy_inputs(step, ctx):
    for role in step.inputs:
        file = step.input(role)
        shutil.copyfile(file, f'./{file.name}')


StepType = namedtuple('StepType', ['run', 'inputs', 'outputs', 'func', 'set_by_script', 'extra_params'])
"""
Definition of a step type.

run : callable
    ``run(step, ctx)``.
inputs, outputs : tuple of str or None
    Required roles; ``None`` allows any roles.
func : callable or None
    Function whose parameters ``params`` may set.
set_by_script : set of str
    Parameters of ``func`` the script sets itself.
extra_params : set of str
    Further ``params`` keys handled by ``run``.
"""

_PLOT_SET_BY_SCRIPT = {
    'surf', 'meta', 'output_path', 'standard_surface', 'mesh', 'mesh_meta', 'engine', 'cmap',
    'cmap_bg_first', 'colorbar', 'colorbar_labels', 'vmin', 'vmax'
}
# plotting.plot_lateral_medial sets these for each of its panels.
_VIEWS_SET_BY_SCRIPT = {'labels', 'colors', 'hemi', 'view', 'axes'}

STEP_TYPES = {
    'correction': StepType(
        run_correction, ('p_values', 'mask'), ('corrected',), volume.correct_images,
        {'img', 'meta', 'output_path', 'mask_img', 'load_errors'}, set()),
    'thresholding': StepType(
        run_thresholding, ('z_score', 'p_values', 'mask'), ('thresholded',), volume.threshold_images,
        {'img', 'thresh_img', 'meta', 'thresh_img_meta', 'output_path', 'thresh_val', 'mask_img', 'load_errors'}, set()),
    'roi': StepType(
        run_roi, ('stats', 'atlas'), ('rois',), volume.roi_single_image,
        {'img', 'regions', 'meta', 'contrast_idx', 'atlas', 'output_path', 'load_errors', 'outside_val'}, set()),
    'wta': StepType(
        run_wta, ('rois', 'mask'), ('wta',), volume.wta,
        {'data', 'below_thresh_val', 'outside_val', 'no_result_idx'}, set()),
    'segmentation': StepType(
        run_segmentation, ('wta', 'template'), ('segmentation',), volume.save_as_segmentation,
        {'img', 'meta', 'template', 'labels', 'output_path', 'load_errors', 'color_palette'}, set()),
    'mni_surfaces': StepType(
        run_mni_surfaces, ('native_surface', 'xfm'), ('mni_surface',), surface.transform_surface_to_mni,
        {'left_surf', 'right_surf', 'xfm_t1w_mni', 'output_path'}, {'surfaces'}),
    'projection': StepType(
        run_projection, ('volume', 'pial', 'white', 'atlas'), ('projected',), surface.project_image,
        {'img', 'meta', 'output_path', 'mesh', 'inner_mesh', 'mesh_meta', 'inner_mesh_meta', 'atlas'},
        {'hemi_regions'}),
    'fsaverage': StepType(
        run_fsaverage, ('projected', 'sphere', 'midthickness'), ('fsaverage_labels',),
        surface.transform_surface_to_fsaverage,
        {'surf', 'left_sphere', 'right_sphere', 'left_midthickness', 'right_midthickness', 'standard_surface',
         'output_path', 'meta'}, set()),
    'plot_mni': StepType(
        run_plot_mni, ('projected', 'pial'), ('plot',), plotting.make_plot, _PLOT_SET_BY_SCRIPT, set()),
    'plot_fsaverage': StepType(
        run_plot_fsaverage, ('labels',), ('plot',), plotting.make_plot, _PLOT_SET_BY_SCRIPT, set()),
    'views_mni': StepType(
        run_views_mni, ('projected', 'pial'), ('plot',), plotting.make_plot,
        _PLOT_SET_BY_SCRIPT | _VIEWS_SET_BY_SCRIPT, set()),
    'views_fsaverage': StepType(
        run_views_fsaverage, ('labels',), ('plot',), plotting.make_plot,
        _PLOT_SET_BY_SCRIPT | _VIEWS_SET_BY_SCRIPT, set()),
    'html': StepType(
        run_html, ('fsaverage_labels',), ('html',), plotting.make_plot, _PLOT_SET_BY_SCRIPT, set()),
    'resampled_t1': StepType(
        run_resampled_t1, ('t1', 'reference'), ('resampled_t1',), nilearn.image.resample_to_img,
        {'source_img', 'target_img'}, set()),
    # Copies each input to the working directory.
    'copy_inputs': StepType(run_copy_inputs, None, (), None, set(), set()),
}

REQUIRED_KEYS = ('paths', 'regions', 'contrasts', 'rest_color', 'background_color', 'fsaverage', 'steps')
STEP_KEYS = {'type', 'name', 'enabled', 'inputs', 'outputs', 'params'}


def _check_step_params(where, step_type, params):
    """
    Return errors for ``params`` keys that ``step_type`` does not
    accept.
    """
    errors = []
    if step_type.func is None:
        accepted, any_kwargs = set(), False
    else:
        signature = inspect.signature(step_type.func).parameters
        accepted = set(signature) - step_type.set_by_script
        any_kwargs = any(p.kind is inspect.Parameter.VAR_KEYWORD for p in signature.values())
    for key in params:
        if key in step_type.extra_params:
            continue
        if key in step_type.set_by_script:
            errors.append(f'{where}: parameter `{key}` is set by the script and cannot be configured')
        elif key not in accepted and not any_kwargs:
            errors.append(f'{where}: unknown parameter `{key}`')
    return errors


def validate_config(config):
    """
    Check the config before anything runs.

    Raises
    ------
    ValueError
        Listing every problem found: missing or unknown keys, steps with
        missing or unknown roles or parameters, roles pointing at paths
        that are not defined, duplicate step names, outputs written by
        more than one step, inputs only produced by a later step, path
        templates with unknown placeholders, and contrasts or
        projections using unknown region sets.
    """
    errors = [f'missing top-level key `{key}`' for key in REQUIRED_KEYS if key not in config]
    if errors:
        raise ValueError('Invalid config:\n  ' + '\n  '.join(errors))
    paths = config['paths']

    # Every template must only use known placeholders.
    variables = config.get('variables', {})
    fields = {'sub': 'sub', 'ses': 'ses', 'hemi': 'L', 'surf': 'pial'}
    try:
        variable_values = {key: value.format(**fields) for key, value in variables.items()}
    except KeyError as err:
        variable_values = {}
        errors.append(f'variables: unknown placeholder {err}')
    for name, template in paths.items():
        try:
            template.format(**fields, **variable_values)
        except KeyError as err:
            errors.append(f'path `{name}`: unknown placeholder {err}')

    for contrast, spec in config['contrasts'].items():
        if spec.get('regions') not in config['regions']:
            errors.append(f'contrast `{contrast}` uses unknown region set `{spec.get("regions")}`')
        if 'color' not in spec:
            errors.append(f'contrast `{contrast}` has no `color`')

    steps = config['steps']
    if not isinstance(steps, list):
        raise ValueError('Invalid config:\n  `steps` must be a list')

    names, written_by, produced_later = set(), {}, {}
    # Outputs of enabled steps, by position, to find inputs that are only
    # produced later in the list.
    for idx, spec in enumerate(steps):
        if spec.get('enabled', True):
            for path_name in (spec.get('outputs') or {}).values():
                produced_later.setdefault(path_name, idx)

    for idx, spec in enumerate(steps):
        name = spec.get('name', spec.get('type'))
        where = f'step {idx + 1} (`{name}`)'
        errors += [f'{where}: unknown key `{key}`' for key in spec if key not in STEP_KEYS]
        step_type = STEP_TYPES.get(spec.get('type'))
        if step_type is None:
            errors.append(f'{where}: unknown or missing `type` (one of: {", ".join(STEP_TYPES)})')
            continue

        if name in names:
            errors.append(f'{where}: duplicate step name; give repeated steps a unique `name`')
        names.add(name)

        for kind, roles in (('inputs', step_type.inputs), ('outputs', step_type.outputs)):
            if kind not in spec:
                errors.append(f'{where}: missing `{kind}`')
                continue
            given = spec[kind] or {}
            if roles is not None:
                errors += [f'{where}: missing {kind[:-1]} `{role}`' for role in roles if role not in given]
                errors += [f'{where}: unknown {kind[:-1]} `{role}` (expected: {", ".join(roles) or "none"})'
                           for role in given if role not in roles]
            errors += [f'{where}: {kind[:-1]} `{role}` uses undefined path `{path_name}`'
                       for role, path_name in given.items() if path_name not in paths]

        if spec.get('enabled', True):
            for role, path_name in (spec.get('inputs') or {}).items():
                if produced_later.get(path_name, -1) >= idx and path_name not in written_by:
                    errors.append(f'{where}: input `{role}` (path `{path_name}`) is only produced by this or a later step')
            for path_name in (spec.get('outputs') or {}).values():
                if path_name in written_by:
                    errors.append(f'{where}: output path `{path_name}` is also written by `{written_by[path_name]}`')
                written_by.setdefault(path_name, name)

        params = spec.get('params') or {}
        errors += _check_step_params(where, step_type, params)
        if spec.get('type') == 'projection':
            for hemi, region_set in (params.get('hemi_regions') or {}).items():
                if region_set not in config['regions']:
                    errors.append(f'{where}: unknown region set `{region_set}` for {hemi}')

    if errors:
        raise ValueError('Invalid config:\n  ' + '\n  '.join(errors))


def load_config(path):
    """Load and validate a YAML config."""
    with open(path) as f:
        config = yaml.safe_load(f)
    validate_config(config)
    return config


def create_bodymap(sub, ses, config, base_dir, config_path=None):
    """
    Run all enabled steps for one subject and session.

    Parameters
    ----------
    sub, ses : str
        Subject and session IDs, e.g. ``'sub-118'`` and ``'ses-03'``.
    config : dict
        Validated config, see :func:`load_config`.
    base_dir : path-like
        Root of the derivatives folder; config paths are relative to it.
    config_path : path-like, optional
        Path of the config file, recorded in provenance.
    """
    ctx = Context(sub, ses, base_dir, config)
    # Every sidecar written by this run records the config it used.
    provenance.add_run_info(
        config_file=str(Path(config_path).resolve()) if config_path else None,
        config=config,
        sub=sub,
        ses=ses
    )

    for spec in config['steps']:
        step = Step(ctx, spec)
        if not step.enabled:
            logging.info(f'Skipping {step.name} (disabled)')
            continue
        logging.info(f'Running {step.name}')
        # Label everything this step records with its name in the config.
        with provenance.pipeline_step(step.name):
            STEP_TYPES[step.type].run(step, ctx)

    logging.info(f'Done with {sub}/{ses}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Create body maps from fMRI data.")
    parser.add_argument("-s", "--sub", type=str, required=True, help="Subject ID.")
    parser.add_argument("-e", "--ses", type=str, required=True, help="Session ID.")
    parser.add_argument("-d", "--base-dir", type=str, required=True, help="Base directory where the data is stored. This should be the root of the derivatives folder.")
    parser.add_argument("-c", "--config", type=str, default=str(DEFAULT_CONFIG), help=f"YAML config file. Default: {DEFAULT_CONFIG.name} next to this script.")
    args = parser.parse_args()

    config = load_config(args.config)
    create_bodymap(args.sub, args.ses, config=config, base_dir=args.base_dir, config_path=args.config)
