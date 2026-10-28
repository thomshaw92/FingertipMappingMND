"""
Static and interactive plots of surface data.

See ``_common`` for the conventions all public functions follow. For
label images whose sidecar records label names (e.g. from
``volume.winner_take_all``), plots use those names for the colorbar
unless told otherwise.
"""
import os
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import nilearn.datasets
import nilearn.plotting
import nilearn.surface
import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.cm import ScalarMappable
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.figure import Figure
from nilearn.surface import SurfaceImage

import io_utils
import provenance
from _common import _check_input_mesh, _check_input_surface, _labels


def _surface_inputs(surf, meta=None):
    """
    Load surface data for plotting and describe it for provenance.

    Parameters
    ----------
    surf : SurfaceImage, path-like or dict
        Surface image, the base path of one saved with
        ``io_utils.save_surface``, or a dict with ``'left'``/``'right'``
        keys holding paths to per-hemi GIFTI files or arrays.
    meta : dict, optional
        Sidecar of ``surf``, or for a dict input either one sidecar for
        both hemispheres or a dict of per-hemi sidecars. Loaded from
        disk for paths if not given.

    Returns
    -------
    surface : SurfaceImage or dict
        The surface image, or a dict of per-hemi arrays for a dict
        input.
    inputs : dict
        Inputs for ``provenance.record_step``.
    """
    if not isinstance(surf, dict):
        surface_image, surf_input = _check_input_surface(surf, meta=meta)
        return surface_image, {'surface': surf_input}

    data, inputs = {}, {}
    for hemi, hemi_data in surf.items():
        hemi_meta = meta.get(hemi) if isinstance(meta, dict) and hemi in meta else meta
        if isinstance(hemi_data, (str, os.PathLike)):
            inputs[hemi] = provenance.describe(hemi_data, hemi_meta)
            hemi_data = nilearn.surface.load_surf_data(str(hemi_data))
        else:
            inputs[hemi] = (None, hemi_meta)
        data[hemi] = hemi_data
    return data, inputs


def _label_names(inputs):
    """
    Names of labels ``1..n`` recorded in the sidecar of the plotted
    surface, ``None`` if there are none.
    """
    surf_input = inputs.get('surface') or inputs.get('left') or (None, None)
    labels = _labels(surf_input[1])
    if not labels:
        return None
    return [labels[key] for key in sorted(labels, key=int) if int(key) > 0]


def _check_bg_map(mesh, left_bg_map=None, right_bg_map=None):
    """
    Load a per-hemi background map (e.g. sulcal depth) for ``mesh``.

    Parameters
    ----------
    mesh : nilearn.surface.PolyMesh
        Mesh the map is shown on.
    left_bg_map, right_bg_map : path-like or np.ndarray, optional
        Per-vertex values of each hemisphere, as GIFTI paths (e.g.
        fMRIPrep's ``*_hemi-L_sulc.shape.gii``) or arrays. Give both or
        neither.

    Returns
    -------
    bg_map : SurfaceImage or None
        The background map, ``None`` if neither is given.
    inputs : dict
        Inputs for ``provenance.record_step``.

    Raises
    ------
    ValueError
        If only one hemisphere is given, or a map does not have one
        value per vertex of its hemisphere of ``mesh``.
    """
    if left_bg_map is None and right_bg_map is None:
        return None, {}
    if left_bg_map is None or right_bg_map is None:
        raise ValueError('Give both `left_bg_map` and `right_bg_map`, or neither.')

    data, inputs = {}, {}
    for hemi, bg_map in (('left', left_bg_map), ('right', right_bg_map)):
        if isinstance(bg_map, (str, os.PathLike)):
            inputs[f'{hemi}_bg_map'] = provenance.describe(bg_map)
            bg_map = nilearn.surface.load_surf_data(os.fspath(bg_map))
        else:
            inputs[f'{hemi}_bg_map'] = (None, None)
        bg_map = np.asarray(bg_map).ravel()
        n_vertices = mesh.parts[hemi].n_vertices
        if bg_map.size != n_vertices:
            raise ValueError(
                f'`{hemi}_bg_map` has {bg_map.size} values but the {hemi} mesh has {n_vertices} vertices; '
                'the map must come from the same mesh (e.g. native sulc with a native/MNI mesh).'
            )
        data[hemi] = bg_map
    return SurfaceImage(mesh=mesh, data=data), inputs


