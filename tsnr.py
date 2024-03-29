#!/usr/bin/env python

# Compute temperal SNR of a time series, with the option to remove low frequency temporal fluctuations
# and compute SFNR (signal fluctuation to noise ratio). Also perform Weisskoff analysis and calculate 
# the STD within ROIs.
# Require AFNI functions 3dTcat, 3dAutomask, 3dDetrend.

import os
import json
import nibabel as nb
import numpy as np
from scipy import ndimage
# disable X-display
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
#from nipype.interfaces import fsl

if __name__ == '__main__':

    import argparse

    arg_parser = argparse.ArgumentParser()
    arg_parser.description  = ('Calculate temporal SNR of a 3D+time nifti after removing components from voxel time series.\n\n')
    arg_parser.add_argument('infile', help='path to nifti file of the time series')
    arg_parser.add_argument('-o', '--outbase', default='', help='basename of the output files')
    arg_parser.add_argument('-d', '--discard_vol', type=int, default=3, help='number of volumes to discard from the beginning, default=3')
    arg_parser.add_argument('-f', '--mask_frac', type=float, default=0.4, help='clip level fraction for mask generation, default=0.4')
    arg_parser.add_argument('-p', '--detrend_polort', type=int, default=2, help='polynomials order for 3dDetrend, default=2')
    arg_parser.add_argument('-r', '--roi_size', type=int, default=21, help='length of square ROI in Weisskoft analysis, default=21')
    arg_parser.add_argument('--save_all_outputs', action='store_true', help='flag for saving all intermediate results')
    args = arg_parser.parse_args()

    basename = (os.path.basename(args.infile)).split('.')[0]
    outbase = args.outbase
    if outbase == '':
        outbase = basename
    tseries_name = outbase+'_tseries.nii.gz'
    detrend_name = outbase+'_detrend.nii.gz'
    mask_name = outbase+'_mask.nii.gz'
    tsnr_name = outbase+'_tsnr.nii.gz'
    tmean_name = outbase+'_tmean.nii.gz'
    tstd_name = outbase+'_tstd.nii.gz'
    nstd_name = outbase+'_nstd.nii.gz'
    sfnr_name = outbase+'_sfnr.nii.gz'

    # discard volumes, mask, detrend using AFNI functions.
    # 3dTcat removes the beginning non steady-state volumes; 3dAutomask generates a 3D mask; 3dDetrend removes a fitted polynomial from the time series signal of each voxel, the detrended the time series is used to calculate the signal fluctuation to noise ratio
    #os.system("3dTcat -prefix %s %s[%d..$]; 3dAutomask -prefix %s -clfrac %f %s; 3dDetrend -prefix %s -polort %d %s" 
    os.system(". /etc/afni/afni.sh; 3dTcat -prefix %s %s[%d..$]; 3dAutomask -prefix %s -clfrac %f %s; 3dDetrend -prefix %s -polort %d %s" 
              %(tseries_name, args.infile, args.discard_vol, 
                mask_name, args.mask_frac, tseries_name, 
                detrend_name, args.detrend_polort, tseries_name))

    ni = nb.load(tseries_name)
    pixdim = ni.get_header()['pixdim'][1:4]  # pixel size in mm
    tr = ni.get_header()['pixdim'][4]  # TR in seconds
    tseries = ni.get_data()
    noise = nb.load(detrend_name).get_data()
    mask  = nb.load(mask_name).get_data()
    tmean = np.multiply(np.mean(tseries, axis=3), mask)
    tstd  = np.multiply(np.std(tseries, axis=3), mask)
    nstd  = np.multiply(np.std(noise, axis=3), mask)
    tsnr  = np.nan_to_num(np.multiply(np.divide(tmean, tstd), mask))
    sfnr  = np.nan_to_num(np.multiply(np.divide(tmean, nstd), mask))
    
    # Weisskoff analysis, drift, mean SNR
    num_tpoints = noise.shape[3]
    center_of_mass_t = np.zeros((3, num_tpoints))
    center_of_mass_drift = np.zeros((3, num_tpoints))
    # calculate the center of mass drift in mm over the time series
    for t in range(num_tpoints):
        center_of_mass_t[:, t] = ndimage.measurements.center_of_mass(tseries[...,t])
        if t == 0:
            center_of_mass = list(int(s) for s in ndimage.measurements.center_of_mass(tseries[...,t]))
        else:
            center_of_mass_drift[:, t] = np.multiply(center_of_mass_t[:, t] - center_of_mass_t[:, 0], pixdim)
    # calculate the radius of decorrelation according to the Weisskoff analysis. Radius of correlation measures how much correlation there is among the adjacent voxels due to noise contamination. Smaller radius of correlation indicates less contamination
    roi_length = range(1, args.roi_size+1)
    roi_std_detrend = []
    for r in roi_length:
        roi = []
        for i in range(0,2):
            roi.append(range(center_of_mass[i]-r//2, center_of_mass[i]+r//2+np.mod(r,2)))
        roi_mask = np.zeros(noise.shape)
        roi_mask[np.meshgrid(roi[0],roi[1],[center_of_mass[2]],range(num_tpoints))] = 1
        #roi_std = np.std(tseries[np.where(roi_mask)].flatten())
        #roi_std_noise = np.std(np.sum(np.sum(np.multiply(noise[:,:,center_of_mass[2],:], roi_mask[:,:,center_of_mass[2],:]), axis=0), axis=0)*1.0/r/r)
        roi_mean = np.sum(np.sum(np.multiply(tseries[:,:,center_of_mass[2],:], roi_mask[:,:,center_of_mass[2],:]), axis=0), axis=0)*1.0/r/r
        coeff = np.polyfit(range(num_tpoints), roi_mean, 2)
        poly = np.poly1d(coeff)
        res = roi_mean - poly(range(num_tpoints))
        roi_std_detrend.append(np.std(res))
    rdc = roi_std_detrend[0] / roi_std_detrend[args.roi_size-1]
    # mean signal intensity within ROI over the time series. Temporal variation within 0.05% is preferred
    roi_signal_mean = roi_mean 
    roi_signal_mean_fitted = poly(range(num_tpoints))
    sfnr_center = np.mean(sfnr[np.where(roi_mask[:,:,:,0])])
    sfnr_edge = np.percentile(sfnr[:,:,center_of_mass[2]][np.where(mask[:,:,center_of_mass[2]])], 95)
    
    # save data
    data = {'roi_size': args.roi_size, 
            'roi_std': ['%.2f' % x for x in roi_std_detrend], 
            'radius_decorrelation': '%.1f' % rdc,
            'roi_signal_mean': ['%.2f' % x for x in roi_signal_mean],
            'roi_signal_mean_fitted': ['%.2f' % x for x in roi_signal_mean_fitted],
            'center_of_mass_x': ['%.4f' % x for x in center_of_mass_t[0, :]],
            'center_of_mass_y': ['%.4f' % x for x in center_of_mass_t[1, :]],
            'center_of_mass_z': ['%.4f' % x for x in center_of_mass_t[2, :]],
            'center_of_mass_drift_x': ['%.4f' % x for x in center_of_mass_drift[0, :]],
            'center_of_mass_drift_y': ['%.4f' % x for x in center_of_mass_drift[1, :]],
            'center_of_mass_drift_z': ['%.4f' % x for x in center_of_mass_drift[2, :]],
            'sfnr_center': '%.2f' % sfnr_center,
            'sfnr_edge': '%.2f' % sfnr_edge}
    with open(outbase+'_results.json','w') as fp:
        json.dump(data, fp, indent=2, sort_keys=True)

    # plot Weisskoff analysis result
    plt.plot(range(1, args.roi_size+1), roi_std_detrend, '-x', range(1, args.roi_size+1), np.divide(roi_std_detrend[0], range(1, args.roi_size+1)), 'r-x')
    plt.axhline(roi_std_detrend[args.roi_size-1], color='k', linestyle='--', linewidth=0.5)
    plt.axvline(rdc, color='k', linestyle='--', linewidth=0.5) 
    plt.xscale('log')
    plt.yscale('log')
    plt.xlim(0, args.roi_size+1)
    ymin = 0.1 if roi_std_detrend[0]/args.roi_size < 1 else 1
    plt.ylim(ymin, roi_std_detrend[0]*2)
    plt.xticks([1, 10, (args.roi_size//10)*10], [1, 10, (args.roi_size//10)*10])
    plt.yticks([0.1, 1, 10] if ymin==0.1 else [1, 10], [0.1, 1, 10] if ymin==0.1 else [1, 10])
    plt.xlabel('ROI length (N)')
    plt.ylabel('Standard deviation within ROI')
    plt.text(1.5, 1.5*roi_std_detrend[0], 'radius of decorrelation = %.1f' %(rdc))
    plt.savefig(outbase+'_rdc.png', bbox_inches='tight')
    plt.close()

    # plot ROI mean signal of the time series
    plt.plot((np.arange(num_tpoints) + args.discard_vol + 1) * tr, roi_signal_mean/np.max(roi_signal_mean), label='mean signal')
    plt.plot((np.arange(num_tpoints) + args.discard_vol + 1) * tr, roi_signal_mean_fitted/np.max(roi_signal_mean), label='fitted mean signal')
    plt.legend(loc='upper right')
    plt.ylabel('signal intensity (normalized)'); plt.xlabel('time (s)'); plt.xlim(0, (num_tpoints+1)*tr)
    plt.savefig(outbase+'_mean_signal.png', bbox_inches='tight')
    plt.close()

    # plot drift of center of mass
    plt.plot((np.arange(num_tpoints-1) + args.discard_vol + 2) * tr, center_of_mass_drift[0, 1:], label='x')
    plt.plot((np.arange(num_tpoints-1) + args.discard_vol + 2) * tr, center_of_mass_drift[1, 1:], label='y')
    plt.plot((np.arange(num_tpoints-1) + args.discard_vol + 2) * tr, center_of_mass_drift[2, 1:], label='z')
    plt.legend(loc='upper right')
    plt.ylim(-np.ceil(np.max(np.abs(center_of_mass_drift)) * 10) / 10.0, np.ceil(np.max(np.abs(center_of_mass_drift)) * 10) / 10.0)
    plt.ylabel('drift of center of mass (mm)'); plt.xlabel('time (s)'); plt.xlim(0, (num_tpoints+1)*tr)
    plt.savefig(outbase+'_cm_drift.png', bbox_inches='tight')
    plt.close()

    ni_sfnr  = nb.Nifti1Image(sfnr,  ni.get_affine())
    nb.save(ni_sfnr,  sfnr_name)
    if args.save_all_outputs:
        ni_tmean = nb.Nifti1Image(tmean, ni.get_affine())
        ni_nstd  = nb.Nifti1Image(nstd,  ni.get_affine())
        ni_tstd  = nb.Nifti1Image(tstd,  ni.get_affine())
        ni_tsnr  = nb.Nifti1Image(tsnr,  ni.get_affine())
        nb.save(ni_tmean, tmean_name)
        nb.save(ni_nstd,  nstd_name)
        nb.save(ni_tstd,  tstd_name)
        nb.save(ni_tsnr,  tsnr_name)
    else:
        os.remove(tseries_name)
        os.remove(detrend_name)
        os.remove(mask_name)

