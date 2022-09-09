# tSNR
Calculates the temporal SNR (tSNR) and signal fluctuation to noise ratio (SFNR) of a 4D NIFTI containing time series images. Scripts in this repository are for building a processing gear in Flywheel. 
- Gear input:
    - 4D NIFTI
- Gear configuration options:
    - Mask threshold
    - Number of discarded volumes
    - Size of central ROI
- Gear outputs:
    - tSNR map ``*_tsnr.nii.gz``, SFNR map ``*_sfnr.nii.gz``
    - Plot of the temporal drift of mean signal within ROI ``*_mean_signal.png``, plot of the temporal drift of center of mass ``*_cm_drift.png``, plot of Weisskoff analysis (radius of decorrelation) ``*_rdc.png``
    - JSON file containing statistic results e.g. mean tSNR, SFNR in ROI

The script ``tsnr.py`` can also be executed seperately to generate tSNR maps on 4D NIFTIs containing time series images:

``python tsnr.py [-o OUTBASE] [-d DISCARD_VOL] [-f BET_FRAC] [-r ROI_SIZE] infile``

Dependencies include AFNI, NumPy, SciPy, NiBabel.

Reference:  Friedman and Glover, 2006, Report on a multicenter fMRI quality assurance protocol.