def _plot_surface(surf, meta=None, standard_surface='fsaverage6', mesh='inflated', verbose=False, colorbar_labels=None, cmap=None, cmap_bg_first=False, mesh_meta=None, left_bg_map=None, right_bg_map=None, **kwargs):
    """
    Plot a surface image without saving it.

    Takes the same arguments as :func:`make_plot` except
    ``output_path``.

    Returns
    -------
    display
        The nilearn display object (matplotlib figure or plotly
        display).
    inputs : dict
        Inputs for ``provenance.record_step``.
    parameters : dict
        Plotting parameters for ``provenance.record_step``.
    """
    mesh, mesh_name, mesh_input = _check_input_mesh(mesh, mesh_meta, standard_surface, verbose)
    bg_map, bg_inputs = _check_bg_map(mesh, left_bg_map=left_bg_map, right_bg_map=right_bg_map)
    if bg_map is None and mesh_name is not None:
        # fsaverage meshes come with a sulcal map to show underneath.
        with io_utils.optional_silent_print(verbose):
            bg_map = nilearn.datasets.load_fsaverage_data(mesh=standard_surface, data_type="sulcal", mesh_type=mesh_name)

    surface_image, inputs = _surface_inputs(surf, meta=meta)
    if not isinstance(surface_image, SurfaceImage):
        surface_image = SurfaceImage(mesh=mesh, data=surface_image)
    inputs['mesh'] = mesh_input
    inputs.update(bg_inputs)

    # Label images: use the recorded label names for the colorbar.
    if colorbar_labels is None:
        colorbar_labels = _label_names(inputs)
        if colorbar_labels is not None:
            kwargs.setdefault('vmin', 1)
            kwargs.setdefault('vmax', len(colorbar_labels))

    parameters = {
        'standard_surface': standard_surface if mesh_name else None,
        'mesh': mesh_name,
        'colorbar_labels': colorbar_labels,
        'cmap': cmap,
        'cmap_bg_first': cmap_bg_first,
        **kwargs
    }

    if 'vmin' not in kwargs or 'vmax' not in kwargs:
        # Set vmin/vmax based on the data range across both hemispheres.
        data = np.concatenate([surface_image.data.parts['left'], surface_image.data.parts['right']])
        # Keep existing values in kwargs.
        kwargs['vmin'] = kwargs.get('vmin', np.nanmin(data))
        kwargs['vmax'] = kwargs.get('vmax', np.nanmax(data))

    if isinstance(cmap, list):
        if cmap_bg_first:
            # Remove the first color (background) from the colormap so
            # that it is not used in the plot or the legend.
            cmap = cmap[1:]
        cmap = matplotlib.colors.ListedColormap(cmap)
    if cmap is not None:
        # The default value for `cmap` in `plot_surf_stat_map` is a
        # constant var so cannot pass `cmap=None` directly.
        kwargs['cmap'] = cmap

    display = nilearn.plotting.plot_surf_stat_map(
        surf_mesh=mesh,
        stat_map=surface_image,
        bg_map=bg_map,
        **kwargs
    )

    # A labelled, discrete colorbar only makes sense for label data. For
    # anything else keep nilearn's continuous colorbar.
    if colorbar_labels is None or not kwargs.get('colorbar', True):
        return display, inputs, parameters

    vmin = kwargs['vmin']
    vmax = kwargs['vmax']
    if 'engine' in kwargs and kwargs['engine'] == 'plotly':
        n = len(colorbar_labels)

        display.figure.update_traces(
            cmin=vmin-0.5, cmax=vmax+0.5,  # to make sure that the colors extend past labels
            colorbar=dict(
                tickvals=np.arange(vmin, n + 1),   # [1, 2, 3, ... 8]
                ticktext=colorbar_labels,
                tickfont=dict(size=35),
                tickmode='array',
            )
        )
    else:
        n = len(colorbar_labels)

        cbar_ax = display.axes[-1]
        cbar = cbar_ax._colorbar

        cbar.vmin = vmin - 0.5
        cbar.vmax = vmax + 0.5
        cbar.boundaries = np.arange(vmin - 0.5, vmax + 1.5)
        cbar._draw_all()  # needed to update the colorbar

        cbar_ax.set_ylim(vmin - 0.5, vmax + 0.5)
        cbar_ax.set_yticks(np.arange(vmin, n + 1))
        cbar_ax.set_yticklabels(colorbar_labels)
        cbar_ax.tick_params(labelsize=16)

    return display, inputs, parameters


