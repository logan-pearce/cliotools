from astropy.io import fits
import numpy as np
import os
from scipy import ndimage
import image_registration

############################ Finding stars in CLIO images ################################

def daostarfinder(scienceimage, x, y, boxsize = 100, threshold = 1e4, fwhm = 10):
    """Find the subpixel location of a single star in a single clio BDI image.
       Written by Logan A. Pearce, 2020

       Parameters:
       -----------
       image : 2d array
           boxsize by boxsize substamp image of a reference psf for cross correlation
       scienceimage_filename : string
           path to science image
       x, y : int
           integer pixel locations of star
       boxsize : int
           size of box to draw around star psfs for DAOStarFinder
       threshold : int
           threshold keyword for StarFinder
       fwhm : int
           fwhm keyword for StarFinder
           
       Returns:
       --------
       x_subpix, y_subpix : flt
           subpixel location of star
    """
    from photutils import DAOStarFinder
    image2 = scienceimage
    # The settings fwhm = 10.0 seems to be good for clio
    # Define box around source B:
    ymin, ymax = y-boxsize, y+boxsize
    xmin, xmax = x-boxsize, x+boxsize
    # Correct for sources near image edge:
    if ymin < 0:
        ymin = 0
    if ymax > scienceimage.shape[0]:
        ymax = scienceimage.shape[0]
    if xmin < 0:
        xmin = 0
    if xmax > scienceimage.shape[1]:
        xmax = scienceimage.shape[1]
    # Use DAOStarFinder to find subpixel locations:
    # If the threshold is too high and it can't find a point source, lower the threshold
    # until ~ 5e2, then declare failure.
    try:
        #print('threshold =',threshold)
        daofind = DAOStarFinder(fwhm=fwhm, threshold=threshold) 
        sources = daofind(image2[np.int_(ymin):np.int_(ymax),\
                                     np.int_(xmin):np.int_(xmax)])
        x_subpix, y_subpix = (xmin+sources['xcentroid'])[0], (ymin+sources['ycentroid'])[0]
        # If it finds too many sources, keep uping the search threshold until there is only one:
        while len(sources) > 1:
            threshold += 500
            daofind = DAOStarFinder(fwhm=10.0, threshold=threshold) 
            sources = daofind(image2[np.int_(y-boxsize):np.int_(y+boxsize),np.int_(x-boxsize):np.int_(x+boxsize)])
            x_subpix, y_subpix = (xmin+sources['xcentroid'])[0], (ymin+sources['ycentroid'])[0]
    except:
        try:
            threshold=1e3
            #print('threshold =',threshold)
            daofind = DAOStarFinder(fwhm=fwhm, threshold=threshold) 
            sources = daofind(image2[np.int_(ymin):np.int_(ymax),\
                                         np.int_(xmin):np.int_(xmax)])
            x_subpix, y_subpix = (xmin+sources['xcentroid'])[0], (ymin+sources['ycentroid'])[0]
            while len(sources) > 1:
                threshold += 250
                daofind = DAOStarFinder(fwhm=fwhm, threshold=threshold) 
                sources = daofind(image2[np.int_(y-boxsize):np.int_(y+boxsize),np.int_(x-boxsize):np.int_(x+boxsize)])
                x_subpix, y_subpix = (xmin+sources['xcentroid'])[0], (ymin+sources['ycentroid'])[0]
        except:
            try:
                threshold=5e2
                #print('threshold =',threshold)
                daofind = DAOStarFinder(fwhm=fwhm, threshold=threshold) 
                sources = daofind(image2[np.int_(ymin):np.int_(ymax),\
                                             np.int_(xmin):np.int_(xmax)])
                x_subpix, y_subpix = (xmin+sources['xcentroid'])[0], (ymin+sources['ycentroid'])[0]
                while len(sources) > 1:
                    threshold += 250
                    daofind = DAOStarFinder(fwhm=fwhm, threshold=threshold) 
                    sources = daofind(image2[np.int_(y-boxsize):np.int_(y+boxsize),np.int_(x-boxsize):np.int_(x+boxsize)])
                    x_subpix, y_subpix = (xmin+sources['xcentroid'])[0], (ymin+sources['ycentroid'])[0]
            except:
                print("Failed to find all stars.")
                x_subpix, y_subpix = np.nan, np.nan

    return x_subpix, y_subpix

