"""
Surface processing: projecting volumes onto surfaces, label dilation
and smoothing, and transforming surfaces and surface data to MNI and
fsaverage.

See ``_common`` for the conventions all public functions follow.
"""
import contextlib
import copy
import os
import shlex
import subprocess
import tempfile
from pathlib import Path

import nibabel as nib
import nilearn.datasets
import nilearn.surface
import numpy as np
import pandas as pd
from nilearn.surface import SurfaceImage
from scipy.sparse import csr_matrix

import io_utils
import provenance
from _common import (
    ANTS_MODULE,
    WB_MODULE,
    _atlas_input,
    _check_input_img,
    _check_input_mesh,
    _check_input_surface,
    _labels,
    _load_polymesh,
)
from volume import get_roi_mask


def _remove_zeros(surf_img):
    """
    Replace zero values with NaN in a surface image.

    Prevents zeros from appearing in surface plots where NaN is treated
    as transparent.

    Parameters
    ----------
    surf_img : SurfaceImage
        Surface image to modify. A deep copy is made; the original is
        not modified.

    Returns
    -------
    SurfaceImage
        Copy of ``surf_img`` with zeros replaced by NaN in both
        hemispheres.
    """
    surf_img = copy.deepcopy(surf_img)
    for hemi in ['left', 'right']:
        idx = surf_img.data.parts[hemi] == 0
        surf_img.data.parts[hemi][idx] = np.nan

    return surf_img


def _label_keys(data):
    """
    Convert per-vertex labels to integer keys, with ``0`` for
    unlabelled vertices.

    Parameters
    ----------
    data : np.ndarray
        Per-vertex labels. NaN and ``0`` mean unlabelled; all other
        values must be integers.

    Returns
    -------
    np.ndarray
        int32 keys with the shape of ``data``.

    Raises
    ------
    ValueError
        If ``data`` contains non-integer values (NaNs are allowed).
    """
    data = np.asarray(data)
    labelled = np.isfinite(data)
    if not np.all(data[labelled] == np.round(data[labelled])):
        raise ValueError(
            'Label operations require integer labels (e.g. projected with '
            "interpolation='nearest_most_frequent'), but the data contain "
            'non-integer values.'
        )
    return np.where(labelled, data, 0).astype(np.int32)


def _mesh_neighbours(faces, n_vertices, n_ring=1):
    """
    Build a sparse matrix of which vertices are neighbours.

    Parameters
    ----------
    faces : np.ndarray
        (n_faces, 3) vertex indices of the mesh triangles.
    n_vertices : int
        Number of vertices of the mesh.
    n_ring : int, optional
        Neighbourhood size: ``1`` for the vertices sharing an edge,
        ``2`` to also include their neighbours, and so on. Default is
        ``1``.

    Returns
    -------
    scipy.sparse.csr_matrix
        (n_vertices, n_vertices) matrix with ``1`` where the column
        vertex is a neighbour of the row vertex. A vertex is not its own
        neighbour.
    """
    faces = np.asarray(faces)
    # Each triangle has three edges; store both directions of each.
    edges = np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]])
    rows = np.concatenate([edges[:, 0], edges[:, 1]])
    cols = np.concatenate([edges[:, 1], edges[:, 0]])
    adjacency = csr_matrix((np.ones(len(rows)), (rows, cols)), shape=(n_vertices, n_vertices))

    # Grow the neighbourhood one ring at a time.
    neighbours = adjacency
    for _ in range(n_ring - 1):
        neighbours = neighbours + neighbours @ adjacency

    # Edges shared by two triangles were counted twice; keep 0/1 only.
    neighbours = (neighbours > 0).astype(np.float32)
    neighbours.setdiag(0)
    neighbours.eliminate_zeros()
    return neighbours