def make_plot(surf, meta=None, output_path=None, standard_surface='fsaverage6', mesh='inflated', verbose=False, colorbar_labels=None, cmap=None, cmap_bg_first=False, mesh_meta=None, left_bg_map=None, right_bg_map=None, **kwargs):
    """
    Create a static surface stat-map plot.

    Parameters
    ----------
    surf : SurfaceImage, path-like or dict
        Surface image (e.g. from ``surface.project_image``), the base
        path of one saved with ``io_utils.save_surface``, or a dict with
        ``'left'``/``'right'`` keys holding per-hemi GIFTI paths or
        arrays.
    meta : dict, optional
        Sidecar of ``surf`` (or a dict of per-hemi sidecars). Required
        to keep the provenance of in-memory surfaces; loaded from disk
        for paths if not given.
    output_path : path-like, optional
        Path at which to save the plot. Not saved if not given.
    standard_surface : str, optional
        fsaverage resolution used when ``mesh`` is a mesh name. Default
        is ``'fsaverage6'``.
    mesh : str, path-like or nilearn.surface.PolyMesh, optional
        Mesh to plot on: a mesh name of the ``standard_surface``
        fsaverage, which also provides the sulcal background, the base
        path of a saved mesh, or a mesh in memory. Default is
        ``'inflated'``.
    verbose : bool, optional
        If ``False``, suppress nilearn's printed output. Default is
        ``False``.
    colorbar_labels : list of str, optional
        Tick labels for the integer values ``vmin``..``vmax``. If given,
        the colorbar is drawn as discrete colour blocks, one per label
        (for label data such as WTA maps). Defaults to the label names
        recorded in the sidecar of ``surf`` (with ``vmin``/``vmax``
        then defaulting to ``1``/the number of labels); without any,
        nilearn's continuous colorbar is used.
    cmap : str, list or matplotlib colormap, optional
        Colormap. A list of colours is turned into a ``ListedColormap``.
    cmap_bg_first : bool, optional
        If ``True`` and ``cmap`` is a list, its first colour is the
        background and is dropped from the plot and colorbar. Default is
        ``False``.
    mesh_meta : dict, optional
        Sidecar of ``mesh`` when it is a mesh in memory; loaded from
        disk for paths if not given.
    left_bg_map, right_bg_map : path-like or np.ndarray, optional
        Background map (e.g. sulcal depth) of each hemisphere with one
        value per vertex of ``mesh``, as GIFTI paths (e.g. fMRIPrep's
        ``*_hemi-L_sulc.shape.gii``, which also fits the MNI meshes from
        ``surface.transform_surface_to_mni``) or arrays. Give both or
        neither. Defaults to the fsaverage sulcal map for fsaverage
        meshes and no background otherwise.
    **kwargs
        Additional keyword arguments passed to
        ``nilearn.plotting.plot_surf_stat_map``. ``vmin``/``vmax``
        default to the data range across both hemispheres.

    Returns
    -------
    display : matplotlib.figure.Figure or plotly display
        The nilearn display object.
    meta : dict
        Sidecar of the plot.
    """
    display, inputs, parameters = _plot_surface(
        surf, meta=meta, standard_surface=standard_surface, mesh=mesh, verbose=verbose,
        colorbar_labels=colorbar_labels, cmap=cmap, cmap_bg_first=cmap_bg_first, mesh_meta=mesh_meta,
        left_bg_map=left_bg_map, right_bg_map=right_bg_map, **kwargs
    )

    meta = provenance.record_step('plotting.make_plot', inputs=inputs, parameters=parameters, output_path=output_path)

    if output_path:
        os.makedirs(Path(output_path).parent, exist_ok=True)
        io_utils.save_figure(display, output_path, meta=meta)

    if isinstance(display, matplotlib.figure.Figure):
        plt.close(display)

    return display, meta