def findstars(imstamp, scienceimage_filename, nstars, \
              boxsize = 100, threshold = 1e4, fwhm = 10, radius = 20):
    """Find the subpixel location of all stars in a single clio BDI image using DAOStarFinder 
       (https://photutils.readthedocs.io/en/stable/api/photutils.detection.DAOStarFinder.html).
       Written by Logan A. Pearce, 2020
       Dependencies: numpy, astropy, scipy, photutils

       Parameters:
       -----------
       imstamp : 2d array
           boxsizex by boxsizey substamp image of a reference psf for cross correlation
       scienceimage_filename : string
           path to science image
       nstars : int
           number of stars in the image.
       boxsize : int
           size of box to draw around star psfs for DAOStarFinder
       threshold : int
           threshold keyword for DAO StarFinder
       fwhm : int
           fwhm keyword for DAO StarFinder
       radius : int
           radius to use when masking stars in image
           
       Returns:
       --------
       x_subpix, y_subpix : arr,flt
           1 x nstars array of subpixel x location and y location of stars
    """
    from scipy import signal
    from photutils import DAOStarFinder
    
    # Open science target image:
    image = fits.getdata(scienceimage_filename)
    # If image is a cube, take the first image:
    if len(image.shape) == 3:
        image = image[0]
    # Median filter to smooth image:
    image = ndimage.median_filter(image, 3)
    # Use cross-correlation to find int(y,x) of star A (brightest star) in image:
    corr = signal.correlate2d(image, imstamp, boundary='symm', mode='same')
    # Find the location of the brightest star in the image:
    y, x = np.unravel_index(np.argmax(corr), corr.shape)
    # Make container to hold results:
    x_subpix, y_subpix = np.array([]), np.array([])
    # Make a copy of the correlation image to mask:
    corr_masked = corr.copy()
    image_masked = image.copy()
    # For each star in the image:
    for i in range(nstars):
        # Use DAO Star Finder to find the subpixel location of the star at that location:
        xs, ys = daostarfinder(image_masked, x, y, boxsize = boxsize, threshold = threshold, fwhm = fwhm)
        x_subpix, y_subpix = np.append(x_subpix, xs), np.append(y_subpix, ys)
        # Make a mask around that star on the cross-correlation image:
        # Make a meshgrid of the image centered at the last found star:
        xx,yy = np.meshgrid(np.arange(image.shape[1])-x_subpix[i],np.arange(image.shape[0])-y_subpix[i])
        # Make an array of the distances of each pixel from that center:
        rA=np.hypot(xx,yy)
        # Mask wherever that distance is less than the set radius and
        # set those pixels to zero:
        corr_masked[np.where((rA < radius))] = 0
        image_masked[np.where((rA < radius))] = 0
        # Now find the new highest correlation which should be the next star:
        y, x = np.unravel_index(np.argmax(corr_masked), corr.shape)
        # Repeat until all stars are found.

    return x_subpix, y_subpix

