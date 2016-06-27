# -*- coding: utf-8 -*-
#   moldynplot.Dataset.py
#
#   Copyright (C) 2015-2016 Karl T Debiec
#   All rights reserved.
#
#   This software may be modified and distributed under the terms of the
#   BSD license. See the LICENSE file for details.
"""
Manages Moldynplot datasets.

.. todo:
  - Fix ordering of argument groups: input, action, output
"""
################################### MODULES ###################################
from __future__ import absolute_import,division,print_function,unicode_literals
import h5py
import numpy as np
import pandas as pd
pd.set_option('display.width', 120)
from .myplotspec.Dataset import Dataset
from .myplotspec import sformat, wiprint
################################### CLASSES ###################################
class SequenceDataset(Dataset):
    """
    Manages sequence datasets.
    """

    default_h5_address = "/"
    default_h5_kw = dict(
      chunks      = True,
      compression = "gzip",
      dtype       = np.float32,
      scaleoffset = 5)

    @classmethod
    def get_cache_key(cls, infile=None, *args, **kwargs):
        """
        Generates tuple of arguments to be used as key for dataset
        cache.

        .. todo:
          - Verify that keyword arguments passed to pandas may be safely
            converted to hashable tuple, and if they cannot throw a
            warning and load dataset without caching
        """
        from os.path import expandvars

        if infile is None:
            return None
        read_csv_kw = []
        if "use_indexes" in kwargs:
            use_indexes = tuple(kwargs.get("use_indexes"))
        else:
            use_indexes = None
        for key, value in kwargs.get("read_csv_kw", {}).items():
            if isinstance(value, list):
                value = tuple(value)
            read_csv_kw.append((key, value))
        return (cls, expandvars(infile), use_indexes, tuple(read_csv_kw))

    @staticmethod
    def add_shared_args(parser, **kwargs):
        """
        Adds command line arguments shared by all subclasses.

        Arguments:
          parser (ArgumentParser): Nascent argument parser to which to
            add arguments
          kwargs (dict): Additional keyword arguments
        """

        # Process arguments
        arg_groups = {ag.title: ag for ag in parser._action_groups}

        # Output arguments
        output_group = arg_groups.get("output", 
          parser.add_argument_group("output"))
        output_group.add_argument(
          "-outfile",
          required = False,
          type     = str,
          help     = """text or hdf5 file to which processed results will be
                     output; may contain environment variables""")

        # Arguments from superclass
        super(SequenceDataset, SequenceDataset).add_shared_args(parser)

    def __init__(self, downsample=None, calc_pdist=False, **kwargs):
        """
        Initializes dataset.

        Arguments:
          infile (str): Path to input file, may contain environment
            variables
          usecols (list): Columns to select from DataFrame, once
            dataframe has already been loaded
          pdist (bool): Calculate probability distribution
          pdist_key (str): Column of which to calculate probability
            distribution
          kde_kw (dict): Keyword arguments passed to
            sklearn.neighbors.KernelDensity; key arguments are 'bandwidth' and
            'grid'
          verbose (int): Level of verbose output
          kwargs (dict): Additional keyword arguments
        """

        # Arguments
        verbose = kwargs.get("verbose", 1)

        # Load
        super(SequenceDataset, self).__init__( **kwargs)
        dataframe = self.dataframe
        dataframe.index.name = "residue"
        dataframe["amino acid"] = [str(i.split(":")[0])
                                     for i in dataframe.index.values]
        dataframe["index"] = [int(i.split(":")[1])
                               for i in dataframe.index.values]
        if "use_indexes" in kwargs:
            dataframe = self.dataframe = dataframe[
                          dataframe["index"].isin(kwargs.pop("use_indexes"))]
#        if True:
#            dataframe["r1/r2"]    = dataframe["r1"] / dataframe["r2"]
#            dataframe["r1/r2 se"] = np.sqrt((dataframe["r1 se"] /
#            dataframe["r1"]) ** 2 + (dataframe["r2 se"] / dataframe["r2"]) **
#            2) * dataframe["r1/r2"]

        if calc_pdist:
            self.calc_pdist(**kwargs)

    def calc_pdist(self, **kwargs):
        """
        Calcualtes probability distribution of time series.

        Arguments:
          pdist_kw (dict): Keyword arguments used to configure
            probability distribution calculation
          verbose (int): Level of verbose output
          kwargs (dict): Additional keyword arguments
        """
        from collections import OrderedDict
        from scipy.stats import norm

        # Arguments
        verbose = kwargs.get("verbose", 1)
        dataframe = self.dataframe

        pdist_kw = kwargs.get("pdist_kw", {})
        pdist_cols = [a for a in dataframe.columns.values
                      if not a.endswith(" se")
                      and str(dataframe[a].dtype).startswith("float")
                      and a + " se" in dataframe.columns.values]
        mode = "kde"
        if mode == "kde":

            # Prepare grids
            grid = pdist_kw.pop("grid", None)
            if grid is None:
                all_grid = None
                grid = {}
            elif isinstance(grid, list) or isinstance(grid, np.ndarray):
                all_grid = np.array(grid)
                grid = {}
            elif isinstance(grid, dict):
                all_grid = None
                pass
            for column, series in dataframe[pdist_cols].iteritems():
                if column in grid:
                    grid[column] = np.array(grid[column])
                elif all_grid is not None:
                    grid[column] = all_grid
                else:
                    grid[column] = np.linspace(series.min() - series.std(),
                                      series.max() + series.std(), 100)
            scale = {"r1":0.05, "r2":0.4, "noe":0.05, "r1/r2": 0.1}

            # Calculate probability distributions
            pdist = OrderedDict()
            for column in pdist_cols:
                qwer = dataframe[[column, column + " se"]]
                if verbose >= 1:
                    print("calculating probability distribution of "
                    "{0} using a kernel density estimate".format(column))
                g = grid[column]
                s = scale[column]
                pdf = np.zeros_like(g)
                for residue, b in qwer.iterrows():
                    if np.any(np.isnan(b.values)):
                        continue
