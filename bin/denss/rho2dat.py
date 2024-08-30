#!/usr/bin/env python
#
#    denss.rho2dat.py
#    A tool for calculating simple scattering profiles
#    from MRC formatted electron density maps
#
#    Part of the DENSS package
#    DENSS: DENsity from Solution Scattering
#    A tool for calculating an electron density map from solution scattering data
#
#    Tested using Anaconda / Python 2.7
#
#    Author: Thomas D. Grant
#    Email:  <tgrant@hwi.buffalo.edu>
#    Copyright 2018 The Research Foundation for SUNY
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
from scipy import ndimage
from saxstats._version import __version__
import saxstats.saxstats as saxs

parser = argparse.ArgumentParser(description="A tool for calculating simple scattering profiles from MRC formatted electron density maps", formatter_class=argparse.RawTextHelpFormatter)
parser.add_argument("--version", action="version",version="%(prog)s v{version}".format(version=__version__))
parser.add_argument("-f", "--file", type=str, help="Electron density filename (.mrc)")
parser.add_argument("-dq", "--dq", default=None, type=float, help="Desired q spacing (pads map with zeros)")
parser.add_argument("-n", "--n", default=None, type=int, help="Desired number of samples (overrides --dq option)")
parser.add_argument("--ns", default=1, type=int, help="Sampling fraction (i.e. every ns'th element, must be integer, allows for reduced sampling for speed up at cost of resolution (i.e. qmax will be smaller))")
parser.add_argument("-t","--threshold", default=None, type=float, help="Minimum density threshold (sets lesser values to zero).")
parser.add_argument("--plot_on", dest="plot", action="store_true", help="Plot the profile (requires Matplotlib, default if module exists).")
parser.add_argument("--plot_off", dest="plot", action="store_false", help="Do not plot the profile. (Default if Matplotlib does not exist)")
parser.add_argument("--save_mrc", action="store_true", help="Save the modified MRC file.")
parser.add_argument("-o", "--output", default=None, help="Output filename prefix")
parser.set_defaults(plot=True)
args = parser.parse_args()

if args.plot:
    #if plotting is enabled, try to import matplotlib
    #if import fails, set plotting to false
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        args.plot = False