def findstars_in_dataset(dataset_path, nstars, xca, yca, corrboxsizex = 40, corrboxsizey = 40, boxsize = 100, skip_list = False, \
                         append_file = False, threshold = 1e4, radius = 20, fwhm = 10):
    """Find the subpixel location of stars A and B in a clio BDI dataset.
       Written by Logan A. Pearce, 2020
       Dependencies: numpy, astropy, scipy, photutils

       Parameters:
       -----------
       dataset_path : string
           path to science images including image prefixes and underscores.  
           ex: An image set of target BDI0933 with filenames of the form BDI0933__00xxx.fit
               would take as input a path string of 'BDI0933/BDI0933__'
       xca, yca : int
           integer pixel locations of a star in the first image of the dataset, rough guess 
       corrrboxsize : int
           size of box to draw around star psfs for imstamp and cross correlation
       boxsize : int
           size of box to draw around star psfs for DAOStarFinder
       skip_list : bool
           By default script will make a list of all "skysub" images in given directory.
           Set to True if a list of paths to science files has already been made.  List
           must be named "list".  
        append_file : bool
            Set to True to append to an existing locations file, False to make a new file or 
            overwrite an old one.  Defautl = False.
        threshold : flt
            threshold for finding stars using DAOStarFinder

       Returns:
       --------
       writes subpixel location of stars to file called 'StarLocations' in order:
           image_filename   x   y   x   y   ...ect. for all requested stars.
    """
    from scipy import ndimage
    from cliotools.pcaskysub import update_progress
    # Supress warnings when failing to find point sources
    import warnings
    warnings.filterwarnings("ignore")
    # Make a file to store results:
    newfile = dataset_path.split('/')[0]+'/ABLocations'
    
    if append_file == False:
        string = '#     '
        for i in range(nstars):
            string += 'xc'+str(i+1) + '     ' + 'yc'+str(i+1)  + '     ' 
        string += "\n"
        k = open(newfile, 'w')
        k.write(string)
        k.close()
    
    # Make a list of all images in dataset:
    if skip_list == False:
        os.system('ls '+dataset_path+'0*_skysub.fit > list')
    with open('list') as f:
        ims = f.read().splitlines()
    # Open initial image in dataset:
    image = fits.getdata(ims[0])
    if len(image.shape) == 3:
        image = image[0]
    # Apply median filter to smooth bad pixels:
    image = ndimage.median_filter(image, 3)
    # Create referance stamp from initial image of A:
    imstamp = np.copy(image[np.int_(yca-corrboxsizey):np.int_(yca+corrboxsizey),np.int_(xca-corrboxsizex):np.int_(xca+corrboxsizex)])
    
    count = 0
    for im in ims:
        # For each image in the dataset, find subpixel location of stars:
        x_subpix, y_subpix = findstars(imstamp, im, nstars, \
                                                           boxsize = boxsize, threshold = threshold, \
                                                           radius = radius, fwhm = fwhm)
        if any(np.isnan(x_subpix)) or any(np.isnan(y_subpix)):
            # If any of the stars were failed to find, mark this entry with a comment:
            string = '# '+ im + ' '
        else:
            string = im + ' '
        for i in range(nstars):
            string += str(x_subpix[i]) + '     ' + str(y_subpix[i])  + '     ' 
        string += "\n"

        k = open(newfile, 'a')
        k.write(string)
        k.close()
        
        count+=1
        update_progress(count,len(ims))
    print('Done')
    os.system('rm list')
    os.system("say 'done'")

################################ prepare images for KLIP ##################################################

def rotate_clio(image, imhdr, **kwargs):
    """Rotate CLIO image to north up east left.
       Written by Logan A. Pearce, 2020
       
       Dependencies: scipy

       Parameters:
       -----------
       image : 2d array
           2d image array
       imhdr : fits header object
           header for image to be rotated
       kwargs : for scipy.ndimage
           
       Returns:
       --------
       imrot : 2d arr 
           rotated image with north up east left
    """
    
    NORTH_CLIO = -1.80
    derot = imhdr['ROTOFF'] - 180. + NORTH_CLIO
    imrot = ndimage.rotate(image, derot, **kwargs)
    return imrot