def make_html(surf, meta=None, output_path=None, legacy=False, **kwargs):
    """
    Create an interactive HTML surface plot.

    Parameters
    ----------
    surf : SurfaceImage, path-like or dict
        Surface image, as accepted by :func:`make_plot`.
    meta : dict, optional
        Sidecar of ``surf``. Required to keep the provenance of
        in-memory surfaces; loaded from disk for paths if not given.
    output_path : path-like, optional
        Path at which to save the HTML file. Not saved if not given.
    legacy : bool, optional
        If ``True``, use the legacy nilearn viewer (``view_surf``)
        instead of the new plotly-based viewer. Default is ``False``.
    **kwargs
        Passed to :func:`_surf_plot_html` or :func:`_view_surf_html`
        depending on ``legacy``.

    Returns
    -------
    display
        The interactive display object.
    meta : dict
        Sidecar of the HTML file.
    """
    plot_html = _view_surf_html if legacy else _surf_plot_html
    return plot_html(surf, meta=meta, output_path=output_path, **kwargs)


def _surf_plot_html(surf, meta=None, output_path=None, standard_surface='fsaverage6', mesh='inflated', verbose=False, **kwargs):
    """
    Create an interactive (plotly) HTML surface plot.

    Parameters
    ----------
    surf, meta, standard_surface, mesh, verbose
        See :func:`make_plot`.
    output_path : path-like, optional
        Path at which to save the HTML file. Not saved if not given.
    **kwargs
        Other arguments of :func:`make_plot` (e.g. ``cmap``,
        ``colorbar_labels``, ``mesh_meta``) and of
        ``nilearn.plotting.plot_surf_stat_map``. ``engine`` is always
        ``'plotly'``.

    Returns
    -------
    display
        The nilearn plotly display object.
    meta : dict
        Sidecar of the HTML file.
    """
    display, inputs, parameters = _plot_surface(
        surf,
        meta=meta,
        standard_surface=standard_surface,
        mesh=mesh,
        verbose=verbose,
        engine='plotly',
        **kwargs
    )

    meta = provenance.record_step('plotting.make_html', inputs=inputs, parameters=parameters, output_path=output_path)

    if output_path:
        os.makedirs(Path(output_path).parent, exist_ok=True)
        io_utils.save_figure(display, output_path, meta=meta, interactive=True)

    return display, meta