def _smooth_labels(data, faces, n_iter=3, fill_threshold=0.5, n_ring=1):
    """
    Fill small holes in a label map and smooth it by majority vote.

    1. Fill holes: an unlabelled vertex gets the most common label of
       its neighbours if more than ``fill_threshold`` of its neighbours
       are labelled. Unlabelled areas outside the ROI have mostly
       unlabelled neighbours and stay empty.
    2. Smooth: ``n_iter`` times, every labelled vertex takes the most
       common label among itself and its labelled neighbours, keeping
       its own label on a tie. Unlabelled vertices are not changed, so
       the outline of the labelled area stays the same.

    Parameters
    ----------
    data : np.ndarray
        Per-vertex labels of one hemisphere. NaN and ``0`` mean
        unlabelled; all other values must be integers.
    faces : np.ndarray
        (n_faces, 3) vertex indices of the mesh triangles.
    n_iter : int, optional
        Number of smoothing iterations. Default is ``3``.
    fill_threshold : float, optional
        Fraction of labelled neighbours above which a hole is filled.
        Default is ``0.5``.
    n_ring : int, optional
        Neighbourhood size, see :func:`_mesh_neighbours`. Default is
        ``1``.

    Returns
    -------
    np.ndarray
        Labels (float) with the shape of ``data``, ``0`` where
        unlabelled.

    Raises
    ------
    ValueError
        If ``data`` contains non-integer values (NaNs are allowed).
    """
    keys = _label_keys(data).ravel()
    n_vertices = len(keys)
    n_labels = keys.max() + 1
    neighbours = _mesh_neighbours(faces, n_vertices, n_ring=n_ring)

    def neighbour_label_counts(keys):
        # (n_vertices, n_labels): number of neighbours with each label;
        # column 0 counts unlabelled neighbours.
        onehot = csr_matrix((np.ones(n_vertices), (np.arange(n_vertices), keys)), shape=(n_vertices, n_labels))
        return (neighbours @ onehot).toarray()

    # 1. Fill holes.
    counts = neighbour_label_counts(keys)
    n_neighbours = counts.sum(axis=1)
    n_labelled = n_neighbours - counts[:, 0]
    holes = (keys == 0) & (n_labelled > fill_threshold * n_neighbours)
    keys[holes] = counts[holes, 1:].argmax(axis=1) + 1

    # 2. Majority vote among labelled vertices.
    labelled = keys > 0
    for _ in range(n_iter):
        counts = neighbour_label_counts(keys)[:, 1:]
        # The vertex itself counts as one vote; the extra 0.5 makes it
        # keep its own label on a tie.
        counts[labelled, keys[labelled] - 1] += 1.5
        keys[labelled] = counts[labelled].argmax(axis=1) + 1

    return keys.astype(np.float64).reshape(np.shape(data))


def _write_label_gifti(data, path):
    """
    Save per-vertex integer labels as a GIFTI label file for Workbench.

    NaNs are saved as key ``0``, Workbench's unlabelled key (``???``),
    which is always included in the label table. Other keys are named
    after their value.

    Parameters
    ----------
    data : np.ndarray
        Per-vertex labels of one hemisphere. NaN and ``0`` mean
        unlabelled; all other values must be integers.
    path : path-like
        Output path, conventionally ending in ``.label.gii``.

    Raises
    ------
    ValueError
        If ``data`` contains non-integer values (NaNs are allowed).
    """
    # NaNs become 0, which Workbench treats as unlabelled.
    keys = _label_keys(data)

    label_table = nib.gifti.GiftiLabelTable()
    # Make sure that 0 is always present in the keys.
    for key in [0] + sorted(set(np.unique(keys)) - {0}):
        label = nib.gifti.GiftiLabel(key=int(key), red=0., green=0., blue=0., alpha=0. if key == 0 else 1.)
        label.label = '???' if key == 0 else str(key)
        label_table.labels.append(label)

    darray = nib.gifti.GiftiDataArray(
        keys.ravel(),
        intent=nib.nifti1.intent_codes['NIFTI_INTENT_LABEL'],
        datatype='NIFTI_TYPE_INT32',
    )
    nib.gifti.GiftiImage(darrays=[darray], labeltable=label_table).to_filename(path)