#                    c = norm(loc=b[column], scale=b[column+" se"])
                    c = norm(loc=b[column], scale=s)
                    d = c.pdf(g)
                    pdf += c.pdf(g)
                pdf /= pdf.sum()
                series_pdist = pd.DataFrame(pdf, index=grid[column],
                  columns=["probability"])
                series_pdist.index.name = column
                pdist[column] = series_pdist

            self.pdist = pdist
            return pdist

    def read(self, infile, **kwargs):
        """
        """
        pass

    def write(self, outfile, **kwargs):
        """
        """
        from os.path import expandvars
        import re

        # Process arguments
        verbose = kwargs.get("verbose", 1)
        outfile = expandvars(outfile)

        if verbose >= 1:
            print("Writing sequence dataframe to '{0}'".format(outfile))

        # Check for /path/to/outfile.h5:/address
        is_h5 = re.match(
          r"^(?P<path>(.+)\.(h5|hdf5))((:)?(/)?(?P<address>.+))?$",
          outfile, flags=re.UNICODE)
        if is_h5:
            path    = is_h5.groupdict()["path"]
            address = is_h5.groupdict()["address"]
            if address is None or address == "":
                address = self.default_h5_address
            with h5py.File(path) as hdf5_file:
                h5_kw = self.default_h5_kw
                h5_kw.update(kwargs.get("h5_kw", {}))
                hdf5_file.create_dataset("{0}/values".format(address),
                  data=self.sequence_df.values, **h5_kw)
                hdf5_file.create_dataset("{0}/index".format(address),
                  data=np.array(self.sequence_df.index.values, np.str))
                hdf5_file[address].attrs["columns"] = str(
                  self.sequence_df.columns.tolist())
        else:
            with open(outfile, "w") as text_file:
                text_file.write(
                  self.sequence_df.to_string(col_space=12, sparsify=False))


class TimeSeriesDataset(Dataset):
    """
    Manages time series datasets.
    """

    def __init__(self, downsample=None, calc_pdist=False, **kwargs):
        """
        Initializes dataset.

        Arguments:
          infile (str): Path to input file, may contain environment
            variables
          usecols (list): Columns to select from DataFrame, once
            dataframe has already been loaded
          dt (float): Time interval between points; units unspecified
          toffset (float): Time offset to be added to all points (i.e.
            time of first point)
          downsample (int): Interval by which to downsample points
          downsample_mode (str): Method of downsampling; may be 'mean'
            or 'mode'
          pdist (bool): Calculate probability distribution
          pdist_key (str): Column of which to calculate probability
            distribution
          kde_kw (dict): Keyword arguments passed to
            sklearn.neighbors.KernelDensity; key argument is 'bandwidth'
          grid (ndarray): Grid on which to calculate probability
            distribution
          verbose (int): Level of verbose output
          kwargs (dict): Additional keyword arguments

          .. todo:
            - 'y' argument does not belong here; make sure it is
              removable
            - move downsampling to function
            - Calculate pdist for multiple columns
            - Make pdist a dataframe rather than explicit x and y
            - Calculate pdist using histogram
            - Verbose pdist
        """

        # Arguments
        verbose = kwargs.get("verbose", 1)

        # Load
        super(TimeSeriesDataset, self).__init__( **kwargs)
        timeseries = self.timeseries = self.dataframe
        timeseries.index.name = "time"

        if "usecols" in kwargs:
            timeseries = timeseries[timeseries.columns[kwargs.pop("usecols")]]

        # Convert from frame index to time
        if "dt" in kwargs:
            timeseries.index *= kwargs.pop("dt")

        # Offset time
        if "toffset" in kwargs:
            timeseries.index += kwargs.pop("toffset")