def _view_surf_html(surf, meta=None, output_path=None, hemi='left', standard_surface='fsaverage6', surface_type='inflated', verbose=False, **kwargs):
    """
    Create an interactive HTML surface viewer with
    ``nilearn.plotting.view_surf``.

    The colour scale is set symmetrically around zero based on the data
    range across both hemispheres, unless ``vmin``/``vmax`` are supplied
    in ``**kwargs``.

    Parameters
    ----------
    surf : SurfaceImage or path-like
        Surface image on the ``standard_surface`` fsaverage, or the base
        path of one saved with ``io_utils.save_surface``.
    meta : dict, optional
        Sidecar of ``surf``. Loaded from disk for paths if not given.
    output_path : path-like, optional
        Path at which to save the HTML file. Not saved if not given.
    hemi : {'left', 'right'}, optional
        Hemisphere to display. Default is ``'left'``. The viewer does
        not support plotting both hemispheres at once.
    standard_surface : str, optional
        fsaverage resolution. Default is ``'fsaverage6'``.
    surface_type : str, optional
        fsaverage mesh to plot on. Default is ``'inflated'``.
    verbose : bool, optional
        If ``False``, suppress nilearn's printed output. Default is
        ``False``.
    **kwargs
        Additional keyword arguments passed to
        ``nilearn.plotting.view_surf``.

    Returns
    -------
    view : nilearn.plotting.html_surface.SurfaceView
        The nilearn interactive view object.
    meta : dict
        Sidecar of the HTML file.
    """
    with io_utils.optional_silent_print(verbose):
        fsaverage = nilearn.datasets.load_fsaverage(mesh=standard_surface)
        fsaverage_data = nilearn.datasets.load_fsaverage_data(mesh=standard_surface, data_type="sulcal", mesh_type=surface_type)

    surface_image, inputs = _surface_inputs(surf, meta=meta)

    # Automatic vmin/vmax does not work that well in view_surf.
    surface_data = surface_image.data.parts
    data_max = float(np.nanmax([
        np.nanmax(np.abs(surface_data['left'])),
        np.nanmax(np.abs(surface_data['right']))
    ]))
    # Ensure that user-supplied values are not overridden.
    if 'vmin' not in kwargs:
        kwargs['vmin'] = -data_max
    if 'vmax' not in kwargs:
        kwargs['vmax'] = data_max

    view = nilearn.plotting.view_surf(
        surf_mesh=fsaverage[surface_type],
        surf_map=surface_image,
        bg_map=fsaverage_data,
        hemi=hemi,
        **kwargs
    )

    meta = provenance.record_step(
        'plotting.make_html',
        inputs=inputs,
        parameters={
            'standard_surface': standard_surface,
            'surface_type': surface_type,
            'hemi': hemi,
            **kwargs
        },
        output_path=output_path
    )

    if output_path:
        os.makedirs(Path(output_path).parent, exist_ok=True)
        io_utils.save_view(view, output_path, meta=meta)

    return view, meta


def _render_view(surf, hemi, view, colors, n_labels, meta=None, dpi=200, **plot_kwargs):
    """
    Render one view of one hemisphere and crop it to the brain.

    The view is drawn with :func:`make_plot` on its own figure, which is
    created with an Agg canvas directly (not through pyplot) so that it
    can still be rendered after ``make_plot`` closes it.

    Parameters
    ----------
    surf : SurfaceImage, path-like or dict
        Surface image, as accepted by :func:`make_plot`.
    hemi : {'left', 'right'}
        Hemisphere to show.
    view : str
        nilearn view, e.g. ``'lateral'`` or ``'medial'``.
    colors : list
        Colours with the background first.
    n_labels : int
        Number of labels; values ``1..n_labels`` are coloured.
    meta : dict, optional
        Sidecar of ``surf``, passed to :func:`make_plot`.
    dpi : int, optional
        Resolution of the rendering. Default is ``200``.
    **plot_kwargs
        Passed to :func:`make_plot`.

    Returns
    -------
    img : np.ndarray
        RGB image cropped to the non-white pixels.
    meta : dict
        Sidecar of the view from :func:`make_plot`.
    """
    fig = Figure(figsize=(8, 6), dpi=dpi)
    canvas = FigureCanvasAgg(fig)
    ax = fig.add_subplot(projection='3d')
    # No per-view colorbar: the figure gets one shared colorbar.
    _, view_meta = make_plot(
        surf,
        meta=meta,
        hemi=hemi,
        view=view,
        axes=ax,
        colorbar=False,
        cmap=colors,
        cmap_bg_first=True,
        vmin=1,
        vmax=n_labels,
        engine='matplotlib',
        **plot_kwargs
    )
    canvas.draw()
    img = np.asarray(canvas.buffer_rgba())[..., :3].copy()

    # 3D axes leave a wide margin around the brain; crop it away.
    content = (img < 250).any(axis=2)
    rows, cols = np.where(content.any(axis=1))[0], np.where(content.any(axis=0))[0]
    if rows.size and cols.size:
        img = img[rows[0]:rows[-1] + 1, cols[0]:cols[-1] + 1]
    return img, view_meta