def ab_stack_shift(k, boxsize = 20, path_prefix=''):
    """Prepare stacks for BDI/ADI by stacking and subpixel aligning image 
       postage stamps of star A and star B.
       Written by Logan A. Pearce, 2020
       
       Dependencies: astropy, image_registration, scipy

       Parameters:
       -----------
       k : Pandas array
           Pandas array made from the output of bditools.findstars_in_dataset.  
           Assumes column names are ['filename', 'xca','yca', 'xcb', 'ycb']
       boxsize : int
           size of box to draw around star psfs for DAOStarFinder
       path_prefix : int
           string to put in front of filenames in input file in case the relative
           location of files has changed
           
       Returns:
       --------
       astamp, bstamp : 3d arr 
           stack of aligned psf's of star A and B for BDI.
    """
    import warnings
    warnings.filterwarnings("ignore")
    
    # Open first image in dataset:
    i = 0
    image = fits.getdata(path_prefix+k['filename'][i])
    # Make stamps:
    if len(image.shape) == 2:
        first_a = fits.getdata(path_prefix+k['filename'][i])[np.int_(k['yca'][i]-boxsize):np.int_(k['yca'][i]+boxsize),\
                                                                 np.int_(k['xca'][i]-boxsize):np.int_(k['xca'][i]+boxsize)]
        first_b = fits.getdata(path_prefix+k['filename'][i])[np.int_(k['ycb'][i]-boxsize):np.int_(k['ycb'][i]+boxsize),\
                                                                 np.int_(k['xcb'][i]-boxsize):np.int_(k['xcb'][i]+boxsize)]
    elif len(image.shape) == 3:
        first_a = fits.getdata(path_prefix+k['filename'][i])[:,np.int_(k['yca'][i]-boxsize):np.int_(k['yca'][i]+boxsize),\
                                                                 np.int_(k['xca'][i]-boxsize):np.int_(k['xca'][i]+boxsize)]
        first_b = fits.getdata(path_prefix+k['filename'][i])[:,np.int_(k['ycb'][i]-boxsize):np.int_(k['ycb'][i]+boxsize),\
                                                                 np.int_(k['xcb'][i]-boxsize):np.int_(k['xcb'][i]+boxsize)]
    # create empty containers:
    if len(image.shape) == 2:
        astamp = np.zeros([len(k),*first_a.shape])
        bstamp = np.zeros([len(k),*first_b.shape])
    elif len(image.shape) == 3:
        astamp = np.zeros([len(k)*image.shape[0],first_a.shape[1],first_a.shape[2]])
        bstamp = np.zeros([len(k)*image.shape[0],first_b.shape[1],first_b.shape[2]])
    
    # For each subsequent image, make the imagestamp for a and b, and 
    # align them with the first image, and add to stack:
    if len(image.shape) == 2:
        # place first a at bottom of stack:
        i = 0
        astamp[i,:,:] = first_a
        bstamp[i,:,:] = first_b
        for i in range(1,len(k)):
        # make stamp:
            a = fits.getdata(path_prefix+k['filename'][i])[np.int_(k['yca'][i]-boxsize):np.int_(k['yca'][i]+boxsize),\
                   np.int_(k['xca'][i]-boxsize):np.int_(k['xca'][i]+boxsize)]
            # place in container:
            try:
                astamp[i,:,:] = a
                # measure offset from the first image stamp:
                dx,dy,edx,edy = image_registration.chi2_shift(astamp[0,:,:], astamp[i,:,:], upsample_factor='auto')
                # shift new stamp by that amount:
                astamp[i,:,:] = ndimage.shift(astamp[i,:,:], [-dy,-dx], output=None, order=3, mode='constant', \
                                              cval=0.0, prefilter=True)
            except:
                print('ab_stack_shift: Oops! the box is too big and one star is too close to an edge. I cut it off at i=',i)
                astamp = astamp[:i,:,:]
                bstamp = bstamp[:i,:,:]
                return astamp, bstamp
            # repeat for b:
            b = fits.getdata(path_prefix+k['filename'][i])[np.int_(k['ycb'][i]-boxsize):np.int_(k['ycb'][i]+boxsize),\
                   np.int_(k['xcb'][i]-boxsize):np.int_(k['xcb'][i]+boxsize)]
            try:
                bstamp[i,:,:] = b
                # measure offset from the first image stamp:
                dx,dy,edx,edy = image_registration.chi2_shift(bstamp[0,:,:], bstamp[i,:,:], upsample_factor='auto')
                # shift new stamp by that amount:
                bstamp[i,:,:] = ndimage.shift(bstamp[i,:,:], [-dy,-dx], output=None, order=3, mode='constant', \
                              cval=0.0, prefilter=True)
            except:
                print('ab_stack_shift: Oops! the box is too big and one star is too close to an edge. I cut it off at i=',i)
                astamp = astamp[:i,:,:]
                bstamp = bstamp[:i,:,:]
                return astamp, bstamp
    if len(image.shape) == 3:
        count = first_a.shape[0]
        astamp[0:count,:,:] = first_a
        bstamp[0:count,:,:] = first_b
        for i in range(1,len(k)):
            try:
                a = fits.getdata(path_prefix+k['filename'][i])[:,np.int_(k['yca'][i]-boxsize):np.int_(k['yca'][i]+boxsize),\
                                                                   np.int_(k['xca'][i]-boxsize):np.int_(k['xca'][i]+boxsize)]
                astamp[count:count+a.shape[0],:,:] = a
                b = fits.getdata(path_prefix+k['filename'][i])[:,np.int_(k['ycb'][i]-boxsize):np.int_(k['ycb'][i]+boxsize),\
                                                                   np.int_(k['xcb'][i]-boxsize):np.int_(k['xcb'][i]+boxsize)]
                bstamp[count:count+b.shape[0],:,:] = b
                   
                for j in range(count,count+a.shape[0]):
                    dx,dy,edx,edy = image_registration.chi2_shift(astamp[0,:,:], astamp[j,:,:], upsample_factor='auto')
                    astamp[j,:,:] = ndimage.shift(astamp[j,:,:], [-dy,-dx], output=None, order=3, mode='constant', cval=0.0, \
                                                              prefilter=True)
                    dx,dy,edx,edy = image_registration.chi2_shift(bstamp[0,:,:], bstamp[j,:,:], upsample_factor='auto')
                    bstamp[j,:,:] = ndimage.shift(bstamp[j,:,:], [-dy,-dx], output=None, order=3, mode='constant', cval=0.0, \
                                                              prefilter=True)
                count += a.shape[0]
            except:
                print('ab_stack_shift: Oops! the box is too big and one star is too close to an edge. I cut it off at i=',count)
                astamp = astamp[:count,:,:]
                bstamp = bstamp[:count,:,:]
                return astamp, bstamp
            
    return astamp, bstamp