#
#        # Store y, if applicable
#        if "y" in kwargs:
#            self.y = kwargs.pop("y")

        # Downsample
        if downsample:
            self.downsample(downsample, **kwargs)

        if calc_pdist:
            self.calc_pdist(**kwargs)

    def downsample(self, downsample, downsample_mode="mean", **kwargs):
        """
        Downsamples time series.

        Arguments:
          downsample (int): Interval by which to downsample points
          downsample_mode (str): Method of downsampling; may be 'mean'
            or 'mode'
          verbose (int): Level of verbose output
          kwargs (dict): Additional keyword arguments
        """
        from scipy.stats.mstats import mode

        # Arguments
        verbose = kwargs.get("verbose", 1)
        timeseries = self.timeseries

        # Truncate dataset
        reduced = timeseries.values[
          :timeseries.shape[0] - (timeseries.shape[0] % downsample),:]
        new_shape = (int(reduced.shape[0]/downsample), downsample,
          reduced.shape[1])
        index = np.reshape(timeseries.index.values[
          :timeseries.shape[0]-(timeseries.shape[0] % downsample)],
          new_shape[:-1]).mean(axis=1)
        reduced = np.reshape(reduced, new_shape)

        # Downsample
        if downsample_mode == "mean":
            if verbose >= 1:
                print("downsampling by factor of {0} using mean".format(
                  downsample))
            reduced = np.squeeze(reduced.mean(axis=1))
        elif downsample_mode == "mode":
            if verbose >= 1:
                print("downsampling by factor of {0} using mode".format(
                  downsample))
            reduced = np.squeeze(mode(reduced, axis=1)[0])

        # Store downsampled time series
        reduced = pd.DataFrame(data=reduced, index=index,
          columns=timeseries.columns.values)
        reduced.index.name = "time"
        timeseries = self.timeseries = reduced

        return timeseries

    def calc_error(self, error_method="std", **kwargs):
        """
        Calculates standard error using time series data.

        .. todo:
          - Support breaking into blocks (essentially downsampling,
            then calculating standard error)
        """

        # Arguments
        verbose = kwargs.get("verbose", 1)
        timeseries=self.timeseries

        # Calculate standard error
        if error_method == "std":
            if verbose >= 1:
                print("calculating standard error using standard deviation")
            se = timeseries.std()
        elif error_method == "block":
            from .fpblockaverager.FPBlockAverager import FPBlockAverager
            if verbose >= 1:
                print("calculating standard error using block averaging")
            ba = FPBlockAverager(timeseries, **kwargs)
            se = ba.parameters.loc["exp", "a (se)"]
        else:
            if verbose >= 1:
                print("error_method '{0}' not understood, ".format(scale) +
                      "must be one of 'std', 'block'; not calculating error.")
            return

        return se

    def calc_pdist(self, **kwargs):
        """
        Calcualtes probability distribution of time series.

        Arguments:
          pdist_kw (dict): Keyword arguments used to configure
            probability distribution calculation
          verbose (int): Level of verbose output
          kwargs (dict): Additional keyword arguments
        """
        from collections import OrderedDict
        from sklearn.neighbors import KernelDensity

        # Arguments
        verbose = kwargs.get("verbose", 1)
        timeseries = self.timeseries

        pdist_kw = kwargs.get("pdist_kw", {"bandwidth": 0.1})
        mode = "kde"
        if mode == "kde":

            # Prepare bandwidths
            bandwidth = pdist_kw.pop("bandwidth", None)
            if bandwidth is None:
                all_bandwidth = None
                bandwidth = {}
            elif isinstance(bandwidth, float):
                all_bandwidth = bandwidth
                bandwidth = {}
            elif isinstance(bandwidth, dict):
                all_bandwidth = None
                pass
            for column, series in timeseries.iteritems():
                if column in bandwidth:
                    bandwidth[column] = float(bandwidth[column])
                elif all_bandwidth is not None:
                    bandwidth[column] = all_bandwidth
                else:
                    bandwidth[column] = series.std() / 10.0

            # Prepare grids
            grid = pdist_kw.pop("grid", None)
            if grid is None:
                all_grid = None
                grid = {}
            elif isinstance(grid, list) or isinstance(grid, np.ndarray):
                all_grid = np.array(grid)
                grid = {}
            elif isinstance(grid, dict):
                all_grid = None
                pass
            for column, series in timeseries.iteritems():
                if column in grid:
                    grid[column] = np.array(grid[column])
                elif all_grid is not None:
                    grid[column] = all_grid
                else:
                    grid[column] = np.linspace(series.min() - series.std(),
                                      series.max() + series.std(), 100)

            # Calculate probability distributions
            kde_kw = pdist_kw.get("kde_kw", {})
            pdist = OrderedDict()
            for column, series in timeseries.iteritems():
                if verbose >= 1:
                    print("calculating probability distribution of "
                    "{0} using a kernel density estimate".format(column))
                kde = KernelDensity(bandwidth=bandwidth[column], **kde_kw)
                kde.fit(series[:, np.newaxis])
                pdf = np.exp(kde.score_samples(grid[column][:, np.newaxis]))
                pdf /= pdf.sum()
                series_pdist = pd.DataFrame(pdf, index=grid[column],
                  columns=["probability"])
                series_pdist.index.name = column
                pdist[column] = series_pdist

            self.pdist = pdist
            return pdist

