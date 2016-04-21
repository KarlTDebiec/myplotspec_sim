#!/usr/bin/python
# -*- coding: utf-8 -*-
#   moldynplot.TimeSeries2DFigureManager.py
#
#   Copyright (C) 2015-2016 Karl T Debiec
#   All rights reserved.
#
#   This software may be modified and distributed under the terms of the
#   BSD license. See the LICENSE file for details.
"""
Generates one or more 2D time series figures to specifications in a YAML
file.
"""
################################### MODULES ###################################
from __future__ import absolute_import,division,print_function,unicode_literals
if __name__ == "__main__":
    __package__ = str("moldynplot")
    import moldynplot
from .myplotspec.FigureManager import FigureManager
################################### CLASSES ###################################
class TimeSeries2DFigureManager(FigureManager):
    """
    Manages the generation of 2D time series figures.
    """

    from .myplotspec.manage_defaults_presets import manage_defaults_presets
    from .myplotspec.manage_kwargs import manage_kwargs

    defaults = """
        draw_figure:
          subplot_kw:
            autoscale_on: False
          multi_tick_params:
            left:   on
            right:  off
            bottom: on
            top:    off
          shared_legend_kw:
            spines: False
            handle_kw:
              ls: none
              marker: s
              mec: black
            legend_kw:
              frameon: False
              handletextpad: 0
              loc: 9
              numpoints: 1
        draw_subplot:
          title_kw:
            verticalalignment: bottom
          xlabel: Time
          tick_params:
            direction: out
            bottom: on
            top:    off
            right:  off
            left:   on
          grid: True
          grid_kw:
            b: True
            color: [0.2,0.2,0.2]
            linestyle: '-'
        draw_dataset:
          draw_heatmap: True
          heatmap_kw:
            edgecolors: none
            rasterized: True
    """

    available_presets = """
      dssp:
        class: content
        help: Dynamic secondary structure of proteins calculated by cpptraj
        draw_figure:
          shared_legend: True
          shared_legend_kw:
            handles:
              "None":
                color: !!python/object/apply:moldynplot.dssp_cmap [0,0,7]
              "Parallel β Sheet":
                color: !!python/object/apply:moldynplot.dssp_cmap [1,0,7]
              "Antiparallel β Sheet":
                color: !!python/object/apply:moldynplot.dssp_cmap [2,0,7]
              "$3_{10}$ Helix":
                color: !!python/object/apply:moldynplot.dssp_cmap [3,0,7]
              "α Helix":
                color: !!python/object/apply:moldynplot.dssp_cmap [4,0,7]
              "π Helix":
                color: !!python/object/apply:moldynplot.dssp_cmap [5,0,7]
              "Turn":
                color: !!python/object/apply:moldynplot.dssp_cmap [6,0,7]
              "Bend":
                color: !!python/object/apply:moldynplot.dssp_cmap [7,0,7]
        draw_subplot:
          ylabel: Residue
        draw_dataset:
          dataset_kw:
            cls: moldynplot.CpptrajDataset.CpptrajDataset
            downsample_mode: mode
          heatmap_kw:
            cmap: !!python/object/apply:moldynplot.dssp_cmap []
            vmin: 0
            vmax: 7
      perres_rmsd:
        class: content
        help: Per-residue RMSD calculated by cpptraj
        draw_figure:
          shared_legend: False
        draw_dataset:
          dataset_kw:
            cls: moldynplot.CpptrajDataset.CpptrajDataset
            downsample_mode: mean
          heatmap_kw:
            cmap: afmhot_r
            vmin: 0
            vmax: 10
          draw_colorbar: True
          colorbar_kw:
            zticks: [0,1,2,3,4,5,6,7,8,9,10]
            zlabel: Per-Residue Backbone RMSD (Å)
      saxs:
        class: content
        help: Small-angle X-ray scattering calculated by saxs_md
        draw_figure:
          shared_legend: False
        draw_subplot:
          ylabel:      "q ($Å^{-1}$)"
          yticks:      [0.00,0.05,0.10,0.15,0.20,0.25,0.30,0.35]
          yticklabels: ["0.00","0.05","0.10","0.15","0.20","0.25","0.30","0.35"]
          grid_kw:
            color: [0.5,0.5,0.5]
        draw_dataset:
          dataset_kw:
            cls: moldynplot.CpptrajDataset.SAXSDataset
          heatmap_kw:
            cmap: bone
            vmin: 0
            vmax: 10000000
          draw_colorbar: True
          colorbar_kw:
            zlabel: Intensity
            zticks: [0,5000000,10000000]
      saxs_log:
        class: content
        help: Intensity on log scale
        extends: saxs
        draw_dataset:
          logz: True
          heatmap_kw:
            vmin: 5
            vmax: 10
          colorbar_kw:
            zlabel: $log_{10}$(Intensity)
            zticks: [5,6,7,8,9,10]
      manuscript:
        class: target
        inherits: manuscript
        draw_figure:
          left:       0.50
          sub_width:  4.40
          wspace:     0.05
          right:      0.20
          bottom:     0.80
          sub_height: 1.00
          hspace:     0.05
          top:        0.25
          shared_legend_kw:
            left:       0.50
            sub_width:  4.40
            bottom:     0.00
            sub_height: 0.40
            handle_kw:
              ms: 5
            legend_kw:
              legend_fp: 7r
              ncol: 4
        draw_subplot:
          xlabel_kw:
            labelpad: 3
          ylabel_kw:
            labelpad: 6
        draw_dataset:
          partner_kw:
            position: bottom
            hspace:     0.42
            sub_height: 0.05
            left:       1.82
            sub_width:  1.76
          colorbar_kw:
            ztick_fp:  6r
            zlabel_fp: 8b
            zlabel_kw:
              labelpad: 2
      manuscript_stacked_dssp:
        class: target
        extends: manuscript
        help: Set of vertically stacked DSSP plots
        draw_figure:
          sub_width: 6.31
          bottom:    0.60
          hspace:    0.00
          shared_ylabel_kw:
            left: -0.37
          shared_legend_kw:
            sub_width:  6.31
        draw_subplot:
          ylabel:
          ylabel_kw:
            labelpad: 6
            rotation: horizontal
          yticklabels: []
          ylabel_fp: 7r
      notebook:
        class: target
        inherits: notebook
        draw_figure:
          left:       0.60
          sub_width:  5.00
          wspace:     0.10
          right:      0.25
          bottom:     1.10
          sub_height: 2.00
          hspace:     0.10
          top:        0.35
          shared_legend_kw:
            left:       0.50
            sub_width:  5.00
            right:      0.25
            bottom:     0.10
            sub_height: 0.50
            legend_kw:
              ncol: 4
        draw_subplot:
          ylabel_kw:
            labelpad: 12
        draw_dataset:
          partner_kw:
            position: bottom
            left:       2.10
            sub_width:  2.00
            right:      1.75
            bottom:     0.40
            sub_height: 0.10
            top:        0.50
          colorbar_kw:
            ztick_fp: 8r
            zlabel_fp: 10b
            zlabel_kw:
              labelpad: 3
    """

    @manage_defaults_presets()
    @manage_kwargs()
    def draw_dataset(self, subplot, label=None,
        handles=None, logz=False,
        draw_heatmap=False, draw_colorbar=False, draw_legend=False,
        verbose=1, debug=0, **kwargs):
        import numpy as np
        from .myplotspec import multi_get_copy

        # Load data
        dataset_kw = multi_get_copy("dataset_kw", kwargs, {})
        if "infile" in kwargs:
            dataset_kw["infile"] = kwargs["infile"]
        dataset = self.load_dataset(verbose=verbose, debug=debug, **dataset_kw)
        dataframe = dataset.dataframe

        # Draw heatmap
        if draw_heatmap:
            heatmap_kw = multi_get_copy("heatmap_kw", kwargs, {})
            x = dataframe.index.values
            if hasattr(dataset, "y"):
                y = dataset.y
            else:
                y = np.array(range(1, dataframe.shape[1] + 2))
            z = dataframe.values.T
            if logz:
                z = np.log10(z)
            pcolormesh = subplot.pcolor(x, y, z, **heatmap_kw)

            # Draw colorbar
            if draw_colorbar:
                from .myplotspec.axes import set_colorbar

                if not hasattr(subplot, "_mps_partner_subplot"):
                    from .myplotspec.axes import add_partner_subplot

                    add_partner_subplot(subplot, verbose=verbose,
                      debug=debug, **kwargs)

                set_colorbar(subplot, pcolormesh, **kwargs)

#################################### MAIN #####################################
if __name__ == "__main__":
    TimeSeries2DFigureManager().main()