def _dilate_labels(data, mesh, dilate_dist, erode=True, use_temp=True):
    """
    Dilate (and optionally erode) integer labels on one hemisphere with
    ``wb_command -label-dilate`` and ``-label-erode``.

    Dilation gives unlabelled vertices (NaN or ``0``) within
    ``dilate_dist`` of a labelled vertex the nearest label; labelled
    vertices are left unchanged. Eroding by the same distance afterwards
    (a morphological closing) removes labels from vertices within
    ``dilate_dist`` of a still unlabelled vertex. This fills gaps up to
    about twice ``dilate_dist`` wide while pulling the outer edge of the
    labelled area back to roughly where it was. Borders between two
    labels are not eroded. Connectome Workbench is loaded with
    ``ml load WB_MODULE`` in a login shell.

    Parameters
    ----------
    data : np.ndarray
        Per-vertex labels of one hemisphere. NaN and ``0`` mean
        unlabelled; all other values must be integers.
    mesh : nilearn.surface.surface.SurfaceMesh
        Mesh of the same hemisphere, used for the geodesic distances.
    dilate_dist : float
        Dilation (and erosion) distance in mm.
    erode : bool, optional
        Erode by ``dilate_dist`` after dilating. Default is ``True``.
    use_temp : bool, optional
        Write intermediate files to a temporary directory under
        ``$TMPDIR``. Default is ``True``.

    Returns
    -------
    np.ndarray
        Processed labels (float) with the shape of ``data``, ``0`` where
        unlabelled, including vertices that were NaN in ``data``. In
        :func:`project_image` these zeros are turned into NaN by
        :func:`_remove_zeros` afterwards.

    Raises
    ------
    ValueError
        If ``data`` contains non-integer values (NaNs are allowed).
    """
    data = np.asarray(data)

    tmpdir = os.getenv('TMPDIR', '/tmp')
    ctx = tempfile.TemporaryDirectory(dir=tmpdir) if use_temp else contextlib.nullcontext()
    with ctx as tmpdir:
        label_path = Path(tmpdir) / 'labels.label.gii'
        surf_path = Path(tmpdir) / 'mesh.surf.gii'
        dilated_path = Path(tmpdir) / 'dilated.label.gii'
        eroded_path = Path(tmpdir) / 'eroded.label.gii'
        _write_label_gifti(data, label_path)
        mesh.to_gifti(surf_path)

        wb_cmds = [[
            'wb_command', '-label-dilate',
            str(label_path),
            str(surf_path),
            str(dilate_dist),
            str(dilated_path),
        ]]
        out_path = dilated_path
        if erode:
            wb_cmds.append([
                'wb_command', '-label-erode',
                str(dilated_path),
                str(surf_path),
                str(dilate_dist),
                str(eroded_path),
            ])
            out_path = eroded_path
        cmd = f'ml load {WB_MODULE} && ' + ' && '.join(shlex.join(c) for c in wb_cmds)
        subprocess.run(['/bin/bash', '-lc', cmd], check=True)

        dilated = nib.load(str(out_path)).darrays[0].data.astype(np.float64)

    return dilated.reshape(data.shape)