class SAXSDataset(Dataset):
    """
    Manages Small Angle X-ray Scattering datasets.
    """

    def scale(self, scale, **kwargs):
        """
        Scales SAXS intensity, either by a constant or to match the
        intensity of a target dataset.

        Arguments:
          scale (float, str): If float, proportion by which to scale
            intensity; if str, path to input file to which intensity
            will be scaled, may contain environment variables
          curve_fit_kw (dict): Keyword arguments passed to
            scipy.optimize.curve_fit (scale to match target dataset
            only)
          verbose (int): Level of verbose output
          kwargs (dict): Additional keyword arguments
        """
        from os.path import expandvars, isfile
        from scipy.interpolate import interp1d
        from scipy.optimize import curve_fit
        import six

        verbose = kwargs.get("verbose", 1)

        # Scale by constant
        if (isinstance(scale, float) 
        or (isinstance(scale, int) and not isinstance(scale, bool))):
            scale = float(scale)
        # Scale to match target
        elif isinstance(scale, six.string_types):
            if not isfile(expandvars(scale)):
                if verbose >= 1:
                    print("scale target '{0}' ".format(scale) +
                          "not found, not scaling.")
                return

            # Prepare target
            target = self.load_dataset(infile=expandvars(scale),
                       loose=True).dataframe
            if "intensity_se" in target.columns.values:
                scale_se = True
            else:
                scale_se = False
            target_q = np.array(target.index.values, np.float64)
            target_I = np.array(target["intensity"], np.float64)
            if scale_se:
                target_Ise = np.array(target["intensity_se"], np.float64)

            # Prepare own values over x range of target
            template = self.dataframe
            template_q  = np.array(template.index.values, np.float64)
            template_I  = np.array(template["intensity"].values, np.float64)
            indexes = np.logical_and(template_q > target_q.min(),
                                     template_q < target_q.max())
            template_q = template_q[indexes]
            template_I = template_I[indexes]

            # Update target
            target_I = interp1d(target_q, target_I, kind="cubic")(template_q)
            if scale_se:
                target_Ise = interp1d(target_q, target_Ise,
                               kind="cubic")(template_q)

            def scale_I(_, a):
                return a * template_I
#            curve_fit_kw = dict(p0=(1), bounds=(0.0,0.35))
            curve_fit_kw = dict(p0=(1))     # Not clear why bounds broke
            curve_fit_kw.update(kwargs.get("curve_fit_kw", {}))
            if scale_se:
                curve_fit_kw["sigma"] = target_Ise
            scale = curve_fit(scale_I, template_q, target_I,
                      **curve_fit_kw)[0][0]
        # 'scale' argument not understood
        else:
            if verbose >= 1:
                print("scale target '{0}' ".format(scale) +
                      "not understood, not scaling.")
            return

        if verbose >= 1:
            print("scaling by factor of {0}".format(scale))
        self.dataframe["intensity"] *= scale
        if "intensity_se" in self.dataframe.columns.values:
            self.dataframe["intensity_se"] *= scale

        return scale