def plot_lateral_medial(surf, colors, output_path=None, labels=None, meta=None, mesh_meta=None, **plot_kwargs):
    """
    Plot lateral and medial views of both hemispheres in a 2x2 figure
    with one shared colorbar.

    Each view is rendered separately and cropped to the brain (see
    :func:`_render_view`), so the panels can be placed close together.

    Parameters
    ----------
    surf : SurfaceImage, path-like or dict
        Surface image of integer labels ``1..len(labels)``, as accepted
        by :func:`make_plot`.
    colors : list
        Colours with the background first, i.e. ``len(labels) + 1``
        colours.
    output_path : path-like, optional
        Path at which to save the PNG (with a JSON sidecar). Not saved
        if not given.
    labels : list of str, optional
        Name of each label value, starting at ``1``. Defaults to the
        label names recorded in the sidecar of ``surf``.
    meta : dict, optional
        Sidecar of ``surf``, passed to :func:`make_plot`. Required to
        keep the provenance of in-memory surfaces.
    mesh_meta : dict, optional
        Sidecar of ``mesh`` (in ``plot_kwargs``) when it is a mesh in
        memory.
    **plot_kwargs
        Passed to :func:`make_plot` (e.g. ``mesh``,
        ``standard_surface``, ``avg_method``, ``left_bg_map`` and
        ``right_bg_map``).

    Returns
    -------
    fig : matplotlib.figure.Figure
        The figure.
    meta : dict
        Sidecar of the figure.

    Raises
    ------
    ValueError
        If ``labels`` is not given and the sidecar of ``surf`` records
        none.
    """
    if labels is None:
        _, inputs = _surface_inputs(surf, meta=meta)
        labels = _label_names(inputs)
        if labels is None:
            raise ValueError('Pass `labels`: the sidecar of `surf` does not record label names.')

    panels, panel_metas = {}, {}
    for hemi in ('left', 'right'):
        for view in ('lateral', 'medial'):
            panels[hemi, view], panel_metas[f'{hemi}_{view}'] = _render_view(
                surf, hemi, view, colors, len(labels), meta=meta, mesh_meta=mesh_meta, **plot_kwargs
            )

    # Lay the cropped views out edge to edge, sized so that they keep
    # their aspect ratio, with the colorbar in its own column.
    aspect = np.mean([img.shape[1] / img.shape[0] for img in panels.values()])
    fig_width, cbar_frac, gap = 10, 0.14, 0.02
    panel_width = fig_width * (1 - cbar_frac) / 2
    fig = plt.figure(figsize=(fig_width, 2 * panel_width / aspect))
    for row, hemi in enumerate(('left', 'right')):
        for col, view in enumerate(('lateral', 'medial')):
            ax = fig.add_axes([
                col * (1 - cbar_frac) / 2,
                0.5 - row * 0.5,
                (1 - cbar_frac) / 2 - gap / 2,
                0.5 - gap / 2
            ])
            ax.imshow(panels[hemi, view])
            ax.set_axis_off()

    # Discrete colorbar with one block per label.
    norm = BoundaryNorm(np.arange(0.5, len(labels) + 1.5), len(labels))
    mappable = ScalarMappable(norm=norm, cmap=ListedColormap(colors[1:]))
    cax = fig.add_axes([1 - cbar_frac + 0.03, 0.15, 0.02, 0.7])
    cbar = fig.colorbar(mappable, cax=cax, ticks=range(1, len(labels) + 1))
    cbar.ax.set_yticklabels(labels)

    meta = provenance.record_step(
        'plotting.plot_lateral_medial',
        inputs={panel: (None, panel_meta) for panel, panel_meta in panel_metas.items()},
        parameters={'labels': labels, 'colors': colors},
        output_path=output_path
    )
    if output_path:
        os.makedirs(Path(output_path).parent, exist_ok=True)
        fig.savefig(output_path, dpi=200, bbox_inches='tight')
        io_utils.save_sidecar(output_path, meta)
    plt.close(fig)

    return fig, meta