def project_image(img, contrast=None, meta=None, output_path=None, mesh='pial', standard_surface='fsaverage6', verbose=True, load_errors='raise', inner_mesh='white_matter', radius=4, n_samples=20, mesh_meta=None, inner_mesh_meta=None, hemi_regions=None, atlas=None, dilate_dist=None, erode=True, smooth_iter=None, smooth_fill_threshold=0.5, smooth_n_ring=1, **kwargs):
    """
    Project a volumetric image onto a surface.

    Zeros in the projected data are replaced with NaN so they are
    transparent in plots. Projected label images (e.g. WTA maps) can
    optionally be dilated to fill small gaps left by the projection.

    Parameters
    ----------
    img : path-like or nib.Nifti1Image
        Volumetric image to project, 3D or 4D (see ``contrast``).
    contrast : str, optional
        Label (from ``volume_labels`` in the sidecar) of the volume to
        project. Required when ``img`` is 4D.
    meta : dict, optional
        Sidecar of ``img``. Required to keep the provenance of in-memory
        images; loaded from disk for paths if not given. Its ``labels``
        (e.g. from ``volume.winner_take_all``) are carried over to the
        surface image's sidecar.
    output_path : path-like, optional
        Path at which to save the surface image (see
        ``io_utils.save_surface``). Not saved if not given.
    mesh : str, path-like or nilearn.surface.PolyMesh, optional
        Outer mesh: a mesh name of the ``standard_surface`` fsaverage
        (e.g. ``'pial'``), the base path of a saved mesh, or a mesh in
        memory (e.g. from :func:`transform_surface_to_mni`). Default is
        ``'pial'``.
    standard_surface : str, optional
        fsaverage resolution used when ``mesh`` or ``inner_mesh`` is a
        string. Default is ``'fsaverage6'``.
    verbose : bool, optional
        If ``False``, suppress nilearn's printed output. Default is
        ``True``.
    load_errors : {'raise', 'warn'}, optional
        How to handle loading errors. Default is ``'raise'``.
    inner_mesh : str, path-like or nilearn.surface.PolyMesh, optional
        Inner mesh used for depth sampling, as for ``mesh``. Default is
        ``'white_matter'``.
    radius : float, optional
        Radius (mm) for sampling around each surface vertex. Default is
        ``4``.
    n_samples : int, optional
        Number of samples per vertex. Default is ``20``.
    mesh_meta, inner_mesh_meta : dict, optional
        Sidecars of ``mesh`` and ``inner_mesh`` when they are in-memory
        meshes; loaded from disk for paths if not given.
    hemi_regions : dict, optional
        Atlas regions of each hemisphere, as
        ``{'left': [...], 'right': [...]}``. If given, each hemisphere
        is projected separately from a copy of the volume in which
        voxels outside that hemisphere's regions are set to ``0``, so
        that no values bleed from one hemisphere into the other. Default
        is to project both hemispheres from the whole volume.
    atlas : str or path-like, optional
        nilearn atlas name or path to a NIfTI atlas, see
        :func:`volume.get_roi_mask`. Required with ``hemi_regions``.
    dilate_dist : float, optional
        If given, dilate the projected labels by this distance (mm) on
        ``mesh`` with ``wb_command -label-dilate``: unlabelled vertices
        (``0``) within this distance of a label get the nearest label.
        This runs before zeros are replaced with NaN. Requires integer
        data, e.g. from ``interpolation='nearest_most_frequent'``.
        Default is no dilation.
    erode : bool, optional
        Only used with ``dilate_dist``. Erode by the same distance after
        dilating (``wb_command -label-erode``), so that gaps are filled
        but the labels do not grow past the edge of the labelled area.
        Default is ``True``.
    smooth_iter : int, optional
        If given, fill small holes in the projected labels and smooth
        them by majority vote over neighbouring vertices, with this many
        iterations (see :func:`_smooth_labels`). An alternative to
        ``dilate_dist`` that does not need Workbench; only one of the
        two can be used. Requires integer data. Default is no smoothing.
    smooth_fill_threshold : float, optional
        Only used with ``smooth_iter``. An unlabelled vertex is filled
        if more than this fraction of its neighbours are labelled.
        Default is ``0.5``.
    smooth_n_ring : int, optional
        Only used with ``smooth_iter``. Neighbourhood size: ``1`` for
        vertices sharing an edge, ``2`` to also include their
        neighbours, and so on. Default is ``1``.
    **kwargs
        Additional keyword arguments passed to
        ``SurfaceImage.from_volume`` (e.g. ``interpolation``, ``kind``).

    Returns
    -------
    surface_image : SurfaceImage
        Projected surface image.
    meta : dict
        Sidecar of the surface image.

    Raises
    ------
    ValueError
        If ``hemi_regions`` is given without ``atlas``, both
        ``dilate_dist`` and ``smooth_iter`` are given, or the data are
        not integer labels when either of them is given.
    """
    if dilate_dist and smooth_iter:
        raise ValueError('Use either `dilate_dist` or `smooth_iter`, not both.')

    mesh, mesh_param, mesh_input = _check_input_mesh(mesh, mesh_meta, standard_surface, verbose)
    if inner_mesh is not None:
        inner_mesh, inner_mesh_param, inner_mesh_input = _check_input_mesh(
            inner_mesh, inner_mesh_meta, standard_surface, verbose)
    else:
        inner_mesh_param, inner_mesh_input = None, None

    vol_img, vol_input = _check_input_img(img, meta=meta, load_errors=load_errors)
    if vol_img.ndim == 4:
        vol_img = vol_img.slicer[..., vol_input[1]['volume_labels'].index(contrast)]

    if hemi_regions is None:
        surface_image = SurfaceImage.from_volume(
            mesh=mesh,
            volume_img=vol_img,
            inner_mesh=inner_mesh,
            radius=radius,
            n_samples=n_samples,
            **kwargs
        )
    else:
        # Project each hemisphere from its own copy of the volume so
        # that vertices cannot pick up values from the other hemisphere
        # (e.g. across the midline between the paracentral lobules).
        if atlas is None:
            raise ValueError('`atlas` is required with `hemi_regions`.')
        vol_data = vol_img.get_fdata(caching='unchanged')
        textures = {}
        for hemi in ('left', 'right'):
            hemi_mask = get_roi_mask(img=vol_img, regions=hemi_regions[hemi], atlas=atlas, use_temp=False, verbose=0)
            hemi_img = nib.Nifti1Image(np.where(hemi_mask.get_fdata(caching='unchanged') > 0, vol_data, 0), vol_img.affine, vol_img.header)
            textures[hemi] = nilearn.surface.vol_to_surf(
                hemi_img,
                mesh.parts[hemi],
                inner_mesh=inner_mesh.parts[hemi] if inner_mesh is not None else None,
                radius=radius,
                n_samples=n_samples,
                **kwargs
            )
        surface_image = SurfaceImage(mesh=mesh, data=textures)

    if dilate_dist:
        for hemi in ('left', 'right'):
            surface_image.data.parts[hemi] = _dilate_labels(
                surface_image.data.parts[hemi],
                surface_image.mesh.parts[hemi],
                dilate_dist,
                erode=erode
            )

    if smooth_iter:
        for hemi in ('left', 'right'):
            surface_image.data.parts[hemi] = _smooth_labels(
                surface_image.data.parts[hemi],
                surface_image.mesh.parts[hemi].faces,
                n_iter=smooth_iter,
                fill_threshold=smooth_fill_threshold,
                n_ring=smooth_n_ring
            )

    surface_image = _remove_zeros(surface_image)

    meta = provenance.record_step(
        'surface.project_image',
        inputs={
            'img': vol_input,
            'mesh': mesh_input,
            'inner_mesh': inner_mesh_input,
            'atlas': _atlas_input(atlas) if hemi_regions is not None else None,
        },
        parameters={
            'standard_surface': standard_surface if (mesh_param or inner_mesh_param) else None,
            'mesh': mesh_param,
            'inner_mesh': inner_mesh_param,
            'contrast': contrast,
            'radius': radius,
            'n_samples': n_samples,
            'hemi_regions': hemi_regions,
            'atlas': atlas if hemi_regions is not None and _atlas_input(atlas) is None else None,
            'zeros_to_nan': True,
            'dilation': {
                'dilate_dist': dilate_dist,
                'erode': erode,
                'tool': f'wb_command -label-dilate{" -label-erode" if erode else ""} ({WB_MODULE})'
            } if dilate_dist else None,
            'smoothing': {
                'n_iter': smooth_iter,
                'fill_threshold': smooth_fill_threshold,
                'n_ring': smooth_n_ring
            } if smooth_iter else None,
            **kwargs
        },
        output_path=output_path,
        fields={'labels': _labels(vol_input[1])}
    )

    if output_path:
        os.makedirs(Path(output_path).parent, exist_ok=True)
        io_utils.save_surface(surface_image, output_path, meta=meta)

    return surface_image, meta