class IREDSequenceDataset(SequenceDataset):
    """
    Manages iRED sequence datasets.
    """

    @staticmethod
    def construct_argparser(subparsers=None, **kwargs):
        """
        Constructs argument parser, either new or as a subparser.

        Arguments:
          subparsers (_SubParsersAction, optional): Nascent collection
            of subparsers to which to add; if omitted, a new parser will
            be generated
          kwargs (dict): Additional keyword arguments

        Returns:
          parser (ArgumentParser): Argument parser or subparser
        """
        import argparse

        # Process arguments
        help_message = """Process relaxation data calculated from MD
          simulation using the iRED method as implemented in cpptraj;
          treat infiles as independent simulations; processed results
          are the average across the simulations, including standard
          errors calculated using standard deviation"""
        if subparsers is not None:
            parser = subparsers.add_parser(
              name        = "ired",
              description = help_message,
              help        = help_message)
        else:
            parser = argparse.ArgumentParser(
              description = help_message)

        # Locked defaults
        parser.set_defaults(cls=IREDSequenceDataset)
        input_group  = parser.add_argument_group("input")

        # Arguments from superclass
        super(IREDSequenceDataset, IREDSequenceDataset).add_shared_args(parser)

        # Input arguments
        input_group = parser.add_argument_group("input")
        input_group.add_argument(
          "-infiles",
          required = True,
          dest     = "infiles",
          metavar  = "INFILE",
          nargs    = "+",
          type     = str,
          help     = """cpptraj iRED output file(s) from which to load
                     datasets; may be plain text or compressed, and may contain
                     environment variables and wildcards""")
        input_group.add_argument(
          "-indexfile",
          required = False,
          type     = str,
          help     = """text file from which to load residue names; should list
                    amino acids in the form 'XAA:#' separated by whitespace; if
                    omitted will be taken from rows of first infile; may
                    contain environment variables""")

        return parser

    @staticmethod
    def identify_infile(infile, **kwargs):
        """
        Determines if an infile contains iRED relaxation data, iRED
        order parameters, or neither

        Arguments:
          infile (str): Path to input file

        Returns:
          kind (str): Kind of data in *infile*; may be 'ired_relax',
            'ired_order', or 'other'

        .. todo:
          - Identify pandas files and hdf5 files
        """
        import six
        from os import devnull
        import re
        from subprocess import Popen, PIPE

        re_t1t2noe = re.compile(
          r"^#Vec\s+[\w_]+\[T1\]\s+[\w_]+\[\T2\]\s+[\w_]+\[NOE\]$",
          flags=re.UNICODE)
        re_order = re.compile(
          r"^#Vec\s+[\w_]+\[S2\]$", flags=re.UNICODE)

        with open(devnull, "w") as fnull:
            header = Popen("head -n 1 {0}".format(infile),
              stdout=PIPE, stderr=fnull, shell=True).stdout.read().strip()
            if six.PY3:
                header = str(header, "utf-8")

        if re.match(re_t1t2noe, header):
            return "ired_relax"
        elif re.match(re_order, header):
            return "ired_order"
        else:
            return "other"

    @staticmethod
    def parse_ired(infiles, **kwargs):
        """
        Parses a series of cpptraj iRED files.

        Arguments:
          infiles (list): Path(s) to input file(s)
          verbose (int): Level of verbose output
          kwargs (dict): Additional keyword arguments

        Returns:
          relax_dfs (list): DataFrames containing data from relax infiles
          order_dfs (list): DataFrames containing data from order infiles
        """

        # Process arguments
        verbose = kwargs.get("verbose", 1)

        # Load data
        relax_dfs = []
        order_dfs = []
        for i, infile in enumerate(infiles):

            # Determine if infile contains relaxation or order parameters
            kind = IREDSequenceDataset.identify_infile(infile)

            # Parse relaxation
            if kind == "ired_relax":
                if verbose >= 1:
                    wiprint("""Loading iRED relaxation data from '{0}'
                            """.format(infile))
                raw_data = pd.read_csv(infile, delim_whitespace=True,
                  header=0, index_col=0, names=["r1","r2","noe"])
                raw_data["r1"] = 1 / raw_data["r1"]
                raw_data["r2"] = 1 / raw_data["r2"]
                relax_dfs.append(raw_data)

            # Parse order parameters
            elif kind == "ired_order":
                if verbose >= 1:
                    wiprint("""Loading iRED order parameter data from '{0}'
                            """.format(infile))
                raw_data = pd.read_csv(infile, delim_whitespace=True,
                  header=0, index_col=0, names=["s2"])
                order_dfs.append(raw_data)

            # Input file not understood
            else:
                raise Exception(sformat("""parse_ired() cannot read infile
                  '{0}'; if loading iREDdata from cpptaj, all infiles must
                  contain either iRED relaxation data or order parameters
                  """.format(infile)))

        return relax_dfs, order_dfs

    @staticmethod
    def average_independent(relax_dfs=None, order_dfs=None, **kwargs):
        """
        Calculates the average and standard error of a set of independent
        datasets.

        Arguments:
          relax_dfs (list): DataFrames containing data from relax infiles
          order_dfs (list): DataFrames containing data from order infiles
          kwargs (dict): Additional keyword arguments

        Returns:
          df (DataFrame): Averaged dataframe including relax and order
        """

        # Process arguments
        verbose = kwargs.get("verbose", 1)
        df = pd.DataFrame()

        # Process relaxation
        if len(relax_dfs) == 1:
            if verbose >= 1:
                wiprint("""Single relaxation infile provided; skipping error
                        calculation""")
            df["r1"]  = relax_dfs[0]["r1"]
            df["r2"]  = relax_dfs[0]["r2"]
            df["noe"] = relax_dfs[0]["noe"]
        elif len(relax_dfs) >= 2:
            if verbose >= 1:
                wiprint("""Calculating mean and standard error of {0}
                        relaxation infiles""".format(len(relax_dfs)))
            relax_dfs = pd.concat(relax_dfs)
            relax_mean     = relax_dfs.groupby(level=0).mean()
            relax_se       = relax_dfs.groupby(level=0).std() / \
                               np.sqrt(len(relax_dfs))
            df["r1"]     = relax_mean["r1"]
            df["r1 se"]  = relax_se["r1"]
            df["r2"]     = relax_mean["r2"]
            df["r2 se"]  = relax_se["r2"]
            df["noe"]    = relax_mean["noe"]
            df["noe se"] = relax_se["noe"]

        # Process order parameters
        if len(order_dfs) == 1:
            if verbose >= 1:
                wiprint("""Single order parameter infile provided; skipping
                        error calculation""")
            df["s2"] = order_dfs[0]["s2"]
        elif len(order_dfs) >= 2:
            if verbose >= 1:
                wiprint("""Calculating mean and standard error of {0} order
                        parameter infiles""".format(len(order_dfs)))
            order_dfs   = pd.concat(order_dfs)
            order_mean  = order_dfs.groupby(level=0).mean()
            order_se    = order_dfs.groupby(level=0).std() / \
                          np.sqrt(len(order_dfs))
            df["s2"]    = order_mean["s2"]
            df["s2 se"] = order_se["s2"]

        return df

    def __init__(self, infiles, indexfile=None, outfile=None, **kwargs):
        """
        Initializes.

        Arguments:
          infiles (list): Path(s) to input file(s); may contain
            environment variables and wildcards
          indexfile (str): Path to index file used to map vector numbers
            listed in *infiles* to amino acid residues. Should contain
            one amino acid per line in the form 'XAA:#'
          outfile (str): Path to output text or hdf5 file
        """

        # Process arguments
        verbose = kwargs.get("verbose", 1)
        infiles = self.process_infiles(infiles)
        if len(infiles) == 0:
            raise Exception(sformat("""No infiles found matching '{0}'
              """.format(kwargs.get("infiles"))))
        elif verbose >= 1:
            if len(infiles) == 1:
                wiprint("""Loading iRED data from '{0}'
                        """.format(len(infiles), infiles[0]))
            elif len(infiles) >= 2:
                wiprint("""Loading iRED data from {0} infiles, starting with
                        '{1}' """.format(len(infiles), infiles[0]))

        # Load as dataframe or cpptraj
        if len(infiles) == 1:
            pass
            # Check if infile is a pandas-format text file or hdf5 etc.
        else:
            relax_dfs, order_dfs = self.parse_ired(infiles, **kwargs)
            df = self.average_independent(relax_dfs, order_dfs, **kwargs)

        # Apply index
        if indexfile is not None:
            indexfile = self.process_infiles(indexfile)[0]
            if verbose >= 1:
                wiprint("""Loading residue indexes from '{0}'
                        """.format(indexfile))
            res_index = np.loadtxt(indexfile, dtype=np.str).flatten()
            df.set_index(res_index, inplace=True)
            df.index.name = "residue" 
        else:
            df.index.name = "vector"

        if verbose >= 2:
            if verbose >= 1:
                print("Processed sequence dataframe:")
                print(df)
        self.sequence_df = df

        # Write outfile
        if outfile is not None:
            self.write(outfile)