def main():

    if args.output is None:
        fname_nopath = os.path.basename(args.file)
        basename, ext = os.path.splitext(fname_nopath)
        output = basename + '_rho'
    else:
        output = args.output

    rho, side = saxs.read_mrc(args.file)
    if rho.shape[0]%2==1:
        rho = rho[:-1,:-1,:-1]
    #if nstmp%2==1: args.ns+=1
    rho = np.copy(rho[::args.ns, ::args.ns, ::args.ns])
    if args.threshold is not None:
        rho[np.abs(rho)<=args.threshold] = 0
    halfside = side/2
    nx, ny, nz = rho.shape[0], rho.shape[1], rho.shape[2]
    n = nx
    voxel = side/n
    #want n to be even for speed/memory optimization with the FFT, ideally a power of 2, but wont enforce that
    #store n for later use if needed
    n_orig = n
    dx = side/n
    dV = dx**3
    V = side**3
    x_ = np.linspace(-halfside,halfside,n)
    x,y,z = np.meshgrid(x_,x_,x_,indexing='ij')
    df = 1/side
    qx_ = np.fft.fftfreq(x_.size)*n*df*2*np.pi
    qz_ = np.fft.rfftfreq(x_.size)*n*df*2*np.pi
    qx, qy, qz = np.meshgrid(qx_,qx_,qx_,indexing='ij')
    qr = np.sqrt(qx**2+qy**2+qz**2)
    qmax = np.max(qr)
    qstep = np.min(qr[qr>0]) - 1e-8
    nbins = int(qmax/qstep)
    qbins = np.linspace(0,nbins*qstep,nbins+1)
    #create an array labeling each voxel according to which qbin it belongs
    qbin_labels = np.searchsorted(qbins,qr,"right")
    qbin_labels -= 1
    qblravel = qbin_labels.ravel()
    xcount = np.bincount(qblravel)
    #create modified qbins and put qbins in center of bin rather than at left edge of bin.
    qbinsc = saxs.mybinmean(qr.ravel(), qblravel, xcount)

    #calculate scattering profile from density
    F = saxs.myfftn(rho)
    F[F.real==0] = 1e-16
    I3D = saxs.abs2(F)
    Imean = saxs.mybinmean(I3D.ravel(), qblravel, xcount=xcount)

    if args.plot: 
        qmax_to_use = np.max(qx_)
        qbinsc_to_use_pre = qbinsc[qbinsc<qmax_to_use]
        Imean_to_use_pre = Imean[qbinsc<qmax_to_use]
        plt.plot(qbinsc_to_use_pre, Imean_to_use_pre, '.-', label='Default dq = %.4f' % (2*np.pi/side))
    print('Default dq = %.4f' % (2*np.pi/side))

    if args.dq is not None or args.n is not None:

        #padded to get desired dq value (or near it)
        if args.n is not None:
            if args.n < n:
                print("Requested number of samples must be greater than or equal to the original map (which is %d)" % n)
                print("Resetting desired N to current N...")
            else:
                n = args.n
        else:
            current_dq = 2*np.pi/side
            desired_dq = args.dq
            if desired_dq > current_dq:
                print("Requested dq must be smaller than dq calculated from map (which is %f)" % current_dq)
                print("Resetting desired dq to current dq...")
                desired_dq = current_dq
            #what side would give us desired dq?
            desired_side = 2*np.pi/desired_dq
            #what n, given the existing voxel size, would give us closest to desired_side
            desired_n = desired_side/voxel
            n = int(desired_n)
            if n%2==1: n+=1
        side = voxel*n
        halfside = side/2
        dx = side/n
        dV = dx**3
        V = side**3
        x_ = np.linspace(-halfside,halfside,n)
        x,y,z = np.meshgrid(x_,x_,x_,indexing='ij')
        df = 1/side
        print(n, 2*np.pi*df)
        qx_ = np.fft.fftfreq(x_.size)*n*df*2*np.pi
        qx, qy, qz = np.meshgrid(qx_,qx_,qx_,indexing='ij')
        qr = np.sqrt(qx**2+qy**2+qz**2)
        qmax = np.max(qr)
        qstep = np.min(qr[qr>0]) - 1e-8
        nbins = int(qmax/qstep)
        qbins = np.linspace(0,nbins*qstep,nbins+1)
        #create modified qbins and put qbins in center of bin rather than at left edge of bin.
        # qbinsc = np.copy(qbins)
        # qbinsc[1:] += qstep/2.

        #create an array labeling each voxel according to which qbin it belongs
        qbin_labels = np.searchsorted(qbins,qr,"right")
        qbin_labels -= 1
        qblravel = qbin_labels.ravel()
        xcount = np.bincount(qblravel)
        qbinsc = saxs.mybinmean(qr.ravel(), qblravel, xcount)
        rho_pad = np.zeros((n,n,n))
        a = n//2-n_orig//2
        b = n//2+n_orig//2
        rho_pad[a:b,a:b,a:b] = rho
        rho = np.copy(rho_pad)

    F = saxs.myfftn(rho)
    I3D = saxs.abs2(F)
    Imean = saxs.mybinmean(I3D.ravel(), qblravel, xcount=xcount)

    qmax_to_use = np.max(qx_)
    print("qmax to use: %f" % qmax_to_use)
    qbinsc_to_use = qbinsc[qbinsc<qmax_to_use]
    Imean_to_use = Imean[qbinsc<qmax_to_use]

    qbinsc = np.copy(qbinsc_to_use)
    Imean = np.copy(Imean_to_use)

    Iq = np.vstack((qbinsc, Imean, Imean*0+Imean[0]*.03)).T

    np.savetxt(output+'.dat', Iq, delimiter=' ', fmt='% .16e')

    if args.save_mrc:
        saxs.write_mrc(rho, side, output+'_mod.mrc')

    if args.plot:
        print('Actual dq = %.4f' % (2*np.pi/side))
        plt.plot(qbinsc_to_use, Imean_to_use,'-',label='Actual dq = %.4f' % (2*np.pi/side))
        plt.semilogy()
        plt.legend()
        plt.show()

if __name__ == "__main__":
    main()