def _transform_surface(coords, xfm_t1w_mni, xfm_fsnative_t1w=None, use_temp=True):
    """
    Warp surface vertex coordinates with
    ``antsApplyTransformsToPoints``.

    Coordinates are converted from RAS to the LPS convention used by
    ANTs and back. ANTs maps points with the inverse of the image
    transform, so pass the transform that goes *from* the target space
    (e.g. ``from-MNI..._to-T1w``) to move points into the target space.
    ANTs is loaded with ``ml load ANTS_MODULE`` in a login shell.

    Parameters
    ----------
    coords : np.ndarray
        (n_vertices, 3) RAS coordinates.
    xfm_t1w_mni : path-like
        ANTs transform applied to the points.
    xfm_fsnative_t1w : path-like, optional
        Additional ANTs transform, applied after ``xfm_t1w_mni`` in the
        ANTs ``-t`` order.
    use_temp : bool, optional
        Write the intermediate CSV files to a temporary directory under
        ``$TMPDIR``. Default is ``True``.

    Returns
    -------
    np.ndarray
        (n_vertices, 3) transformed RAS coordinates.
    """
    tmpdir = os.getenv('TMPDIR', '/tmp')
    ctx = tempfile.TemporaryDirectory(dir=tmpdir) if use_temp else contextlib.nullcontext()
    with ctx as tmpdir:
        df = pd.DataFrame(coords, columns=['x', 'y', 'z'])
        df['t'] = 0
        # RAS → LPS
        df['x'] = -df['x']
        df['y'] = -df['y']
        df.to_csv(f'{tmpdir}/coords_in.csv', index=False)
    
        ants_cmd = [
            "antsApplyTransformsToPoints",
            "-d", "3",
            "-i", f"{tmpdir}/coords_in.csv",
            "-o", f"{tmpdir}/coords_out.csv",
            "-t", str(xfm_t1w_mni),
        ]
        
        if xfm_fsnative_t1w is not None:
            ants_cmd += ["-t", str(xfm_fsnative_t1w)]
        
        cmd = f"ml load {ANTS_MODULE} && " + shlex.join(ants_cmd)
    
        # This should handle setups where a login shell needs to be
        # used for lmod to work (e.g., HPC).
        subprocess.run(
            ["/bin/bash", "-lc", cmd],
            check=True
        )
    
        out = pd.read_csv(f'{tmpdir}/coords_out.csv')
        # LPS → RAS
        out['x'] = -out['x']
        out['y'] = -out['y']
    return out[['x', 'y', 'z']].values