class IREDTimeSeriesDataset(TimeSeriesDataset):
    """
    Manages iRED time series datasets.
    """

    @staticmethod
    def construct_argparser(subparsers=None, **kwargs):
        """
        Constructs argument parser, either new or as a subparser.

        Arguments:
          subparsers (_SubParsersAction, optional): Nascent collection
            of subparsers to which to add; if omitted, a new parser will
            be generated
          kwargs (dict): Additional keyword arguments

        Returns:
          parser (ArgumentParser): Argument parser or subparser
        """
        import argparse

        # Process arguments
        help_message = """Process relaxation data calculated from MD
          simulation using the iRED method as implemented in cpptraj;
          treat infiles as consecutive (potentially overlapping)
          excerpts of a longer simulation; processed results are a
          timeseries and the average across the timeseries, including
          standard errors calculated using block averaging"""
        if subparsers is not None:
            parser = subparsers.add_parser(
              name = "ired_timeseries",
              description = help_message,
              help        = help_message)
        else:
            parser = argparse.ArgumentParser(
              description = help_message)

        # Locked defaults
        parser.set_defaults(cls=IREDTimeSeriesDataset)

        # Arguments from superclass
        super(IREDTimeSeriesDataset, IREDTimeSeriesDataset).add_shared_args(
          parser)

        # Input arguments
        input_group  = parser.add_argument_group("input")
        input_group.add_argument(
          "-infiles",
          required = True,
          dest     = "infiles",
          metavar  = "INFILE",
          nargs    = "+",
          type     = str,
          help     = """cpptraj iRED output file(s) from which to load
                     datasets; may be plain text or compressed, and may
                     contain environment variables and wildcards""")
        input_group.add_argument(
          "-indexfile",
          required = False,
          type     = str,
          help     = """text file from which to load residue names; should list
                     amino acids in the form 'XAA:#' separated by whitespace;
                     if omitted will be taken from rows of first infile; may
                     contain environment variables""")

        # Output arguments
        output_group = parser.add_argument_group("output")
        output_group.add_argument(
          "-outfile",
          required = False,
          type     = str,
          help     = """text or hdf5 file to which processed results will be
                     output; may contain environment variables""")

        return parser

    def __init__(**kwargs):
        pass