def psfsub_cube_header(dataset, K_klip, star, shape, stampshape):
    """ Make a header for writing psf sub BDI KLIP cubes to fits files
        in the subtract_cubes function
    """
    import time
    header = fits.Header()
    header['COMMENT'] = '         ************************************'
    header['COMMENT'] = '         **  BDI KLIP PSF subtraction cube **'
    header['COMMENT'] = '         ************************************'
    header['COMMENT'] = 'Postagestamp cube of PSF subtraction using KLIP algorithm and BDI method'
    try:
        header['NAXIS1'] = str(shape[1])
        header['NAXIS2'] = str(shape[2])
        header['NAXIS3'] = str(shape[0])
    except:
        header['NAXIS1'] = str(shape[0])
        header['NAXIS2'] = str(shape[1])
        header['NAXIS3'] = str(1)
    header['DATE'] = time.strftime("%m/%d/%Y")
    header['DATASET'] = dataset
    header['STAR'] = str(star)
    header['BASIS MODE CUTOFFS'] = str(K_klip)
    header['STAMPAXIS'] = str(stampshape)
    header['COMMENT'] = 'by Logan A Pearce'
    return header

############################# KLIP math #############################################################

def psf_subtract(scienceimage, ref_psfs, K_klip, covariances = None, use_basis = False, basis = None, return_basis = False, return_cov = False):
    """Build an estimator for the psf of a BDI science target image from a cube of reference psfs 
       (use the ab_stack_shift function).  Follows steps of Soummer+ 2012 sec 2.2
       
       Written by Logan A. Pearce, 2020
       Heavily influenced by the lovely coding over at PyKLIP (https://pyklip.readthedocs.io/en/latest/)
       
       Dependencies: numpy, image_registration, scipy

       Parameters:
       -----------
       scienceimage : 2d array
           science target image of shape mxn
       ref_psfs : 3d array
           reference psfs array of shape Nxmxn where N = number of reference psfs
       K_klip : int or arr
           Number of basis modes desired to use.  Can be integer or array of len b
       covariances : arr
           covariance matrix for ref psfs can be passed as an argument to avoid needing
           to calculate it
       basis : 3d arr
           psf basis modes (Z of Soummer 2.2.2) for star A or B can be passed as an argument to avoid needing
           to calculate it
       return_estimator : bool
           if set to True, return the estimated psf(s) used to subtract from the science target
           
       Returns:
       --------
       outputimage : bxmxn arr
           psf subtracted image
       Z : Nxp arr
           psf model basis modes (if return_basis = True)
       cov : NxN arr
           return the computed covariance matrix is return_cov = True. So it can be used in future
           calcs without having to recalculate

    """
    # Shift science image to line up with reference psfs (aligned during the cubing step):
    dx,dy,edx,edy = image_registration.chi2_shift(np.sum(ref_psfs,axis=0), scienceimage, upsample_factor='auto')
    scienceimage = ndimage.shift(scienceimage, [-dy,-dx], output=None, order=4, mode='constant', \
                              cval=0.0, prefilter=True)
    # Start KLIP math:
    from scipy.linalg import eigh
    
    # Soummer 2012 2.2.1:
    ### Prepare science target:
    shape=scienceimage.shape
    p = shape[0]*shape[1]
    # Reshape science target into 1xp array:
    T_reshape = np.reshape(scienceimage,(p))
    # Subtract mean from science image:
    T_meansub = T_reshape - np.nanmean(T_reshape)
    # Make K_klip number of copies of science image
    # to use fast vectorized math:
    T_meansub = np.tile(T_meansub, (np.max(K_klip), 1))
    
    # KL Basis modes:
    if use_basis is True:
        Z = basis
    else:
        # Build basis modes:
        ### Prepare ref psfs:
        refshape=ref_psfs.shape
        N = refshape[0]
        if N < np.min(K_klip):
            print("Oops! All of your requested basis modes are more than there are ref psfs.")
            print("Setting K_klip to number of ref psfs.  K_klip = ",N)
            K_klip = N
        if N < np.max(K_klip):
            print("Oops! You've requested more basis modes than there are ref psfs.")
            print("Setting where K_klip > N to number of ref psfs.")
            K_klip[np.where(K_klip > N)] = N
            print("K_klip = ",K_klip)
        K_klip = np.clip(K_klip, 0, N)
        R = np.reshape(ref_psfs,(N,p))
        # Compute the mean pixel value of each reference image:
        immean = np.nanmean(R, axis=1)
        # subtract mean:
        R_meansub = R - immean[:, None] #<- makes an empty first dimension to make
        # the vector math work out
    
        # Soummer 2.2.2:
        # compute covariance matrix of reference images:
        if covariances is None:
            cov = np.cov(R_meansub)
        else:
            cov = covariances
        # compute eigenvalues (lambda) and corresponding eigenvectors (c)
        # of covariance matrix.  Compute only the eigenvalues/vectors up to the
        # desired number of bases K_klip.
        lamb,c = eigh(cov, eigvals = (N-np.max(K_klip),N-1))
        # np.cov returns eigenvalues/vectors in increasing order, so
        # we need to reverse the order:
        index = np.flip(np.argsort(lamb))
        # sort corresponding eigenvalues:
        lamb = lamb[index]
        # check for any negative eigenvalues:
        check_nans = np.any(lamb <= 0)
        # sort eigenvectors in order of descending eigenvalues:
        c = c.T
        c = c[index]
        # np.cov normalizes the covariance matrix by N-1.  We have to correct
        # for that because it's not in the Soummer 2012 equation:
        lamb = lamb * (p-1)
        # Take the dot product of the reference image with corresponding eigenvector:
        Z = np.dot(R.T, c.T)
        # Multiply by 1/sqrt(eigenvalue):
        Z = Z * np.sqrt(1/lamb)

    # Soummer 2.2.4
    # Project science target onto KL Basis:
    projection_sci_onto_basis = np.dot(T_meansub,Z)
    # This produces a (K_klip,K_klip) sized array of identical
    # rows of the projected science target.  We only need one row:
    projection_sci_onto_basis = projection_sci_onto_basis[0]
    # This fancy math let's you use fewer modes to subtract:
    lower_triangular = np.tril(np.ones([np.max(K_klip), np.max(K_klip)]))
    projection_sci_onto_basis_tril = projection_sci_onto_basis * lower_triangular
    # Create the final psf estimator by multiplying by the basis modes:
    Ihat = np.dot(projection_sci_onto_basis_tril[K_klip-1,:], Z.T)
    
    # Soummer 2.2.5
    # Truncate the science image to the different number of requested modes to use:
    outputimage = T_meansub[:np.size(K_klip),:]
    # Subtract estimated psf from science image:
    outputimage = outputimage - Ihat
    # Reshape to 
    outputimage = np.reshape(outputimage, (np.size(K_klip),*shape))

    if (return_cov and return_basis) is True:
        return outputimage, Z, cov, lamb, c
    elif return_basis:
        return outputimage, Z
    elif return_cov:
        return outputimage, cov
    else:
        return outputimage

