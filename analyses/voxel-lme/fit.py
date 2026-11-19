import logging
import pandas as pd
import numpy as np
import polars
from pymer4.models import lmer
import json
import os
import argparse
import nibabel as nib
import re
import dill
from tqdm import tqdm

logging.basicConfig(
    level=logging.DEBUG,  # show INFO and above
    format="%(asctime)s [%(levelname)s] %(message)s"
)


def load_config(json_path):
    def expand(item):
        """
        Expand shell variables (e.g., ${VAR}, $VAR) into their values.
        """
        if isinstance(item, str):
            return os.path.expandvars(item)
        elif isinstance(item, dict):
            return {k: expand(v) for k, v in item.items()}
        elif isinstance(item, list):
            return [expand(elem) for elem in item]
        else:
            return item

    with open(json_path, 'r') as f:
        config = json.load(f)

    return expand(config)


def fit_model(idx, formula, data, voxel_data):
    def convert_to_pandas(df):
        """Convert to pandas.DataFrame and use the first column as
        index"""
        return pd.DataFrame(df, columns=df.columns).set_index(df.columns[0])

    # print_msg('Setting up data')
    # Make sure to select the right indices if a query has been applied
    # to the data.
    # Nibabel does not support list as index thus the for loop.
    for didx in data.index:
        data.loc[didx, 'activation'] = voxel_data[*idx, didx]

    # print_msg('Parsing formula')
    tokens = set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", formula))
    exist_tokens = [t for t in tokens if t in data.columns]

    # print_msg('Setting up the model')
    # Data must be a type that pymer can use, not pandas.DataFrame.
    model_data = polars.DataFrame(data[exist_tokens])
    model = lmer(
        formula,
        data=model_data
    )

    logging.debug('Preparing to run a model with these parameters:')
    logging.debug(f'  - formula: {formula}')
    logging.debug(f'  - index: {idx}')
    logging.debug(f'  - data size: {data.shape}')
    logging.debug(f'  - voxel data size: {voxel_data.shape}')

    logging.debug('Trying fitting')
    try:
        model.fit(verbose=False)

        logging.debug('Success, saving results')
        result = {
            'fixedeffects': convert_to_pandas(model.fixef),
            'randomeffects': convert_to_pandas(model.ranef),
            'result': convert_to_pandas(model.result_fit),
            'logs': model.r_console,
            'error': None,
            'formula': formula,
            'success': True
        }
    except Exception as rerr:
        logging.debug('Failure, saving results')
        result = {
            'fixedeffects': None,
            'randomeffects': None,
            'result': None,
            'logs': model.r_console,
            'error': str(rerr),
            'formula': formula,
            'success': False
        }

    logging.debug('Done fitting')
    return result

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Run second-level regression.")
    parser.add_argument('-i', '--index', help='Voxel indices (x, y, z).', nargs=3, type=int, action="append", required=True)
    parser.add_argument('-c', '--config', help='Path to the JSON config file.', required=True)
    parser.add_argument('-o', '--output', help='Output file name.', default='')
    args = parser.parse_args()

    config = load_config(args.config)

    logging.debug('Setting up variables for modelling.')
    logging.debug(f'Reading config file: {args.config}.')
    logging.debug(f'Reading data file: {config["data_file"]}')
    logging.debug(f'Reading voxel data file: {config["voxel_file"]}')
    logging.debug(f'Using these indices: {args.index}')
    
    data = pd.read_csv(config['data_file'], index_col=None, header=0)
    if config['query']:
        logging.debug(f'Applying this query: {config["query"]}')
        data = data.query(config['query'])
    voxel_img = nib.load(config['voxel_file'])
    voxel_data = voxel_img.dataobj
    # Indices must be tuples so that they can be used as dict keys.
    index = [tuple(ii) for ii in args.index]
    
    results = {}
    n_ind = len(index)
    for n, idx in tqdm(enumerate(index), total=n_ind):
        res = fit_model(idx, formula=config['formula'], data=data, voxel_data=voxel_data)
        results[idx] = res
        logging.debug('\n')

    logging.debug(f'Done with modelling. Saving data to {config["output_prefix"]}{args.output}.dill')
    with open(f'{config["output_prefix"]}{args.output}.dill', 'wb') as f:
        dill.dump(results, f)
    logging.debug('Done with the script.')

    
