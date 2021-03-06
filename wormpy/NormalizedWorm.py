# -*- coding: utf-8 -*-
"""
  NormalizedWorm class
  
  @authors: @JimHokanson, @MichaelCurrie

  A translation of Matlab code written by Jim Hokanson,
  in the SegwormMatlabClasses GitHub repo.  Original code path:
  SegwormMatlabClasses / 
  +seg_worm / @normalized_worm / normalized_worm.m

"""

import warnings
import numpy as np
import scipy.io
import os
from wormpy import config

class NormalizedWorm():
  """ 
  NormalizedWorm encapsulates the normalized measures data, loaded
  from the two files, one for the eigenworm data and the other for 
  the rest.

  This will be an intermediate representation, between the parsed,
  normalized worms, and the "feature" sets. The goal is to take in the
  code from normWorms and to have a well described set of properties
  for rewriting the feature code.

  PROPERTIES / METHODS FROM JIM'S MATLAB CODE:
  * first column is original name
  * second column is renamed name, if renamed.

  properties / dynamic methods:
    eigen_worms      
    
    IN data_dict:
    
    EIGENWORM_PATH
    segmentation_status   
    frame_codes
    vulva_contours        [49,2,4642]
    non_vulva_contours    [49,2,4642]
    skeletons
    angles
    in_out_touches
    lengths
    widths
    head_areas
    tail_areas
    vulva_areas
    non_vulva_areas      
    
    n_frames               num_frames
    x                      skeletons_x
    y                      skeletons_y
    contour_x              
    contour_y       
  
  static methods:
    getObject              load_normalized_data(self, data_path)
    createObjectFromFiles  load_normalized_blocks(self, blocks_path)
                           * this last one not actually implemented yet *
                           * since I believe it is deprecated in Jim's *
                           * code *
      

  """

  """
  translated from:
  seg_worm.skeleton_indices
  
  This was originally created for feature processing. @JimHokanson 
  found a lot of off-by-1 errors in the feature processing.
  
  Used in: (list is not comprehensive)
  --------------------------------------------------------
  - posture bends
  - posture directions
  
  NOTE: These are hardcoded for now. I didn't find much use in trying
  to make this dynamic based on some maximum value.
  
  Typical Usage:
  --------------------------------------------------------
  SI = seg_worm.skeleton_indices;

  """
  # The normalized worm contains precisely 49 points per frame.  Here
  # we list in a dictionary various partitions of the worm.
  worm_partitions = None
  # this stores a dictionary of various ways of organizing the partitions
  worm_parititon_subsets = None
  
  data_dict = None  # A dictionary of all data in norm_obj.mat
  
  # shape = (7, 48)
  # NOTE: It is one less than 49 because
  #       the values are calculated from paired values, 
  #       and the # of pairs is one less than the # of samples
  eigen_worms = None

  def __init__(self, data_file_path, eigen_worm_file_path):
    """ 
    Initialize this instance by loading both the worm and 
    the eigen_worm data

    Parameters
    ---------------------------------------
    data_file_path: string
    
    eigen_worm_file_path: string
    
    """
    self.load_normalized_data(data_file_path)
    self.load_eigen_worms(eigen_worm_file_path)
    
    # all are valid partitions of the worm's 49 skeleton points:
    # all    
    # head, body, tail
    # head, neck, midbody, hips, tail
    # head_tip, head_base, body, tail_base, tail_tip
    # head_tip, head_base, neck, midbody, hips, tail_base, tail_tip

    self.worm_partitions = {'head': (0, 8), 
                            'neck': (8, 16),
                            'midbody':  (16, 33),
                            'hips':  (33, 41),
                            'tail': (41, 49),
                            # refinements of ['head']
                            'head_tip': (0, 4),     
                            'head_base': (4, 8),    # ""
                            # refinements of ['tail']
                            'tail_base': (40, 45),  
                            'tail_tip': (45, 49),   # ""
                            # DEBUG: for get_locomotion_bends: 
                            # DEBUG: Jim might remove
                            'nose': (3, -1),    
                            # DEBUG: for get_locomotion_bends: 
                            # DEBUG: Jim might remove
                            'neck': (7, -1),
                            'all': (0, 49),
                            # neck, midbody, and hips
                            'body': (8, 41)}

    self.worm_partition_subsets = {'normal': ('head', 'neck', 
                                              'midbody', 'hips', 'tail'),
                                   'first_third': ('head', 'neck'),
                                   'second_third': ('midbody'),
                                   'last_third': ('hips', 'tail'),
                                   'all': ('all')}

    # If we want to mimic the old Schafer Lab decisions,
    # change the partition definitions.
    if(config.MIMIC_OLD_BEHAVIOUR):
      self.worm_partitions['midbody'] = (20, 29)

  def get_partition_subset(self, partition_type):
    """ 
    There are various ways of partitioning the worm's 49 points.
    this method returns a subset of the worm partition dictionary

    Parameters
    ---------------------------------------
    partition_type: string
      e.g. 'head'
      
    Usage
    ---------------------------------------
    For example, to see the mean of the head and the mean of the neck, 
    use the partition subset, 'first_third', like this:
    
    nw = NormalizedWorm(....)
    
    width_dict = {k: np.mean(nw.get_partition(k), 0) \
              for k in ('head', 'neck')}
              
    OR, using self.worm_partition_subsets,
    
    s = nw.get_paritition_subset('first_third')
    # i.e. s = {'head':(0,8), 'neck':(8,16)}
    
    width_dict = {k: np.mean(nw.get_partition(k), 0) \
              for k in s.keys()}

    Notes
    ---------------------------------------    
    Translated from get.ALL_NORMAL_INDICES in SegwormMatlabClasses / 
    +seg_worm / @skeleton_indices / skeleton_indices.m

    """

    # parition_type is assumed to be a key for the dictionary
    # worm_partition_subsets
    p = self.worm_partition_subsets[partition_type]
    
    # return only the subset of partitions contained in the particular 
    # subset of interest, p.
    return {k: self.worm_partitions[k] for k in p}


  def get_partition(self, partition_key, data_key = 'skeletons', 
                    split_spatial_dimensions = False):
    """    
    Retrieve partition of a measurement of the worm, that is, across all
    available frames but across only a subset of the 49 points.
    
    Parameters
    ---------------------------------------    
    partition_key: string
      The desired partition.  e.g. 'head', 'tail', etc.
      
    data_key: string  (optional)
      The desired measurement (default is 'skeletons')

    split_spatial_dimensions: bool    (optional)
      If True, the partition is returned separated into x and y

    Returns
    ---------------------------------------    
    A numpy array containing the data requested, cropped to just
    the partition requested.
    (so the shape might be, say, 4xn if data is 'angles')

    Notes
    ---------------------------------------    
    Translated from get.ALL_NORMAL_INDICES in SegwormMatlabClasses / 
    +seg_worm / @skeleton_indices / skeleton_indices.m
      
    """
    #We use numpy.split to split a data_dict element into three, cleaved
    #first by the first entry in the duple worm_partitions[partition_key],
    #and second by the second entry in that duple.
    
    #Taking the second element of the resulting list of arrays, i.e. [1],
    #gives the partitioned component we were looking for.
    partition = np.split(self.data_dict[data_key], 
                    self.worm_partitions[partition_key])[1]
    
    if(split_spatial_dimensions):
      return partition[:,0,:], partition[:,1,:]
    else:
      return partition
    
  def load_normalized_data(self, data_file_path):
    """ 
    Load the norm_obj.mat file into this class

    Notes
    ---------------------------------------    
    Translated from getObject in SegwormMatlabClasses
    
    """
    
    if(not os.path.isfile(data_file_path)):
      raise Exception("Data file not found: " + data_file_path)
    else:
      self.data_file = scipy.io.loadmat(data_file_path, 
                                        # squeeze unit matrix dimensions:
                                        squeeze_me = True, 
                                        # force return numpy object array:
                                        struct_as_record = False)

      # self.data_file is a dictionary, with keys:
      # self.data_file.keys() = 
      # dict_keys(['__header__', 's', '__version__', '__globals__'])
      
      # All the action is in data_file['s'], which is a numpy.ndarray where
      # data_file['s'].dtype is an array showing how the data is structured.
      # it is structured in precisely the order specified in data_keys below

      staging_data = self.data_file['s']

      # NOTE: These are aligned to the order in the files.
      # these will be the keys of the dictionary data_dict
      data_keys = [
                # this just contains a string for where to find the 
                # eigenworm file.
                'EIGENWORM_PATH',   
                # a string of length n, showing, for each frame of the video:
                # s = segmented
                # f = segmentation failed
                # m = stage movement
                # d = dropped frame
                # n??? - there is reference tin some old code to this 
                # after loading this we convert it to a numpy array.
                'segmentation_status',
                # shape is (1 n), see comments in 
                # seg_worm.parsing.frame_errors
                'frame_codes',
                'vulva_contours',     # shape is (49, 2, n) integer
                'non_vulva_contours', # shape is (49, 2, n) integer
                'skeletons',          # shape is (49, 2, n) integer
                'angles',             # shape is (49, 2, n) integer
                'in_out_touches',     # shape is (49, n) integer (degrees)
                'lengths',            # shape is (n) integer
                'widths',             # shape is (49, n) integer
                'head_areas',         # shape is (n) integer
                'tail_areas',         # shape is (n) integer
                'vulva_areas',        # shape is (n) integer
                'non_vulva_areas',    # shape is (n) integer
                'x',                  # shape is (49, n) integer
                'y']                  # shape is (49, n) integer
      
      # Here I use powerful python syntax to reference data elements of s
      # dynamically through built-in method getattr
      # that is, getattr(s, x)  works syntactically just like s.x, 
      # only x is a variable, so we can do a list comprehension with it!
      # this is to build up a nice dictionary containing the data in s
      self.data_dict = {x: getattr(staging_data, x) for x in data_keys}
      
      # Let's change the string of length n to a numpy array of single 
      # characters of length n, to be consistent with the other data 
      # structures
      self.data_dict['segmentation_status'] = \
        np.array(list(self.data_dict['segmentation_status']))
        
      # TODO: @MichaelCurrie: do this.  but I'm not sure how the file 
      # knows where the eigenworm file is
      # So I have to think about this step.        
      #self.load_eigen_worms(self.data_dict['EIGENWORM_PATH'])
    
      self.load_frame_code_descriptions()    
    
  def load_frame_code_descriptions(self):
    """
    Load the frame_codes descriptions, which are stored in a .csv file
      
    """
    file_path = os.path.join(os.path.abspath(os.getcwd()),
                             'wormpy', 
                             'frame_codes.csv')
    f = open(file_path, 'r')

    self.frame_codes_descriptions = []
    
    for line in f:
      # split along ';' but ignore any newlines or quotes
      a = line.replace("\n","").replace("'","").split(';')
      # the actual frame codes (the first entry on each line)
      # can be treated as integers
      a[0] = int(a[0])
      self.frame_codes_descriptions.append(a)  
    
    f.close()
    
    

  def load_normalized_blocks(self, blocks_path):
    """ 
    Processes all the MatLab data "blocks" created from the raw 
    video into one coherent set of data.  This is a translation 
    of createObjectFromFiles from Jim's original code.
        
    Notes
    ---------------------------------------    
    From @MichaelCurrie: This appears to be the old way of doing this.
    I'll hold off translating this "block" processor.  
    I think norm_obj.mat actually maps directly to the structure I need.
    
    """
    pass


  def rotate(self, theta_d):
    """   
    Returns a NormalizedWorm instance with each frame rotated by 
    the amount given in the per-frame theta_d array.

    Parameters
    ---------------------------------------    
    theta_d: 1-dimensional ndarray of dtype=float
      The frame-by-frame rotation angle in degrees.
      A 1-dimensional n-element array where n is the number of
      frames, giving a rotation angle for each frame.
    
    Returns
    ---------------------------------------    
    A new NormalizedWorm instance with the same worm, rotated
    in each frame by the requested amount.
    
    """
    #theta_r = theta_d * (np.pi / 180)
    
    #%Unrotate worm
    #%-----------------------------------------------------------------
    #wwx = bsxfun(@times,sx,cos(theta_r)) + bsxfun(@times,sy,sin(theta_r));
    #wwy = bsxfun(@times,sx,-sin(theta_r)) + bsxfun(@times,sy,cos(theta_r));


    # TODO
    return self        

  def centre(self):
    """
    Frame-by-frame mean of the skeleton points

    Returns
    ---------------------------------------    
    A numpy array of length n, where n is the number of
    frames, giving for each frame the mean of the skeleton points.
        
    """
    s = self.data_dict['skeletons']
    with warnings.catch_warnings():
      temp = np.nanmean(s, 0, keepdims=False)
      
    return temp

  def angle(self):
    """
    Frame-by-frame mean of the skeleton points

    Returns
    ---------------------------------------    
    A numpy array of length n, giving for each frame
    the angle formed by the first and last skeleton point.
        
    """
    s = self.data_dict['skeletons']
    # obtain vector between first and last skeleton point
    v = s[48,:,:]-s[0,:,:]  
    # find the angle of this vector
    return np.arctan(v[1,:]/v[0,:])*(180/np.pi)

  def translate_to_centre(self):
    """ 
    Return a NormalizedWorm instance with each frame moved so the 
    centroid of the worm is 0,0

    Returns
    ---------------------------------------    
    A NormalizedWorm instance with the above properties.

    """
    s = self.data_dict['skeletons']
    s_mean = np.ones(np.shape(s)) * np.nanmean(s, 0, keepdims=False)
    
    #nw2 = NormalizedWorm()
    
    # TODO
    return s - s_mean
       
  def rotate_and_translate(self):
    """
    Perform both a rotation and a translation of the skeleton

    Returns
    ---------------------------------------    
    A numpy array, which is the centred and rotated normalized
    worm skeleton.

    Notes
    ---------------------------------------    
    To perform this matrix multiplication we are multiplying:
      rot_matrix * s
    This is shape 2 x 2 x n, times 2 x 49 x n.
    Basically we want the first matrix treated as two-dimensional,
    and the second matrix treated as one-dimensional,
    with the results applied elementwise in the other dimensions.
    
    To make this work I believe we need to pre-broadcast rot_matrix into
    the skeleton points dimension (the one with 49 points) so that we have
      2 x 2 x 49 x n, times 2 x 49 x n
    #s1 = np.rollaxis(self.skeletons, 1)
    
    #rot_matrix = np.ones(np.shape(s1)) * rot_matrix
    
    #self.skeletons_rotated = rot_matrix.dot(self.skeletons)    
    
    """
    
    skeletons_centred = self.translate_to_centre()
    orientation = self.angle()
  
    a = -orientation * (np.pi/180)
    
    rot_matrix = np.array([[np.cos(a), -np.sin(a)],
                           [np.sin(a),  np.cos(a)]])    

    # we need the x,y listed in the first dimension
    s1 = np.rollaxis(skeletons_centred, 1)

    # for example, here is the first point of the first frame rotated:
    #rot_matrix[:,:,0].dot(s1[:,0,0])    
    
    # ATTEMPTING TO CHANGE rot_matrix from 2x2x49xn to 2x49xn
    # rot_matrix2 = np.ones((2, 2, np.shape(s1)[1], np.shape(s1)[2])) * rot_matrix    
    
    s1_rotated = []        
    
    # rotate the worm frame-by-frame and add these skeletons to a list
    for frame_index in range(self.num_frames):
      s1_rotated.append(rot_matrix[:,:,frame_index].dot(s1[:,:,frame_index]))
    #print(np.shape(np.rollaxis(rot_matrix[:,:,0].dot(s1[:,:,0]),0)))
      
    # save the list as a numpy array
    s1_rotated = np.array(s1_rotated)
    
    # fix the axis settings
    return np.rollaxis(np.rollaxis(s1_rotated,0,3),1)



  def load_eigen_worms(self, eigen_worm_file_path):
    """ 
    Load the eigen_worms, which are stored in a MatLab data file
    
        
    Parameters
    ---------------------------------------    
    eigen_worm_file_path: string
      file location of the eigenworm file to be loaded


    Notes
    ---------------------------------------    
    Translation of get.eigen_worms(obj) in SegwormMatlabClasses
      
    """
    if(not os.path.isfile(eigen_worm_file_path)):
      raise Exception("Eigenworm file not found: " + eigen_worm_file_path)
    else:
      # scipy.io.loadmat returns a dictionary with variable names 
      # as keys, and loaded matrices as values
      eigen_worms_file = scipy.io.loadmat(eigen_worm_file_path)

      # TODO: turn this into a numpy array, probably
      # TODO: and possibly extract other things of value from 
      #       eigen_worms_file
      #self.eigen_worms = eigen_worms_file.values() # DEBUG: I think this is wrong

      # DEBUG: another way to load eigenworms:
      #h = h5py.File(uconfig.EIGENWORM_PATH,'r')
      #eigen_worms = h['eigenWorms'].value


      self.eigen_worms = eigen_worms_file.values() # DEBUG: I think this is wrong

  @property
  def num_frames(self): 
    """ 
    The number of frames in the video.
    
    Returns
    ---------------------------------------    
    int
      number of frames in the video
      
    """
    
    # ndarray.shape returns a tuple of array dimensions.
    # the frames are along the first dimension i.e. [0].
    return self.data_dict['skeletons'].shape[2]


  def position_limits(self, dimension, measurement='skeletons'):  
    """ 
    Maximum extent of worm's travels projected onto a given axis

    Parameters    
    ---------------------------------------        
    dimension: specify 0 for X axis, or 1 for Y axis.

    Notes
    ---------------------------------------    
    Dropped frames show up as NaN.
    nanmin returns the min ignoring such NaNs.
    
    """
    d = self.data_dict[measurement]
    if(len(np.shape(d))<3):
      raise Exception("Position Limits Is Only Implemented for 2D data")
    return (np.nanmin(d[dimension,0,:]), 
            np.nanmax(d[dimension,1,:]))

  @property
  def contour_x(self):
    """ 
      Return the approximate worm contour, derived from data
      NOTE: The first and last points are duplicates, so we omit
            those on the second set. We also reverse the contour so that
            it encompasses an "out and back" contour
    """
    vc  = self.data_dict['vulva_contours']
    nvc = self.data_dict['non_vulva_contours']
    return np.concatenate((vc[:,0,:], nvc[-2:0:-1,0,:]))    

  @property
  def contour_y(self):
    vc  = self.data_dict['vulva_contours']
    nvc = self.data_dict['non_vulva_contours']
    return np.concatenate((vc[:,1,:], nvc[-2:0:-1,1,:]))    

  @property
  def skeleton_x(self):
    return self.data_dict['skeletons'][:,0,:]
    
  @property
  def skeleton_y(self):
    return self.data_dict['skeletons'][:,1,:]



