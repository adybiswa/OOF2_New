# -*- python -*- 


# This software was produced by NIST, an agency of the U.S. government,
# and by statute is not subject to copyright in the United States.
# Recipients of this software assume all responsibilities associated
# with its operation, modification and maintenance. However, to
# facilitate maintenance we ask that before distributing modifed
# versions of this software, you first contact the authors at
# oof_manager@nist.gov. 

dirname = 'common'
subdirs = ['IO', 'EXTRA']
clib = 'oof2common'
clib_order = 0

cfiles = [
    'activearea.C', 'argv.C', 'bitmask.C', 'boolarray.C',
    'brushstyle.C', 'ccolor.C', 'cdebug.C', 'cmicrostructure.C',
    'colordifference.C', 'coord.C', 'cpixelselection.C', 'despeckle.C',
    'expandgrp.C', 'identification.C', 'intarray.C', 'lock.C',
    'ooferror.C', 'pixelattribute.C', 'pixelgroup.C', 'guitop.C',
    'pixelselectioncourier.C', 'pixelsetboundary.C', 'random.C',
    'sincos.C', 'swiglib.C', 'switchboard.C', 'threadstate.C',
    'timestamp.C', 'trace.C', 'pythonlock.C', 'progress.C',
    'direction.C', 'doublevec.C', 'smallmatrix.C',
    'latticesystem.C', 'burn.C', 'statgroups.C'
]

swigfiles = [
    'abstractimage.swg', 'activearea.swg', 'argv.swg',
    'boolarray.swg', 'brushstyle.swg', 'ccolor.swg', 'cdebug.swg',
    'cmicrostructure.swg', 'colordifference.swg', 'config.swg',
    'coord.swg', 'cpixelselection.swg', 'crandom.swg',
    'doublearray.swg', 'geometry.swg', 'intarray.swg', 'lock.swg',
    'ooferror.swg', 'pixelattribute.swg', 'pixelgroup.swg',
    'pixelselectioncourier.swg', 'switchboard.swg',
    'threadstate.swg', 'timestamp.swg', 'trace.swg', 'progress.swg',
    'guitop.swg', 'identification.swg', 'direction.swg', 'doublevec.swg',
    'smallmatrix.swg', 'latticesystem.swg',
    'pixelsetboundary.swg', 'burn.swg', 'statgroups.swg'
]

pyfiles = [ 
    'activeareamod.py', 'backEnd.py', 'color.py', 'cregisteredclass.py',
    'debug.py', 'director.py', 'enum.py', 'excepthook.py', 'garbage.py'
    'initialize.py', 'labeltree.py', 'mainthread.py',
    'microstructure.py', 'object_id.py', 'oof.py', 'oof_getopt.py',
    'oofversion.py', 'parallel_enable.py', 'parallel_object_manager.py',
    'parallel_performance.py', 'pixelselection.py', 'threadmanager.py',
    'pixelselectionmethod.py', 'pixelselectionmod.py', 'primitives.py',
    'quit.py', 'registeredclass.py', 'ringbuffer.py', 'strfunction.py',
    'subthread.py', 'thread_enable.py', 'timer.py', 'toolbox.py',
    'utils.py', 'version.py', 'worker.py', 'runtimeflags.py'
]

swigpyfiles = [
    'ooferror.spy', 'colordifference.spy', 'coord.spy', 'geometry.spy',
    'switchboard.spy', 'pixelgroup.spy', 'timestamp.spy',
    'cdebug.spy', 'brushstyle.spy', 'pixelattribute.spy', 'guitop.spy',
    'activearea.spy', 'lock.spy', 'cmicrostructure.spy', 'doublevec.spy',
    'smallmatrix.spy', 'direction.spy',
    'latticesystem.spy', 'burn.spy', 'statgroups.spy'
]


hfiles = [
    'abstractimage.h', 'activearea.h', 'argv.h', 'array.h', 'bitmask.h',
    'boolarray.h', 'brushstyle.h', 'cachedvalue.h', 'ccolor.h',
    'cdebug.h', 'cmicrostructure.h', 'colordifference.h', 'coord.h',
    'cpixelselection.h', 'doublearray.h', 'geometry.h', 'guitop.h',
    'identification.h', 'intarray.h', 'lock.h', 'ooferror.h',
    'pixelattribute.h', 'pixelgroup.h', 'pixelselectioncourier.h',
    'pixelsetboundary.h', 'printvec.h', 'pythonexportable.h', 'random.h',
    'removeitem.h', 'sincos.h', 'swiglib.h', 'switchboard.h',
    'threadstate.h', 'timestamp.h', 'tostring.h', 'trace.h',
    'pythonlock.h', 'direction.h', 'doublevec.h', 'smallmatrix.h',
    'latticesystem.h', 'burn.h', 'statgroups.h'
]




if HAVE_MPI:
    cfiles.extend(['mpitools.C'])
    swigfiles.extend(['mpitools.swg'])
    swigpyfiles.extend(['mpitools.spy'])
    hfiles.extend(['mpitools.h'])

def set_clib_flags(clib):
    if HAVE_MPI:
        clib.externalLibs.append('pmpich++')
        clib.externalLibs.append('mpich')