def transform_surface_to_mni(left_surf, right_surf, xfm_t1w_mni, xfm_fsnative_t1w=None, output_path=None):
    """
    Warp left and right subject surfaces into MNI space.

    Parameters
    ----------
    left_surf, right_surf : path-like
        Subject surface GIFTI files (e.g. fMRIPrep
        ``hemi-L_pial.surf.gii``).
    xfm_t1w_mni : path-like
        ANTs transform, see :func:`_transform_surface` for the direction
        (for fMRIPrep, the ``from-MNI..._to-T1w`` transform).
    xfm_fsnative_t1w : path-like, optional
        Additional ANTs transform, e.g. fsnative to T1w.
    output_path : path-like, optional
        Path at which to save the mesh. nilearn writes one file per
        hemisphere (``_hemi-L``/``_hemi-R``); the sidecar is written
        next to ``output_path``. Not saved if not given.

    Returns
    -------
    surf_polymesh : nilearn.surface.PolyMesh
        The surfaces in MNI space.
    meta : dict
        Sidecar of the mesh.
    """
    surf_mesh = {}
    for hemi in ('left', 'right'):
        surf = nib.load(left_surf if hemi == 'left' else right_surf)
        
        coords = surf.darrays[0].data
        faces = surf.darrays[1].data

        # ANTS warps surfaces in reverse therefore, inverse transforms
        # are needed.
        surf_mni = _transform_surface(
            coords,
            xfm_t1w_mni=xfm_t1w_mni,
            xfm_fsnative_t1w=xfm_fsnative_t1w
        )
        
        # Build InMemoryMesh objects
        surf_mesh[hemi] = nilearn.surface.surface.InMemoryMesh(surf_mni, faces)

    surf_polymesh  = nilearn.surface.surface.PolyMesh(**surf_mesh)

    meta = provenance.record_step(
        'surface.transform_surface_to_mni',
        inputs={
            'left_surf': provenance.describe(left_surf),
            'right_surf': provenance.describe(right_surf),
            'xfm_t1w_mni': provenance.describe(xfm_t1w_mni),
            'xfm_fsnative_t1w': provenance.describe(xfm_fsnative_t1w) if xfm_fsnative_t1w is not None else None,
        },
        parameters={'tool': f'antsApplyTransformsToPoints ({ANTS_MODULE})'},
        output_path=output_path
    )

    if output_path:
        os.makedirs(Path(output_path).parent, exist_ok=True)
        surf_polymesh.to_filename(output_path)
        io_utils.save_sidecar(output_path, meta)
    
    return surf_polymesh, meta


