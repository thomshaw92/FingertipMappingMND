from collections import defaultdict
import datetime
from dataclasses import dataclass
import logging
import pandas as pd
import numpy as np
from pathlib import Path
import dill
from functools import wraps, partial
from scipy import stats
from statsmodels.stats.multitest import multipletests

import pdb

TESTS = {
    'parametric': {
        'independent': {'func': partial(stats.ttest_ind, equal_var=False), 'name': 'Independent t-test', 'stat': 't'},
        'paired': {'func': stats.ttest_rel, 'name': 'Paired t-test', 'stat': 't'}
    },
    'nonparametric': {
        'independent': {'func': stats.mannwhitneyu, 'name': 'Mann-Whitney U test', 'stat': 'U'},
        'paired': {'func': stats.wilcoxon, 'name': 'Wilcoxon signed-rank test', 'stat': 'V'}
    }
}


@dataclass
class Operation:
    name: str
    params: dict
    timestamp: datetime.datetime
    row_count_before: int
    row_count_after: int


class AggregateData:
    age_thresh = (18, 95)  # Tuple of (min_age, max_age)
    age_change_thresh = 0.001  # Maximum difference between scan date change and age change
    dateofscan_thresh = (pd.Timestamp('1980-01-01'), pd.Timestamp.now() + pd.Timedelta(days=1))  # Valid range for date.of.scan

    def __init__(self, filename, summary_vars=None, log_direct_operations=True):
        self.filename = filename
        
        self.operations = []
        self.log_direct_operations = log_direct_operations
        
        self.is_loaded = False
        self.is_parsed = False
        self._data = None
        self._info = None
        self._metadata = None
        self.load()
        self.parse()
        self.validate()

        self.summary_vars = summary_vars
        if summary_vars is None:
            self.summary_vars = {
                'age.at.scan': 'mean',
                'formal.diagnosis.revised': 'category_counts',
                'sex': 'category_counts',
            }

    @property
    def data(self):
        return self._data
    
    @property
    def loc(self):
        return self._data.loc

    @property
    def iloc(self):
        return self._data.iloc
    
    def __getattr__(self, name):
        """Dynamically wrap pandas DataFrame methods to log operations."""
        attr = getattr(self._data, name, None)

        if attr is None:
            raise AttributeError(f"{type(self).__name__} has no attribute {name}")

        # If it's not callable (e.g. .columns), just return it
        if not callable(attr):
            return attr

        # Wrap DataFrame method
        @wraps(attr)
        def wrapper(*args, inplace=False, **kwargs):
            result = attr(*args, **kwargs)
            if inplace:
                self.add_operation(name=name, params={"args": args, "kwargs": kwargs}, before=self._data.shape[0], after=result.shape[0])
                self._data = result
            return result

        return wrapper
    
    def __getitem__(self, key):
        return self._data[key]

    @data.setter
    def data(self, value):
        old_value = self._data
        self._data = value
        if self.log_direct_operations:
            before = len(old_value) if old_value is not None else 0
            after = len(value) if value is not None else 0
            self.add_operation("direct_data_change", before=before, after=after)

    def load(self):
        """Load data from an Excel file into a pandas DataFrame."""
        # Make sure to read all sheets ('sheet_name=None').
        df = pd.read_excel(self.filename, sheet_name=['MND.Aggregate', 'MND.Aggregate.Key'])
        data = df['MND.Aggregate']
        info = df['MND.Aggregate.Key']

        self._data = data
        self._info = info
        self.is_loaded = True
        self.is_parsed = False
        self.add_operation(name="load", params={"filename": self.filename})

    def parse(self):
        """Parse the 'MND.Aggregate' sheet."""            
        df = self._data.set_index(['MND.ID', 'MND.IMAGING.session'])
        
        # Get rid of leading/trailing whitespace in column names.
        cols = {c: c.strip() for c in df.columns}
        df = df.rename(columns=cols)
        
        self._metadata = pd.DataFrame()
        self._metadata["age.at.scan_missing"] = df["age.at.scan"].eq("missing")
        self._metadata["sex_missing"] = df["sex"].eq("missing")
        self._metadata["sex.numerical_missing"] = df["sex.numerical"].eq("missing")
        self._metadata["date.of.scan_missing"] = df["date.of.scan"].eq("missing")
        self._metadata["DOB_missing"] = df["DOB"].eq("missing")

        df["age.at.scan"] = pd.to_numeric(df["age.at.scan"], errors="coerce")
        df["sex"] = df["sex"].apply(self.parse_sex)
        df["date.of.scan"] = pd.to_datetime(df["date.of.scan"], errors="coerce")
        df["DOB"] = pd.to_datetime(df["DOB"], errors="coerce")
        df['date.of.scan'] = pd.to_datetime(df['date.of.scan'], errors='coerce')

        self.is_parsed = True
        self._data = df

        self.add_operation(name="parse")

    @staticmethod
    def parse_sex(value):
        if pd.isna(value):
                return np.nan
            
        value = str(value).strip().lower()
        if value in ['m', 'male']:
            return 'male'
        elif value in ['f', 'female']:
            return 'female'
        else:
            return np.nan
        
    def validate(self):
        """Validate the parsed data."""
        if not self.is_loaded or not self.is_parsed:
            raise RuntimeError("Data must be loaded and parsed before validation.")

        self.validate_date_of_scan(self._data['date.of.scan'])
        self.validate_sex(self._data[['sex', 'sex.numerical']])
        self.validate_age(self._data[['age.at.scan', 'date.of.scan', 'DOB']])

        # Additional validation steps can be added here.
        self.add_operation(name="validate")
    
    @staticmethod
    def validate_sex(sex):
        sexes = {'male': 0, 'female': 1}
        
        # Check that numerical and string sex values are consistent
        # with each other.
        conv_sex = sex['sex'].apply(lambda x: sexes.get(x, -1))
        conv_sex_num = sex['sex.numerical'].apply(lambda x: x if x in [0, 1] else -1)

        mismatch = conv_sex != conv_sex_num
        if mismatch.any():
            mismatch_df = sex.loc[mismatch]

            msg = [f'{idx[0]}/{idx[1]}: Sex="{idx_ser["sex"]}" | Numeric={idx_ser["sex.numerical"]})' for idx, idx_ser in mismatch_df.T.items()]
            logging.warning(
                "\n".join(["Mismatch between 'sex' and 'sex.numerical':"] + msg) + "\n"
            )
        
        # Check that sex is consistent across sessions for the same MND.ID.
        if 'MND.ID' in sex.index.names:
            # Check sex as strings.
            sex_per_subject = sex['sex'].dropna().groupby(level='MND.ID').unique()
            inconsistent_sex_subjects = {
                sid: vals.tolist() for sid, vals in sex_per_subject.items() if len(vals) > 1
            }

            if inconsistent_sex_subjects:
                msg = [
                    f'{sid}: sex values={vals}' for sid, vals in inconsistent_sex_subjects.items()
                ]
                logging.warning(
                    "\n".join(["Inconsistent 'sex' across sessions for same MND.ID:"] + msg) + "\n"
                )

            # Check sex as numerical values.
            numeric = sex['sex.numerical'].where(sex['sex.numerical'].isin([0, 1]))
            numeric_per_subject = numeric.dropna().groupby(level='MND.ID').unique()
            inconsistent_numeric_subjects = {
                sid: vals.tolist() for sid, vals in numeric_per_subject.items() if len(vals) > 1
            }

            if inconsistent_numeric_subjects:
                msg = [
                    f'{sid}: sex.numerical values={vals}' for sid, vals in inconsistent_numeric_subjects.items()
                ]
                logging.warning(
                    "\n".join(["Inconsistent 'sex.numerical' across sessions for same MND.ID:" ] + msg) + "\n"
                )
        else:
            logging.warning(
                "validate_sex: MND.ID not found in index; subject-level consistency check skipped."
            )

    def validate_age(self, age):
        age = age.sort_values(['date.of.scan'])
        tmp_age = age['age.at.scan']
        tmp_date = age['date.of.scan']
        if not pd.api.types.is_numeric_dtype(tmp_age):
            logging.warning("Age must be numeric. Skipping validation.")
            return
        
        # Check that age values are within a range.
        too_low = tmp_age < self.age_thresh[0]
        too_low = tmp_age.loc[too_low]
        if not too_low.empty:
            msg = [f'{idx[0]}/{idx[1]}: Age={idx_age:.1f}' for idx, idx_age in too_low.items()]
            logging.warning(
                "\n".join([f"Age values below {self.age_thresh[0]} are unlikely to be valid:"] + msg)
            )
        
        too_high = tmp_age > self.age_thresh[1]
        too_high = tmp_age.loc[too_high]
        if not too_high.empty:
            msg = [f'{idx[0]}/{idx[1]}: Age={idx_age:.1f}' for idx, idx_age in too_high.items()]
            logging.warning(
                "\n".join([f"Age values above {self.age_thresh[1]} are unlikely to be valid:"] + msg)
            )

        # Check that age is consistent across sessions for the same MND.ID.
        if 'MND.ID' in age.index.names:
            messages = []
            for mndid, idx_age in age.groupby(level='MND.ID'):
                # If DOB is missing, age may be missing and the row is not flagged.
                # If DOB and date.of.scan are present but age.at.scan is missing, warn.
                # If date.of.scan is missing but age.at.scan is present, warn.
                age_missing = idx_age['age.at.scan'].isna()
                dob_present = idx_age['DOB'].notna()
                date_present = idx_age['date.of.scan'].notna()

                missing_age = age_missing & dob_present & date_present
                for idx in missing_age.index[missing_age]:
                    messages.append(f'{mndid}/{idx[1]}: DOB and date.of.scan present but age.at.scan missing.')

                age_but_no_date = ~age_missing & ~date_present
                for idx in age_but_no_date.index[age_but_no_date]:
                    messages.append(f'{mndid}/{idx[1]}: age.at.scan present but date.of.scan missing.')

                # Only one session, so no consistency check needed.
                if idx_age.shape[0] == 1:
                    continue

                if idx_age['age.at.scan'].isna().all():
                    continue
                    # logging.warning(f'MND.ID={mndid}: All age values are missing.')
                elif idx_age['age.at.scan'].notna().any() and idx_age['age.at.scan'].isna().any():
                    messages.append(f'{mndid}: Some age values are missing while others are not.')

                diffs = idx_age.dropna().diff().dropna()
                if diffs.empty:
                    continue  # Not enough data to check consistency.
                # The formula in the spreadsheet uses 365.4 for
                # calculating age at scan.
                diffs['date_days_change'] = diffs['date.of.scan'].apply(lambda x: x.days / 365.4)
                check = diffs['age.at.scan'] - diffs['date_days_change']
                mismatch = check.abs() > self.age_change_thresh

                if mismatch.any():
                    for idx, idx_diff in diffs.loc[mismatch].iterrows():
                        msg = [
                            f'{mndid}/{idx[1]}: Age changes by {idx_diff["age.at.scan"]:.3f} years while date changes by {idx_diff["date_days_change"]:.3f} years.'
                        ]
                        messages.extend(msg)

            if messages:
                logging.warning(
                    "\n".join(["Age issues across sessions for some MND.IDs:"] + messages) + "\n"
                )

    def validate_date_of_scan(self, date):
        if not pd.api.types.is_datetime64_any_dtype(date):
            logging.warning("Date of scan must be a datetime. Skipping validation.")
            return

        lower_date = self.dateofscan_thresh[0]
        upper_date = self.dateofscan_thresh[1]
        invalid_dates = date[(date < lower_date) | (date > upper_date)]
        if not invalid_dates.empty:
            msg = [f'{idx[0]}/{idx[1]}: date.of.scan={idx_date}' for idx, idx_date in invalid_dates.items()]
            logging.warning(
                "\n".join([f"date.of.scan values outside [{lower_date.date()}, {upper_date.date()}] are unlikely to be valid:"] + msg)
            )

    def parse_info(self):
        pass

    def query(self, query_str, inplace=False):
        """Query the data for specific conditions."""
        if not self.is_loaded or not self.is_parsed:
            raise RuntimeError("Data must be loaded and parsed before querying.")

        before = self._data.shape[0]
        result_df = self._data.query(query_str)
        after = result_df.shape[0]

        if inplace:
            self._data = result_df
            self.add_operation(
                name="query",
                params={"query_str": query_str},
                before=before,
                after=after,
            )

        return result_df

    def first_session_only(self, inplace=False):
        """Keep only the first imaging session for each MND.ID."""
        if not self.is_loaded or not self.is_parsed:
            raise RuntimeError("Data must be loaded and parsed before filtering.")

        # Rename None to 'index' (which is its default name when doing
        # 'reset_index()').
        idx = self._data.index.names
        idx = ['index' for n in idx if n is None]

        before = len(self._data.shape[0])
        first_sessions = self._data.reset_index().groupby('MND.ID')['MND.IMAGING.session'].min()
        filtered_df = self._data.reset_index().merge(first_sessions, on=['MND.ID', 'MND.IMAGING.session']).set_index(idx)
        after = len(filtered_df.shape[0])

        if inplace:
            self._data = filtered_df
            self.add_operation(
                name="first_session_only",
                before=before,
                after=after,
            )
        
        return filtered_df
    
    def summary(self, grouper=None):
        """Print summary statistics for specified variables."""
        if not self.is_loaded or not self.is_parsed:
            raise RuntimeError("Data must be loaded and parsed before summarizing.")
        
        if grouper is None:
            print("Summary statistics:")
            self._summary_stats()
        else:
            print(f"Summary statistics grouped by {grouper}:")
            self._summary_stats(data=self._data.groupby(grouper))

    def _summary_stats(self, data=None, summariser=None):
        if data is None:
            data = self._data

        mean_str = []
        count_str = []
        errors = []
        customs = []
        for col, summ_type in self.summary_vars.items():
            if summ_type == 'mean':
                stats = data[col].agg(["mean", "std"])
                if isinstance(stats, pd.Series):
                    mean_str.append(self._section_header(col))
                    mean_str.append(stats.to_frame().T.to_string())
                else:
                    # If the stats came from a groupby object.
                    mean_str.append(self._section_header(col))
                    mean_str.append(stats.to_string())
                    
            elif summ_type == 'category_counts':
                counts = data[col].value_counts()
                count_str.append(self._section_header(col))
                count_str.append(counts.to_string())
                
            elif summ_type == 'custom':
                if summariser is None:
                    errors.append(f"No custom summariser provided for column '{col}'")
                    continue
                res = summariser(data[col])
                res = res.rstrip('\n')
                customs.append(res)
            else:
                errors.append(f"Unknown summary type '{summ_type}' for column '{col}'")

        # The summation order also determines printing order.
        for item in mean_str + [''] + count_str + [''] + customs + [''] + errors:
            print(item)

    @staticmethod
    def _section_header(title, width=51, fill='-'):
        return f" {title} ".center(width, fill)

    def group_test(
        self,
        group_col,
        value_col=None,
        test="parametric",
        correction="holm",
        alternative="two-sided",
        paired=False,
        ci_level=0.95,
    ):
        """Perform a t-test between two groups defined by 'group_col' on 'value_col'."""
        if test not in TESTS:
            raise ValueError(f"Unsupported test type '{test}'. Supported tests are: {list(TESTS.keys())}.")
        test_obj = TESTS[test]['paired' if paired else 'independent']
        
        if not self.is_loaded or not self.is_parsed:
            raise RuntimeError("Data must be loaded and parsed before performing t-tests.")
        
        if value_col is None:
            # Choose all numeric columns.
            value_col = self._data.select_dtypes(include=[np.number]).columns
        elif isinstance(value_col, str):
            value_col = [value_col]
        
        # Get data for each group.
        groupby_obj = self._data.groupby(group_col)
        group_data = {
            gr: self._data.loc[gr_idx][value_col]
            for gr, gr_idx in groupby_obj.groups.items()
        }

        # Prepare all pairwise combinations of groups.
        groups = list(group_data.keys())
        combos = [(groups[i], groups[j]) for i in range(len(groups)) for j in range(i+1, len(groups))]

        results = defaultdict(dict)
        for val in value_col:
            stats = []
            raw_pvals = []
            cis = []
            m_diffs = []

            for g1, g2 in combos:
                group1 = group_data[g1][val].dropna()
                group2 = group_data[g2][val].dropna()

                test_func = test_obj['func']
                res = test_func(group1, group2, alternative=alternative)
                stats.append(res.statistic)
                raw_pvals.append(res.pvalue)
                if test == 'parametric':
                    cis.append(res.confidence_interval(confidence_level=ci_level))
                    m_diffs.append(np.nanmean(group1) - np.nanmean(group2))
                else:
                    cis.append(self._bootstrap_ci(group1, group2, level=ci_level, paired=paired))
                    m_diffs.append(np.nanmedian(group1) - np.nanmedian(group2))

            # Multiple comparisons correction.
            reject, pvals_corr, _, _ = multipletests(
                raw_pvals, method=correction
            )

            # Store results
            for i, (g1, g2) in enumerate(combos):
                results[val][(g1, g2)] = {
                    "stat": stats[i],
                    "p_raw": raw_pvals[i],
                    "p_corrected": pvals_corr[i],
                    "ci": cis[i],
                    "m_diff": m_diffs[i],
                }

        print(f"Results from {test_obj['name']} (p-vals corrected):")
        for val, group_results in results.items():
            print(self._section_header(val))
            for (g1, g2), res in group_results.items():
                stat_name = test_obj['stat']
                print(
                    f"{g1} vs {g2}:\n"
                    f"  Mean/Median difference = {res['m_diff']:.4g}\n"
                    f"  {ci_level*100:.1f}% CI = [{res['ci'].low:.4g}, {res['ci'].high:.4g}]\n"
                    f"  {stat_name} = {res['stat']:.4g}\n"
                    f"  p_raw = {res['p_raw']:.4g}\n"
                    f"  p_corr = {res['p_corrected']:.4g}\n"
                )

        return results

    def _bootstrap_ci(x, y, level=0.95, n_boot=2000, paired=False, method='bca'):
        """Compute bootstrap confidence interval for the difference in medians between two samples."""
        # Vectorised computations (indicated by using the axis argument
        #  in the function below) are faster.
        def median_diff(sample1, sample2, axis=-1):
            return np.median(sample1, axis=axis) - np.median(sample2, axis=axis)

        data = (x, y)
        # Calculate bootstrap confidence interval for difference in medians.
        boot_stats = stats.bootstrap(
            data,
            statistic=median_diff,
            vectorized=False,
            paired=paired,
            confidence_level=level,
            n_resamples=n_boot,
            method=method
        )

        return boot_stats.confidence_interval

    def add_operation(self, name, params=None, before=None, after=None):
        """Log an operation performed on the data."""
        if before is None:
            before = self._data.shape[0]
        if after is None:
            after = self._data.shape[0]
        if params is None:
            params = {}

        self.operations.append(
            Operation(
                name=name,
                params=params,
                timestamp=datetime.datetime.now(datetime.timezone.utc),
                row_count_before=before,
                row_count_after=after,
            )
        )

    def save(self, filename=None, save='dill', overwrite=False):
        """Save the current data to an Excel file."""
        if filename is None:
            filename = self.filename
        filename = Path(filename).stem

        # Supported save formats.
        filenames = {
            'dill': Path(filename + '.dill'),
            'excel': Path(filename + '.xlsx'),
            'log': Path(filename + '.log'),
        }
        if save not in list(filenames.keys()) + ['all']:
            raise ValueError(f"Unsupported save format '{save}'. Supported formats are: {list(filenames.keys())} and 'all'.")

        # Check for existing files. If save='all', check if any of the files exist.
        check_overwrite = (save == 'all' and any(Path(f).exists() for f in filenames.values())) or (filenames[save].exists())
        if check_overwrite:
            if overwrite is False:
                raise FileExistsError(f"One or more output files already exist. Use 'overwrite=True' to overwrite.")
            elif overwrite is True and 'onedrive' in str(filename).lower():
                # The file on OneDrive is the master copy - do not overwrite.
                raise ValueError("Overwriting files in OneDrive is not supported. Delete the files first or save elsewhere.")

        if 'dill' in save or save == 'all':
            with open(filenames['dill'], 'wb') as dill_file:
                dill.dump(self, dill_file)
            self.add_operation(name="save", params={"filename": filename + '.dill'})

        if 'excel' in save or save == 'all':
            with pd.ExcelWriter(filenames['excel'], engine="openpyxl") as writer:
                self._data.to_excel(writer, sheet_name='MND.Aggregate')
                self._info.to_excel(writer, sheet_name='MND.Aggregate.Key')
                self.add_operation(name="save", params={"filename": filename + '.xlsx'})

        if 'log' in save or save == 'all':
            self._save_operations_log(filenames['log'])

    def _save_operations_log(self, log_filename):
        """Save the operations log to a file."""
        with open(log_filename, 'w') as log_file:
            for op in self.operations:
                log_file.write(
                    f"{op.timestamp.isoformat()} - {op.name}\n"
                    f"  Params: {op.params}\n"
                    f"  Rows before: {op.row_count_before}, Rows after: {op.row_count_after}\n"
                    "\n"
                )
