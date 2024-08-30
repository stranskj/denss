#!/usr/bin/env python
#
#    denss.regrid.py
#    A tool for regridding a scattering profile using interpolation.
#
#    Part of the DENSS package
#    DENSS: DENsity from Solution Scattering
#    A tool for calculating an electron density map from solution scattering data
#
#    Tested using Anaconda / Python 2.7
#
#    Author: Thomas D. Grant
#    Email:  <tdgrant@buffalo.edu>
#    Copyright 2023-Present The Research Foundation for SUNY
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

from __future__ import print_function
import os, argparse, sys
import logging
import numpy as np
from scipy import interpolate
from saxstats._version import __version__
import saxstats.saxstats as saxs
from textwrap import wrap

parser = argparse.ArgumentParser(description="A tool for calculating a scattering profile from an electron density map and fitting to experimental SWAXS data.", formatter_class=argparse.RawTextHelpFormatter)
parser.add_argument("--version", action="version",version="%(prog)s v{version}".format(version=__version__))
parser.add_argument("-f", "--file", type=str, help="Scattering profile filename (required)")
parser.add_argument("-q", "--qfile", default=None, type=str, help="ASCII text filename to use for setting the calculated q values (like a SAXS .dat file, but just uses first column, optional).")
parser.add_argument("-qmax", "--qmax", default=None, type=float, help="Maximum q value for calculated intensities (optional)")
parser.add_argument("-nq", "--nq", default=None, type=int, help="Number of data points in calculated intensity profile (optional)")
parser.add_argument("-n1", "--n1", default=None, type=int, help="First data point to use of experimental data")
parser.add_argument("-n2", "--n2", default=None, type=int, help="Last data point to use of experimental data")
parser.add_argument("-u", "--units", default="a", type=str, help="Angular units of experimental data (\"a\" [1/angstrom] or \"nm\" [1/nanometer]; default=\"a\"). If nm, will convert output to angstroms.")
parser.add_argument("--plot_on", dest="plot", action="store_true", help="Plot the profile (requires Matplotlib, default if module exists).")
parser.add_argument("--plot_off", dest="plot", action="store_false", help="Do not plot the profile. (Default if Matplotlib does not exist)")
parser.add_argument("-o", "--output", default=None, help="Output filename prefix")
parser.set_defaults(plot=True)
parser.set_defaults(fit_scale=True)
parser.set_defaults(fit_offset=False)
args = parser.parse_args()

if args.plot:
    #if plotting is enabled, try to import matplotlib
    #if import fails, set plotting to false
    try:
        import matplotlib.pyplot as plt
        from matplotlib import gridspec
    except ImportError as e:
        print("matplotlib import failed.")
        args.plot = False

def main():

    scriptname = os.path.basename(sys.argv[0])
    command = scriptname + ' ' + ' '.join(sys.argv[1:])

    if args.output is None:
        fname_nopath = os.path.basename(args.file)
        basename, ext = os.path.splitext(fname_nopath)
        output = basename
    else:
        output = args.output


    #read experimental data
    q, I, sigq, Ifit, file_dmax, isfit = saxs.loadProfile(args.file, units=args.units)
    Iq = np.vstack((q,I,sigq)).T
    Iq = Iq[~np.isnan(Iq).any(axis = 1)]
    #get rid of any data points equal to zero in the intensities or errors columns
    idx = np.where((Iq[:,1]!=0)&(Iq[:,2]!=0))
    Iq = Iq[idx]
    q = Iq[:,0]
    I = Iq[:,1]
    err = Iq[:,2]

    #if no experimental data given, create a new qgrid for interpolation
    if args.qfile is not None:
        #if qfile is given, this takes priority over qmax/nq options
        qc = np.genfromtxt(args.qfile, invalid_raise = False, usecols=(0,))
        qc = qc[~np.isnan(qc)]
    else:
        #let a user set a desired set of q values to be calculated
        #based on a given qmax and nq
        if args.qmax is not None:
            qmax = args.qmax
        else:
            qmax = np.max(q)
        if args.nq is not None:
            nq = args.nq
        else:
            nq = 501
        qc = np.linspace(0,qmax,nq)

    #interpolate Iq to desired qgrid
    I_interpolator = interpolate.interp1d(q,I,kind='cubic',fill_value='extrapolate')
    Ic = I_interpolator(qc)
    err_interpolator = interpolate.interp1d(q,err,kind='cubic',fill_value='extrapolate')
    errc = err_interpolator(qc)
    Iq_calc = np.vstack((qc,Ic,errc)).T

    qmax = np.min([Iq[:,0].max(),Iq_calc[:,0].max()])
    Iq = Iq[Iq[:,0]<=qmax]
    Iq_calc = Iq_calc[Iq_calc[:,0]<=qmax]

    np.savetxt(basename+'.regrid.dat', Iq_calc, delimiter=' ', fmt='%.5e'.encode('ascii'))

if __name__ == "__main__":
    main()





