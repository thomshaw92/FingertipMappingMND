"""
Run a pipeline defined in a YAML config with Pydra (1.0).

The config lists steps; each step names a library function, takes its
inputs from the pipeline's starting files or from earlier steps' results
(by name), sets any other argument of the function in ``params``, and
optionally saves its result. Each step becomes one Pydra task wrapping
the function directly, so a new library function can be used in a
config as soon as it exists. See ``config.yaml`` for the body map
pipeline.

The library functions follow a few conventions (see ``_common``) that
make this possible: they accept images in memory, take the sidecar of an
input ``x`` as ``meta`` (main input) or ``x_meta``, only save when given
``output_path``, and return ``(result, meta)``.

Pydra caches every step's result: a rerun skips steps whose settings
and inputs (including the contents of the starting files) are
unchanged, and reruns a step and everything after it otherwise. Use
``--rerun`` to ignore the cache, e.g. after deleting outputs.

Usage:
    python bodymap-runner.py --sub sub-118 --ses ses-03 \
        [--config config.yaml] [--base-dir DIR] [--rerun]
"""
import argparse
import functools
import importlib
import inspect
import sys
import typing as ty
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / 'utils'))

import yaml
from fileformats.generic import File
from pydra.compose import python, workflow
from pydra.engine.hooks import TaskHooks
from pydra.engine.submitter import Submitter

import provenance

STEP_KEYS = {'name', 'function', 'inputs', 'params', 'output', 'save'}
OUTPUTS = {'result': ty.Any, 'meta': ty.Any}


# --- Config ---------------------------------------------------------------

class FunctionRef(str):
    """
    A ``!func module.name`` value in the config: a function passed as an
    argument.
    """


class ConfigLoader(yaml.SafeLoader):
    """YAML loader that understands ``!func``."""


ConfigLoader.add_constructor('!func', lambda loader, node: FunctionRef(loader.construct_scalar(node)))


def load_config(path):
    """Load a YAML config (see the module docstring)."""
    with open(path) as f:
        return yaml.load(f, Loader=ConfigLoader)


def import_function(dotted_name):
    """Import ``module.function``, e.g. ``volume.threshold_images``."""
    module, _, name = dotted_name.rpartition('.')
    return getattr(importlib.import_module(module), name)


def named_parameters(func):
    """
    Parameters of ``func`` other than ``*args``/``**kwargs``, and
    whether it takes ``**kwargs``.
    """
    params = inspect.signature(func).parameters.values()
    named = {p.name: p for p in params if p.kind not in (p.VAR_POSITIONAL, p.VAR_KEYWORD)}
    return named, any(p.kind is p.VAR_KEYWORD for p in params)


def meta_argument(func, arg):
    """
    Argument of ``func`` taking the sidecar of its input ``arg``:
    ``<arg>_meta``, or ``meta`` if ``arg`` is the first argument.
    """
    named, _ = named_parameters(func)
    if f'{arg}_meta' in named:
        return f'{arg}_meta'
    if named and arg == next(iter(named)) and 'meta' in named:
        return 'meta'
    return None


def validate_config(config):
    """
    Check the config against the functions' signatures before anything
    runs, and raise ``ValueError`` listing every problem found.
    """
    errors = []
    available = set(config['inputs'])
    names = set()

    for idx, step in enumerate(config['steps']):
        where = f'step {idx + 1} (`{step.get("name", "?")}`)'
        errors += [f'{where}: unknown key `{key}`' for key in step if key not in STEP_KEYS]
        if step.get('name') in names:
            errors.append(f'{where}: duplicate name')
        names.add(step.get('name'))

        try:
            func = import_function(step['function'])
        except (KeyError, ImportError, AttributeError, ValueError):
            errors.append(f'{where}: cannot import function `{step.get("function")}`')
            # Still register the output so later steps are not reported too.
            available.add(step.get('output'))
            continue
        named, any_kwargs = named_parameters(func)
        given = {**step.get('params', {}), **step.get('inputs', {})}

        for arg in given:
            if arg not in named and not any_kwargs:
                errors.append(f'{where}: `{step["function"]}` has no argument `{arg}`')
        for arg, ref in step.get('inputs', {}).items():
            if ref not in available:
                errors.append(f'{where}: input `{arg}` refers to `{ref}`, which is not a starting '
                              'file or an earlier step\'s output')
        if 'save' in step and 'output_path' not in named:
            errors.append(f'{where}: `{step["function"]}` cannot save (no `output_path` argument)')
        for arg, p in named.items():
            if p.default is p.empty and arg not in given and arg != 'output_path':
                errors.append(f'{where}: required argument `{arg}` of `{step["function"]}` is not set')

        if 'output' in step:
            if step['output'] in available:
                errors.append(f'{where}: output name `{step["output"]}` is already used')
            available.add(step['output'])

    if errors:
        raise ValueError('Invalid config:\n  ' + '\n  '.join(errors))


# --- Workflow -------------------------------------------------------------