class NatConDataset(TimeSeriesDataset):
    """
    Manages native contact datasets.
    """

    def __init__(self, downsample=None, calc_pdist=True, **kwargs):
        """
        Initializes dataset.

        Arguments:
          infile (str): Path to input file, may contain environment
            variables
          usecols (list): Columns to select from DataFrame, once
            dataframe has already been loaded
          dt (float): Time interval between points; units unspecified
          toffset (float): Time offset to be added to all points (i.e.
            time of first point)
          cutoff (float): Minimum distance within which a contact is
            considered to be formed
          downsample (int): Interval by which to downsample points using
            mode
          pdist (bool): Calculate probability distribution
          verbose (int): Level of verbose output
          kwargs (dict): Additional keyword arguments
        """
        verbose = kwargs.get("verbose", 1)

        # Load
        super(NatConDataset, self).__init__(**kwargs)
        dataframe = self.dataframe
        n_contacts = self.dataframe.shape[1]

        # Convert minimum distances to percent native contacts
        cutoff = kwargs.get("cutoff", 5.5)
        percent = pd.DataFrame(data=(dataframe.values <= cutoff).sum(axis=1)
          / dataframe.shape[1], index=dataframe.index,
          columns=["percent_native_contacts"])
        dataframe = self.dataframe = percent

        # Downsample; flag included in function definition to prevent
        #   superclass from downsampling before applying cutoff
        if downsample is not None:
            from scipy.stats.mstats import mode

            if verbose >= 1:
                print("downsampling by factor of {0} using mode".format(
                  downsample))

            reduced = dataframe.values[
              :dataframe.shape[0]-(dataframe.shape[0] % downsample),:]
            new_shape=(int(reduced.shape[0]/ downsample),
                downsample, reduced.shape[1])
            index = np.reshape(dataframe.index.values[
              :dataframe.shape[0]-(dataframe.shape[0] % downsample)],
              new_shape[:-1]).mean(axis=1)
            reduced = np.reshape(reduced, new_shape)
            reduced = np.squeeze(mode(reduced, axis=1)[0])
            reduced = pd.DataFrame(data=reduced, index=index,
              columns=dataframe.columns.values)
            reduced.index.name = "time"
            dataframe = self.dataframe = reduced

        # Calculate probability distribution
        if calc_pdist:
            if verbose >= 1:
                print("calculating probability distribution using histogram")
            bins = np.linspace(0-((1/n_contacts)/2), 1+((1/n_contacts)/2),
              n_contacts+1)
            pdist, _ = np.histogram(self.dataframe.values, bins)
            pdist    =  np.array(pdist, np.float) / pdist.sum()
            pdist_x = np.zeros(bins.size*2)
            pdist_y = np.zeros(bins.size*2)
            pdist_x[::2]    = pdist_x[1::2]   = bins
            pdist_y[1:-1:2] = pdist_y[2:-1:2] = pdist
            self.pdist_x = pdist_x
            self.pdist_y = pdist_y

class SAXSTimeSeriesDataset(TimeSeriesDataset, SAXSDataset):
    """
    Manages Small Angle X-ray Scattering time series datasets.
    """

    def __init__(self, infile, address="saxs", downsample=None,
        calc_mean=False, calc_error=True, error_method="std", scale=False,
        **kwargs):
        """
        Initializes dataset.

        Arguments:
          infile (str): Path to input file, may contain environment
            variables
          usecols (list): Columns to select from DataFrame, once
            dataframe has already been loaded
          dt (float): Time interval between points; units unspecified
          toffset (float): Time offset to be added to all points (i.e.
            time of first point)
          downsample (int): Interval by which to downsample points
          verbose (int): Level of verbose output
          kwargs (dict): Additional keyword arguments

        .. todo:
          - Calculate error
          - Shift downsampling to superclass
        """
        from os.path import expandvars

#        # Arguments
#        verbose = kwargs.get("verbose", 1)
#
#        # Load
#        with h5py.File(expandvars(infile)) as h5_file:
#            q = ["{0:5.3f}".format(a) for a in np.array(h5_file[address+"/q"])]
#        super(SAXSTimeSeriesDataset, self).__init__(infile=infile,
#          address=address+"/intensity", dataframe_kw=dict(columns=q), **kwargs)
#        timeseries = self.timeseries = self.dataframe
#
#        # Downsample
#        if downsample:
#            self.downsample(downsample, downsample_mode="mean", **kwargs)
#
#        # Average over time series
#        if calc_mean:
#            self.dataframe = dataframe = pd.DataFrame(
#              data=timeseries.mean(axis=0), columns=["intensity"])
#            dataframe.index.name = "q"
#            dataframe.index = np.array(timeseries.columns.values, np.float)
#
#            # Scale
#            if scale:
##                curve_fit_kw = dict(p0=(2e-9), bounds=(0.0,0.35))
#                curve_fit_kw = dict(p0=(2e-9))  # Not clear why bounds broke
#                curve_fit_kw.update(kwargs.get("curve_fit_kw", {}))
#                scale = self.scale(scale, curve_fit_kw=curve_fit_kw, **kwargs)
#                self.timeseries *= scale
#        elif scale:
#            self.timeseries *= scale
#        if calc_error:
#            se = self.calc_error(error_method="block", **kwargs)
#            se.name = "intensity_se"
#            dataframe = self.dataframe = pd.concat([dataframe, se], axis=1)