def subtract_cubes(astamp, bstamp, K_klip, k, a_covariances=None, \
                   b_covariances=None, a_estimator=None, b_estimator=None, \
                   write_to_disk = True, write_directory = '.', outfilesuffix = ''):
    """For each image in the astamp/bstamp cubes, PSF subtract image, rotate to
       north up/east left; then median combine all images for star A and star B into
       single reduced image.  Do this for an array of KLIP mode cutoff values.  Writes
       reduced images to disk in fits cube with z axis = # of KLIP mode cutoff values.

       Written by Logan A. Pearce, 2020
       Dependencies: numpy, astropy.io.fits

       Parameters:
       -----------
       acube, bcube : 3d array
           cube of postage stamp images of star A and star B, array of shape Nxmxn 
           where N = number of images in dataset (or truncated cube if boxsize prevents 
           using every image).  Output of ab_stack_shift function.
       K_klip : int or arr
           Number of basis modes desired to use.  Can be integer or array of len b
       k : Pandas array
           Pandas array made from the output of bditools.findstars_in_dataset.  
           Assumes column names are ['filename', 'xca','yca', 'xcb', 'ycb']. Same Pandas array used in
           the ab_stack_shift function.
       a_covariances, b_covariances : arr
           covariance matrix for ref psfs for star A or B can be passed as an argument to avoid needing
           to calculate it
       a_estimator, b_estimator : 2d arr
           psf model (Z of Soummer 2.2.2) for star A or B can be passed as an argument to avoid needing
           to calculate it
       write_to_disk : bool
           when set to True, output arrays will be written to fits files in the specified directory. 
           Default = True
       write_directory : str
           directory to write fits cubes of output files.
       outfilesuffix : str
           optional suffix to end of output cube filename.  For example, note that the boxsize used for a
           a reduction was 100 pixels by setting outfilesuffix = box100, filename will be dataset_klipcube_a_box100.fit
           
       Returns:
       --------
       a_final, b_final : 3d arr
           cube of psf subtracted and sigma-clipped mean combined postagestamp images
           of star A and B, with z = # of KLIP mode cutoff values.
           If write_to_disk = True the cubes are written to fits files with
           custom headers with filename of system and suffix "_klipcube_a.fits" 
           and "_klipcube_b.fits"

    """
    from cliotools.bditools import rotate_clio, psfsub_cube_header, psf_subtract
    from astropy.stats import sigma_clip

    N = astamp.shape[0]
    if N < np.max(K_klip):
        print("Oops! You've requested more basis modes than there are ref psfs.")
        print("Setting where K_klip > N to number of ref psfs.")
        K_klip[np.where(K_klip > N)] = N
        print("K_klip = ",K_klip)
    # measure the final product image dimensions by performing rotation
    # on first image in cube:
    imhdr = fits.getheader(k['filename'][0])
    a0_rot = rotate_clio(astamp[0], imhdr, order = 4, reshape = True)
    a_final = np.zeros([np.size(K_klip),a0_rot.shape[0],a0_rot.shape[1]])
    a_final_median = np.zeros(a_final.shape)
    b_final = np.zeros(a_final.shape)
    b_final_median = np.zeros(a_final.shape)
    
    # For each KL mode cutoff value:
    for j in range(np.size(K_klip)):
        ############### star A: ##################
        # for a single K_klip value and a single star A:
        print('Subtracting using KL basis mode cutoff K_klip =',K_klip[j])
        # Use the first science image to create basis modes for psf model from star B:
        i = 0
        Fa, Zb = psf_subtract(astamp[i], bstamp, K_klip[j], return_basis = True)
        # get header and rotate image:
        imhdr = fits.getheader(k['filename'][i])
        Fa_rot = rotate_clio(Fa[0], imhdr, order = 4, reshape = True)
        # make a cube to store results:
        a = np.zeros([astamp.shape[0],Fa_rot.shape[0],Fa_rot.shape[1]])
        # Place the psf subtracted image into the container cube:
        a[i,:,:] = Fa_rot
        # Use this basis to subtract all the remaining A images:
        for i in range(1,a.shape[0]):
            # subtract:
            F2a  = psf_subtract(astamp[i], bstamp, K_klip[j], use_basis = True, basis = Zb)
            # rotate:
            F2a_rot = rotate_clio(F2a[0], imhdr, order = 4, reshape = True)
            # store:
            a[i,:,:] = F2a_rot
        # final product is combination of subtracted and rotated images:
        a_final_median[j,:,:] = np.median(a, axis = 0)
        a_final[j,:,:] = np.mean(sigma_clip(a, sigma = 3, axis = 0), axis = 0)
        
        ############### star B: ##################
        # Repeat for star B:
        i = 0
        Fb, Za = psf_subtract(bstamp[i], astamp, K_klip[j], return_basis = True)
        Fb_rot = rotate_clio(Fb[0], imhdr, order = 4, reshape = True)
        b = np.zeros(a.shape)
        b[i,:,:] = Fb_rot
        for i in range(1,b.shape[0]):
            # subtract:
            F2b  = psf_subtract(bstamp[i], astamp, K_klip[j], use_basis = True, basis = Za)
            # rotate:
            F2b_rot = rotate_clio(F2b[0], imhdr, order = 4, reshape = True)
            # store:
            b[i,:,:] = F2b_rot
        b_final_median[j,:,:] = np.median(b, axis = 0)
        b_final[j,:,:] = np.mean(sigma_clip(b, sigma = 3, axis = 0), axis = 0)
    print('Writing finished cubes to file... done!')
    if write_to_disk is True:
        newhdr = psfsub_cube_header(k['filename'][0].split('/')[0], K_klip, 'A', a_final.shape, astamp.shape[1])
        fits.writeto(k['filename'][0].split('_')[0]+'_klipcube_a'+outfilesuffix+'.fit',a_final,newhdr,overwrite=True)
        newhdr = psfsub_cube_header(k['filename'][0].split('/')[0], K_klip, 'B', b_final.shape, bstamp.shape[1])
        fits.writeto(k['filename'][0].split('_')[0]+'_klipcube_b'+outfilesuffix+'.fit',b_final,newhdr,overwrite=True)
    return a_final, b_final

'''
def do_bdi(k, K_klip, **kwargs):
    """Wrapper function for BDI psf subtraction functions
    """
    from cliotools.bditools import ab_stack_shift, subtract_cubes
    # create postage stamp cubes:
    astamp, bstamp = ab_stack_shift(k, **kwargs)
    # psf subtract cubes
    a_final, b_final = subtract_cubes(astamp, bstamp, K_klip, k, **kwargs)'''
