# -*- python -*- 

# This software was produced by NIST, an agency of the U.S. government,
# and by statute is not subject to copyright in the United States.
# Recipients of this software assume all responsibilities associated
# with its operation, modification and maintenance. However, to
# facilitate maintenance we ask that before distributing modifed
# versions of this software, you first contact the authors at
# oof_manager@nist.gov. 

dirname = 'SRC'

if not DIM_3:
    subdirs = ['common',
               'engine',
               'image', 
               'orientationmap',
               'tutorials',
               'EXTENSIONS']

else:
    subdirs = ['common',
               'engine',
               'image']