class SAXSExperimentDataset(SAXSDataset):
    """
    Manages Small Angle X-ray Scattering experimental datasets.
    """

    def __init__(self, scale=False, **kwargs):
        """
        Initializes dataset.

        Arguments:
          infile (str): Path to input file, may contain environment
            variables
          verbose (int): Level of verbose output
          kwargs (dict): Additional keyword arguments
        """
        from os.path import expandvars

        # Load
        super(SAXSExperimentDataset, self).__init__(**kwargs)
        dataframe = self.dataframe

        # Scale
        if scale:
            self.scale(scale, **kwargs)

class SAXSDiffDataset(SAXSDataset):
    """
    Manages Small Angle X-ray Scattering difference datasets.
    """

#    @classmethod
#    def get_cache_key(cls, dataset_classes=None, *args, **kwargs):
#        """
#        Generates tuple of arguments to be used as key for dataset
#        cache.
#
#        Arguments documented under :func:`__init__`.
#        """
#        from .myplotspec import multi_get_copy
#
#        minuend_kw = multi_get_copy(["minuend", "minuend_kw"], kwargs, {})
#        minuend_class = dataset_classes[minuend_kw["kind"].lower()]
#        key = [cls, mask_cutoff, minuend_class.get_cache_key(**minuend_kw)]
#
#        subtrahend_kw = multi_get_copy(["subtrahend", "subtrahend_kw"],
#          kwargs, {})
#        if isinstance(subtrahend_kw, dict):
#            subtrahend_kw = [subtrahend_kw]
#        for sh_kw in subtrahend_kw:
#            sh_class = dataset_classes[sh_kw.pop("kind").lower()]
#            key.append(sh_class.get_cache_key(**sh_kw))
#
#        return tuple(key)

    def __init__(self, dataset_cache=None, **kwargs):
        from sys import exit
        from .myplotspec import multi_get_copy

        self.dataset_cache = dataset_cache

        minuend_kw    = multi_get_copy(["minuend", "minuend_kw"],
                          kwargs, {})
        subtrahend_kw = multi_get_copy(["subtrahend", "subtrahend_kw"],
                          kwargs, {})
        minuend    = self.load_dataset(loose=True, **minuend_kw)
        subtrahend = self.load_dataset(loose=True, **subtrahend_kw)
        m_I    = minuend.dataframe["intensity"]
        m_I_se = minuend.dataframe["intensity_se"]
        s_I    = subtrahend.dataframe["intensity"]
        s_I_se = subtrahend.dataframe["intensity_se"]
        diff_I    = (m_I - s_I)
        diff_I_se = np.sqrt(m_I_se**2 +s_I_se**2)
        diff_I.name = "intensity"
        diff_I_se.name = "intensity_se"
        self.dataframe = pd.concat([diff_I, diff_I_se], axis=1)

class H5Dataset(object):
    """
    Class for managing hdf5 datasets

    .. todo:
      - Reimplement or depreciate
    """

    def __init__(self, **kwargs):
        """
        Initializes dataset.

        Arguments:
          infiles (list): List of infiles
          infile (str): Alternatively, single infile
        """
        self.default_address = kwargs.get("default_address", "")
        self.default_key     = kwargs.get("default_key",     "key")
        self.datasets        = {}
        self.attrs           = {}

        if   "infiles" in kwargs:
            self.load(infiles = kwargs.pop("infiles"))
        elif "infile"  in kwargs:
            self.load(infiles = [kwargs.pop("infile")])

    def load(self, infiles, **kwargs):
        """
        Loads data from h5 files.

        Arguments:
          infiles (list): infiles
        """
        from os.path import expandvars, isfile
        from h5py import File as h5
        import numpy as np
        import six

        for infile in infiles:
            if isinstance(infile, six.string_types):
                path    = expandvars(infile)
                address = self.default_address
                key     = self.default_key
            elif isinstance(infile, dict):
                path    = expandvars(infile.pop("path"))
                address = infile.pop("address", self.default_address)
                key     = infile.pop("key",     self.default_key)
            elif isinstance(infile, list):
                if len(infile) >= 1:
                    path = expandvars(infile[0])
                else:
                    raise OSError("Path to infile not provided")
                if len(infile) >= 2:
                    address = infile[1]
                else:
                    address = self.default_address
                if len(infile) >= 3:
                    key     = infile[2]
                else:
                    key     = self.default_key

            if not isfile(path):
                raise OSError("h5 file '{0}' does not exist".format(path))

            with h5(path) as in_h5:
                if address not in in_h5:
                    raise KeyError("Dataset {0}[{1}] not found".format(path,
                      address))
                dataset            = in_h5[address]
                self.datasets[key] = np.array(dataset)
                self.attrs[key]    = dict(dataset.attrs)
            print("Loaded Dataset {0}[{1}]; Stored at {2}".format(
              path, address, key))