def load_polymesh(path):
    """
    Load a mesh saved with ``PolyMesh.to_filename`` (e.g. by
    :func:`transform_surface_to_mni`), as ``<name>_hemi-L.gii`` and
    ``<name>_hemi-R.gii``, together with its sidecar.

    Parameters
    ----------
    path : path-like
        Base path the mesh was saved with.

    Returns
    -------
    mesh : nilearn.surface.PolyMesh
        The mesh.
    meta : dict or None
        Its sidecar, ``None`` if there is none.
    """
    return _load_polymesh(path)


def _resample_labels_to_fsaverage(data, sphere_path, subject_midthickness, fsavg_sphere, fsavg_pial, fsavg_white, use_temp=True):
    """
    Resample per-vertex integer labels to fsaverage with
    ``wb_command -label-resample``.

    Uses the adaptive barycentric method with vertex-area correction
    (``ADAP_BARY_AREA -area-surfs``), which accounts for the different
    vertex densities of the two meshes; each fsaverage vertex gets the
    label with the largest weight. The fsaverage midthickness needed for
    the area correction is built by averaging the fsaverage pial and
    white surfaces, as nilearn does not provide one. Connectome
    Workbench is loaded with ``ml load WB_MODULE`` in a login shell.

    Parameters
    ----------
    data : np.ndarray
        Per-vertex integer labels (NaN or ``0`` for unlabelled) of one
        hemisphere on the subject's surface.
    sphere_path : path-like
        Subject's sphere registered to fsaverage for the same hemisphere
        (e.g. fMRIPrep ``space-fsaverage_desc-reg_sphere.surf.gii``).
    subject_midthickness : path-like
        Subject's midthickness surface for the same hemisphere, with the
        same vertices as ``sphere_path`` (e.g. fMRIPrep
        ``hemi-L_midthickness.surf.gii``).
    fsavg_sphere : path-like
        Gzipped fsaverage sphere GIFTI for the same hemisphere, as
        returned by ``nilearn.datasets.fetch_surf_fsaverage``.
    fsavg_pial, fsavg_white : path-like
        fsaverage pial and white surfaces for the same hemisphere, as
        returned by ``nilearn.datasets.fetch_surf_fsaverage``.
    use_temp : bool, optional
        Write intermediate files to a temporary directory under
        ``$TMPDIR``. Default is ``True``.

    Returns
    -------
    np.ndarray
        Labels on fsaverage, NaN where unlabelled.

    Raises
    ------
    ValueError
        If the data are not integer labels.
    """
    tmpdir = os.getenv('TMPDIR', '/tmp')
    ctx = tempfile.TemporaryDirectory(dir=tmpdir) if use_temp else contextlib.nullcontext()
    with ctx as tmpdir:
        fsavg_sphere = io_utils.unpack_gifti(fsavg_sphere, output_path=Path(tmpdir) / Path(fsavg_sphere).name.replace('.gz', ''))
        label_path = Path(tmpdir) / 'labels.label.gii'
        out_path = Path(tmpdir) / 'resampled.label.gii'
        _write_label_gifti(data, label_path)

        # nilearn has no fsaverage midthickness; pial and white share
        # their faces, so average their vertices.
        pial = nilearn.surface.load_surf_mesh(fsavg_pial)
        white = nilearn.surface.load_surf_mesh(fsavg_white)
        fsavg_mid_path = Path(tmpdir) / 'fsaverage_midthickness.surf.gii'
        nilearn.surface.surface.InMemoryMesh(
            (pial.coordinates + white.coordinates) / 2,
            pial.faces
        ).to_gifti(fsavg_mid_path)

        wb_cmd = [
            'wb_command', '-label-resample',
            str(label_path),
            str(sphere_path),
            str(fsavg_sphere),
            'ADAP_BARY_AREA',
            str(out_path),
            '-area-surfs',
            str(subject_midthickness),
            str(fsavg_mid_path),
        ]
        cmd = f'ml load {WB_MODULE} && ' + shlex.join(wb_cmd)
        subprocess.run(['/bin/bash', '-lc', cmd], check=True)

        labels = nib.load(str(out_path)).darrays[0].data.astype(np.float64)

    labels[labels == 0] = np.nan
    return labels


