"""
Provenance tracking for JSON sidecars.

Every file written by ``analysis`` gets a JSON sidecar of the form::

    {
      "volume_labels": [...],          # fields describing *this* file
      "provenance": {
        "generated_by": "<step id>",   # step that produced this file
        "steps": [                     # all steps leading to this file,
          {                            # in the order they were run
            "id": "<step id>",
            "function": "analysis.correct_images",
            "run": "<run id>",
            "timestamp": "2026-10-19T12:00:00",
            "parameters": {...},
            "inputs": {
              # A source file:
              "p_values": {"file": "/abs/path.nii.gz"},
              # The output of an earlier step:
              "img": {"step": "<step id>", "file": "/abs/out.nii.gz"}
            },
            "output": "/abs/out.nii.gz"  # null if kept in memory
          }
        ],
        "sources": {                   # files that entered the pipeline
          "/abs/path.nii.gz": {...}    # with their original sidecar
        },                             # (e.g. nilearn stats metadata)
        "runs": {                      # process invocations (software
          "<run id>": {...}            # versions, git commit, command)
        }
      }
    }

Each step, source and run appears exactly once, however many times it is
reached through different inputs, so the sidecar of any file is a
complete and self-contained record of how it was made.
"""
import datetime
import importlib.metadata
import os
import platform
import subprocess
import sys
import uuid
from pathlib import Path

import numpy as np

import io_utils

_PACKAGES = ('numpy', 'nibabel', 'nilearn', 'statsmodels', 'pandas', 'matplotlib')
_RUN = None


def _git_info():
    repo = Path(__file__).parent
    try:
        commit = subprocess.run(
            ['git', '-C', str(repo), 'rev-parse', 'HEAD'],
            capture_output=True, text=True, check=True
        ).stdout.strip()
        status = subprocess.run(
            ['git', '-C', str(repo), 'status', '--porcelain', '--untracked-files=no'],
            capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    return {'commit': commit, 'dirty': bool(status)}


def _current_run():
    """Return ``(run_id, run_info)`` for this process, created once."""
    global _RUN
    if _RUN is None:
        packages = {}
        for pkg in _PACKAGES:
            try:
                packages[pkg] = importlib.metadata.version(pkg)
            except importlib.metadata.PackageNotFoundError:
                packages[pkg] = None
        _RUN = (uuid.uuid4().hex[:12], {
            'started': datetime.datetime.now().isoformat(timespec='seconds'),
            'command': sys.argv,
            'host': platform.node(),
            'python': platform.python_version(),
            'packages': packages,
            'git': _git_info(),
        })
    return _RUN


def _jsonable(obj):
    """
    Convert ``obj`` into something ``json.dump`` can write as strict
    JSON.
    """
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return _jsonable(obj.tolist())
    if isinstance(obj, np.generic):
        obj = obj.item()
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, float) and not np.isfinite(obj):
        # NaN/inf are not valid JSON but are used as sentinel values.
        return str(obj)
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if callable(obj) and hasattr(obj, '__qualname__'):
        return f'{obj.__module__}.{obj.__qualname__}'
    return repr(obj)


def describe(obj, meta=None):
    """
    Describe an input for :func:`record_step`.

    Parameters
    ----------
    obj : path-like or image-like
        The input. For paths (or images loaded from disk) the sidecar is
        read from disk if ``meta`` is not given.
    meta : dict, optional
        Sidecar of the input. Needed for in-memory inputs, otherwise
        their history is lost.

    Returns
    -------
    tuple
        ``(path, meta)`` where ``path`` is an absolute path or ``None``.
    """
    if isinstance(obj, (str, Path)):
        path = obj
    else:
        get_filename = getattr(obj, 'get_filename', None)
        path = get_filename() if get_filename is not None else None

    if path is not None:
        path = os.path.abspath(path)
        if meta is None:
            meta = io_utils.load_sidecar(path, errors='ignore')

    return path, meta


def record_step(function, inputs, parameters=None, output_path=None, fields=None):
    """
    Create the sidecar for the output of a processing step.

    Parameters
    ----------
    function : str
        Name of the function that performed the step.
    inputs : dict
        Mapping of input name to ``(path, meta)`` tuples as returned by
        :func:`describe`. ``None`` values are skipped.
    parameters : dict, optional
        Parameters of the step.
    output_path : path-like or None, optional
        Where the output is saved, ``None``/``False`` if not saved.
    fields : dict, optional
        Top-level fields describing the output file itself (e.g.
        ``volume_labels``). These are not inherited by later steps.

    Returns
    -------
    dict
        Sidecar for the output.
    """
    steps, step_ids, sources, runs = [], set(), {}, {}
    refs = {}

    for name, inp in inputs.items():
        if inp is None:
            continue
        path, meta = inp
        prov = (meta or {}).get('provenance')
        if prov:
            for step in prov['steps']:
                if step['id'] not in step_ids:
                    step_ids.add(step['id'])
                    steps.append(step)
            sources.update(prov.get('sources', {}))
            runs.update(prov.get('runs', {}))
            refs[name] = {'step': prov['generated_by'], 'file': path}
        else:
            # A file entering the pipeline (or an in-memory image
            # without any metadata, whose history cannot be recovered).
            refs[name] = {'file': path}
            if path is not None:
                sources[path] = meta or {}

    run_id, run_info = _current_run()
    runs[run_id] = run_info

    step = {
        'id': uuid.uuid4().hex[:12],
        'function': function,
        'run': run_id,
        'timestamp': datetime.datetime.now().isoformat(timespec='seconds'),
        'parameters': _jsonable(parameters or {}),
        'inputs': refs,
        'output': os.path.abspath(output_path) if output_path else None,
    }
    steps.append(step)

    sidecar = _jsonable(fields or {})
    sidecar['provenance'] = {
        'generated_by': step['id'],
        'steps': steps,
        'sources': sources,
        'runs': runs,
    }
    return sidecar


def last_step(meta):
    """Return the step that generated the file described by ``meta``."""
    prov = (meta or {}).get('provenance')
    if not prov:
        return {}
    return next((s for s in prov['steps'] if s['id'] == prov['generated_by']), {})