def step_task(step):
    """
    A Pydra task class wrapping the step's function. Its fields are the
    function's arguments, plus any extra arguments the step passes on
    through ``**kwargs`` (e.g. nilearn options).
    """
    func = import_function(step['function'])
    named, _ = named_parameters(func)
    fields = {name: ty.Any for name in named}
    fields.update({name: ty.Any for name in {**step.get('params', {}), **step.get('inputs', {})} if name not in fields})
    return python.define(func, inputs=fields, outputs=OUTPUTS, name=step['name'])


def step_hooks(name):
    """
    Hooks labelling the provenance recorded by a step with its name, so
    that repeated uses of a function can be told apart.
    """
    return TaskHooks(
        pre_run_task=functools.partial(_label_provenance, name),
        post_run_task=functools.partial(_label_provenance, None),
    )


def _label_provenance(name, *job_and_result):
    provenance.set_pipeline_step(name)


def build_workflow(config, sub, ses, base_dir):
    """
    Turn the config into a Pydra workflow for one subject and session.

    The steps and the starting files are inputs of the workflow, so that
    Pydra notices when a step's settings or a starting file's contents
    change. Starting files are passed as File (compared by contents);
    base paths of multi-file data (e.g. meshes saved as
    ``<name>_hemi-L/R.gii``) are passed as plain paths.
    """
    def path(template):
        return Path(base_dir) / template.format(sub=sub, ses=ses)

    # Fill in save paths and turn `!func` names into functions.
    steps = []
    for step in config['steps']:
        params = {key: import_function(value) if isinstance(value, FunctionRef) else value
                  for key, value in step.get('params', {}).items()}
        save = {'output_path': str(path(step['save']))} if 'save' in step else {}
        steps.append({**step, 'params': {**params, **save}})
    starting = {}
    for name, template in config['inputs'].items():
        file = path(template)
        starting[name] = File(file) if file.is_file() else file
    saved = [step['name'] for step in steps if 'save' in step]

    def construct(steps, **starting):
        # Name -> value: a starting file, or the result of an earlier step.
        results = dict(starting)
        sidecars = {}
        nodes = {}
        for step in steps:
            func = import_function(step['function'])
            inputs = {}
            for arg, ref in step.get('inputs', {}).items():
                inputs[arg] = results[ref]
                # Pass sidecars along with in-memory results.
                meta_arg = meta_argument(func, arg)
                if ref in sidecars and meta_arg and meta_arg not in step.get('inputs', {}):
                    inputs[meta_arg] = sidecars[ref]
            Task = step_task(step)
            node = workflow.add(Task(**step['params'], **inputs), name=step['name'], hooks=step_hooks(step['name']))
            nodes[step['name']] = node
            if 'output' in step:
                results[step['output']] = node.result
                sidecars[step['output']] = node.meta
        # The sidecars of saved results are the workflow's outputs, so
        # that every saved step runs.
        return tuple(nodes[name].meta for name in saved)

    fields = {'steps': list, **{name: File if isinstance(value, File) else ty.Any for name, value in starting.items()}}
    Workflow = workflow.define(construct, inputs=fields, outputs=saved, name='Pipeline')
    return Workflow(steps=steps, **starting)


def run(config, sub, ses, base_dir=None, rerun=False, cache_root=None, worker='cf'):
    """
    Validate the config and run its steps for one subject and session.

    Parameters
    ----------
    config : dict
        Config, see :func:`load_config`.
    sub, ses : str
        Subject and session, filling ``{sub}``/``{ses}`` in paths.
    base_dir : path-like, optional
        Folder that paths are relative to. Defaults to ``base_dir`` in
        the config.
    rerun : bool, optional
        Rerun every step, ignoring the cache. Default is ``False``.
    cache_root : path-like, optional
        Pydra's cache folder. Defaults to ``<base_dir>/pydra_cache``.
    worker : str, optional
        Pydra worker: ``'cf'`` (parallel processes, the default),
        ``'debug'`` (one at a time, in this process) or e.g.
        ``'slurm'``.

    Returns
    -------
    pydra.engine.result.Result
        Pydra's result of the workflow.
    """
    validate_config(config)
    base_dir = Path(base_dir or config['base_dir'])
    # Workers forked from this process inherit this.
    provenance.add_run_info(config=config, sub=sub, ses=ses)
    cache_root = Path(cache_root or base_dir / 'pydra_cache')
    with Submitter(cache_root=cache_root, worker=worker) as submitter:
        result = submitter(build_workflow(config, sub, ses, base_dir), rerun=rerun)
    if result.errored:
        raise RuntimeError(f'Pipeline failed; see the crash reports under {cache_root}')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run a pipeline defined in a YAML config with Pydra.')
    parser.add_argument('--config', default=str(Path(__file__).with_name('config.yaml')))
    parser.add_argument('--sub', required=True)
    parser.add_argument('--ses', required=True)
    parser.add_argument('--base-dir', help='Overrides `base_dir` in the config.')
    parser.add_argument('--rerun', action='store_true', help='Rerun every step, ignoring the cache.')
    args = parser.parse_args()
    run(load_config(args.config), args.sub, args.ses, args.base_dir, rerun=args.rerun)