def transform_surface_to_fsaverage(surf, left_sphere, right_sphere, left_midthickness, right_midthickness, standard_surface='fsaverage6', output_path=None, meta=None, verbose=True):
    """
    Resample a label surface image (e.g. a projected WTA map) to
    fsaverage.

    Both hemispheres are resampled; see
    :func:`_resample_labels_to_fsaverage` for the method.

    Parameters
    ----------
    surf : SurfaceImage or path-like
        Surface image of integer labels on the subject's surface (e.g.
        from :func:`project_image`), or the base path it was saved with.
    left_sphere, right_sphere : path-like
        Subject's spheres registered to fsaverage (e.g. fMRIPrep
        ``hemi-L_space-fsaverage_desc-reg_sphere.surf.gii``).
    left_midthickness, right_midthickness : path-like
        Subject's midthickness surfaces (e.g. fMRIPrep
        ``hemi-L_midthickness.surf.gii``), used for the vertex-area
        correction.
    standard_surface : str, optional
        fsaverage resolution to resample to. Default is
        ``'fsaverage6'``.
    output_path : path-like, optional
        Path at which to save the resampled surface image (see
        ``io_utils.save_surface``). Not saved if not given.
    meta : dict, optional
        Sidecar of ``surf``. Required to keep the provenance of
        in-memory surface images; loaded from disk for paths if not
        given. Its ``labels`` are carried over.
    verbose : bool, optional
        If ``False``, suppress nilearn's printed output. Default is
        ``True``.

    Returns
    -------
    surf_fsavg : SurfaceImage
        Labels on the fsaverage pial mesh, NaN where unlabelled.
    meta : dict
        Sidecar of the resampled surface image.

    Raises
    ------
    ValueError
        If the data are not integer labels.
    """
    surface_image, surf_input = _check_input_surface(surf, meta=meta)
    with io_utils.optional_silent_print(verbose):
        fsaverage_surf = nilearn.datasets.fetch_surf_fsaverage(mesh=standard_surface)
        fsaverage_mesh = nilearn.datasets.load_fsaverage(mesh=standard_surface)['pial']

    spheres = {'left': left_sphere, 'right': right_sphere}
    midthickness = {'left': left_midthickness, 'right': right_midthickness}
    data = {
        hemi: _resample_labels_to_fsaverage(
            surface_image.data.parts[hemi],
            spheres[hemi],
            midthickness[hemi],
            fsaverage_surf[f'sphere_{hemi}'],
            fsaverage_surf[f'pial_{hemi}'],
            fsaverage_surf[f'white_{hemi}']
        )
        for hemi in ('left', 'right')
    }
    surf_fsavg = SurfaceImage(mesh=fsaverage_mesh, data=data)

    inputs = {'surface': surf_input}
    for hemi in ('left', 'right'):
        inputs[f'{hemi}_sphere'] = provenance.describe(spheres[hemi])
        inputs[f'{hemi}_midthickness'] = provenance.describe(midthickness[hemi])
        for kind in ('sphere', 'pial', 'white'):
            inputs[f'fsaverage_{kind}_{hemi}'] = provenance.describe(fsaverage_surf[f'{kind}_{hemi}'])
    meta = provenance.record_step(
        'surface.transform_surface_to_fsaverage',
        inputs=inputs,
        parameters={
            'standard_surface': standard_surface,
            'tool': f'wb_command -label-resample ADAP_BARY_AREA -area-surfs ({WB_MODULE})'
        },
        output_path=output_path,
        fields={'labels': _labels(surf_input[1])}
    )

    if output_path:
        os.makedirs(Path(output_path).parent, exist_ok=True)
        io_utils.save_surface(surf_fsavg, output_path, meta=meta)

    return surf_fsavg, meta
