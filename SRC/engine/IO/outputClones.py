# -*- python -*-


# This software was produced by NIST, an agency of the U.S. government,
# and by statute is not subject to copyright in the United States.
# Recipients of this software assume all responsibilities associated
# with its operation, modification and maintenance. However, to
# facilitate maintenance we ask that before distributing modified
# versions of this software, you first contact the authors at
# oof_manager@nist.gov.

# A smattering of pre-defined outputs for the convenience of OOF users.

from ooflib.SWIG.common import config
from ooflib.SWIG.common import coord
from ooflib.SWIG.common import ooferror
from ooflib.SWIG.common import progress
from ooflib.SWIG.engine import invariant
from ooflib.SWIG.engine import outputval
from ooflib.SWIG.engine import planarity
from ooflib.common import debug
from ooflib.common import enum
from ooflib.common import primitives
from ooflib.common import utils
from ooflib.common.IO import parameter
from ooflib.engine.IO import meshparameters
from ooflib.engine.IO import output
from types import *
import itertools
import math
import sys

# Examples of Outputs

# See comments in output.py.

## TODO: Output.evaluate() should return an iterator instead of a list
## of outputvals.  Some code that uses outputs tries to index a list
## (eg MeshDataGUI.updateData), and some code needs to make multiple
## passes (eg, contour), so those bits will have to be changed. 

## TODO: Add progress bars to more outputs?

#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#

def _pos(mesh, elements, coords):
    # The argument "elements" is a list of Elements or Edges, possibly
    # mixed together. The argument "coords" is a list of lists.  Each
    # Element in the elements list corresponds to a list of
    # MasterCoords in the coords list, and each Edge corresponds to a
    # list of doubles (ie, master coords for the Edge, in the range
    # [0,1)).
    return utils.flatten1([element.position(coordList)
                           for element,coordList in zip(elements, coords)])

posOutput = output.Output(
    name="original position",
    otype=(primitives.Point, coord.Coord),
    callback=_pos)
                            

#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#

class SpaceComponent(enum.EnumClass('x', 'y', 'z')):
    tip='Components of vectors.'
    discussion="""<para>
    <classname>SpaceComponent</classname> is used by various
    <link
    linkend='Section-Output'><classname>Outputs</classname></link> to
    choose one of the components of a vector quantity.
    </para>"""

if config.dimension() == 2:    
    class InPlaneSpaceComponent(enum.EnumClass('x', 'y')):
        tip="The in-plane components of vectors."
        discussion="""<para>
        <classname>InPlaneSpaceComponent</classname> is used by various
        <link
        linkend='Section-Output'><classname>Outputs</classname></link> to
        choose one of the in-plane components of a vector quantity.
        </para>"""
elif config.dimension() == 3:
    InPlaneSpaceComponent = SpaceComponent

#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#

# FieldOutput is for fields which are defined on the Mesh.  Fields
# that aren't defined return 0.  If a Field isn't defined everywhere,
# the user shouldn't be evaluating it everywhere, but that's his or
# her decision.

def _field(mesh, elements, coords, field):
    return utils.flatten1([element.outputFields(mesh, field, ecoords)
           for element, ecoords in itertools.izip(elements, coords)])

def _field_instancefn(self):
    field = self.resolveAlias('field').value
    if field is None:
        return
    # Don't combine the following two lines into one!  There must be a
    # reference to ovalue until zero() is called.  See valuePtr
    # comment in outputval.h.
    ovalue = field.newOutputValue()
    return ovalue.valuePtr().zero()

def _field_column_names(self):
    field = self.resolveAlias('field').value
    if field.ndof() == 1:
        return [field.name()]
    names = []
    it = field.iterator(planarity.ALL_INDICES)
    while not it.end():
        names.append("%s[%s]" % (field.name(), it.shortstring()))
        it.next()
    return names

FieldOutput = output.Output(
    name = "field",
    callback = _field,
    otype = outputval.OutputValPtr,
    srepr=lambda x: x.resolveAlias('field').value.name(),
    instancefn = _field_instancefn,
    column_names = _field_column_names,
    params = [meshparameters.FieldParameter("field", outofplane=1,
                                               tip=parameter.emptyTipString)],
    tip="Compute Field values.",
    discussion='<para>Compute the value of the given &field; on a &mesh;.</para>'
    )



## TODO: Add Field and Flux outputs that take their values from some
## *other* Mesh, in order to compute how well solutions are
## converging.  Or, possibly, add a DifferenceWithOtherMesh output,
## that computes the same quantities for the minuend and subtrahend,
## but on different Meshes.

############

def _fieldderiv(mesh, elements, coords, field, derivative):
    return utils.flatten1(
        [element.outputFieldDerivs(mesh, field, derivative, ecoords)
         for element, ecoords in itertools.izip(elements, coords)])

def _fieldderiv_shortrepr(self):
    field = self.resolveAlias('field').value
    derivative = self.resolveAlias('derivative').value
    return "d(%s)/d%s" % (field.name(), derivative.string())

def _fieldderiv_column_names(self):
    field = self.resolveAlias('field').value
    derivative = self.resolveAlias('derivative').value
    if field.ndof() == 1:
        return ["d(%s)/d%s" % (field.name(), derivative.string())]
    names = []
    it = field.iterator(planarity.ALL_INDICES)
    while not it.end():
        names.append("d(%s[%s])/d%s" % (field.name(), it.shortstring(),
                                        derivative.string()))
        it.next()
    return names

FieldDerivOutput = output.Output(
    name = "field derivative",
    callback = _fieldderiv,
    otype = outputval.OutputValPtr,
    instancefn = _field_instancefn,
    params = [meshparameters.FieldParameter("field", outofplane=1,
                                                tip=parameter.emptyTipString),
                  enum.EnumParameter("derivative", InPlaneSpaceComponent,
                                     tip='Which derivative to take.')],
    srepr=_fieldderiv_shortrepr,
    column_names=_fieldderiv_column_names,
    tip='Compute derivatives of Fields.',
    discussion='<para>Compute the spatial derivative of a &field; on a &mesh;.</para>')

############

from ooflib.SWIG.common import threadstate

def _flux(mesh, elements, coords, flux):
    ans = []
    prog = progress.getProgress("Evaluating flux", progress.DEFINITE)
    #nel = mesh.nelements()      # No!  Should be len(elements), but
                                # elements is a generator.
    elist = list(elements)
    nel = len(elist)
    try:
        ecount = 0
        for element, ecoords in itertools.izip(elist, coords):
            mesh.begin_all_subproblems(element)
    ##        element.begin_material_computation(mesh)
            ans.append(element.outputFluxes(mesh, flux, ecoords))
    ##        element.end_material_computation(mesh)
            mesh.end_all_subproblems(element)
            ecount += 1
            prog.setFraction((1.*ecount)/nel)
            prog.setMessage("%d/%d elements" % (ecount, nel))
        return utils.flatten1(ans)
    finally:
        prog.finish()

def _flux_shortrepr(self):
    return self.resolveAlias('flux').value.name()

def _flux_instancefn(self):
    flux = self.resolveAlias('flux').value
    if flux is None:
        return
    # Don't combine the following two lines into one!  There must be a
    # reference to ovalue until zero() is called.  See valuePtr
    # comment in outputval.h.
    ovalue = flux.newOutputValue()
    return ovalue.valuePtr().zero()

def _flux_column_names(self):
    flux = self.resolveAlias('flux').value
    it = flux.iterator(planarity.ALL_INDICES)
    names = []
    while not it.end():
        names.append("%s[%s]" % (flux.name(), it.shortstring()))
        it.next()
    return names

FluxOutput = output.Output(
    name = "flux",
    callback = _flux,
    otype = outputval.OutputValPtr,
    instancefn = _flux_instancefn,
    column_names=_flux_column_names,
    params = [meshparameters.FluxParameter("flux",
                                           tip=parameter.emptyTipString)],
    srepr=_flux_shortrepr,
    tip='Compute Flux values.',
    discussion='<para>Compute the value of the given &flux; on a &mesh;.</para>')

################

def _component(mesh, elements, coords, field, component):
    if field:
        # 'component' is a string, "x" or "xy" or the like
        comp = field[0].getIndex(component) # convert string to IndexP
        return [outputval.ScalarOutputVal(f[comp]) for f in field]
    return []
        
def scalar_instancefn(self):
    return outputval.ScalarOutputVal(0.0)

def single_column_name(self):
    # The name of a column in an Output with only one column is the
    # same as the shortrepr of the Output.
    return [self.shortrepr(self)]


ComponentOutput = output.Output(
    name = "component",
    callback = _component,
    otype = outputval.ScalarOutputValPtr,
    instancefn = scalar_instancefn,
    column_names=single_column_name,
    inputs = [outputval.OutputValParameter('field')],
    params = [meshparameters.FieldIndexParameter(
            'component', tip='Which component to take.')]
    )

###

def _fieldcomp_shortrepr(self):
    field = self.resolveAlias('field').value
    fieldname = field.name()
    if field.ndof() > 1:
        comp = self.resolveAlias('component').value
        return "%s[%s]" % (fieldname, comp)
    else:
        return fieldname

FieldCompOutput = ComponentOutput.clone(
    name="field component",
    column_names=single_column_name,
    srepr=_fieldcomp_shortrepr,
    tip='Compute a component of a Field.',
    discussion=
    '<para>Compute a single component of a &field; on a &mesh;.</para>',
    )
FieldCompOutput.connect("field", FieldOutput)
FieldCompOutput.aliasParam('field:field', 'field')

####

def _fieldderiv_shortrepr(self):
    field = self.resolveAlias('field').value
    fieldname = field.name()
    if field.ndof() > 1:
        comp = self.resolveAlias('component').value
        fieldname += '[%s]' % comp
    deriv = self.resolveAlias('derivative').value
    return "d(%s)/d%s" % (fieldname, deriv.string())

FieldDerivCompOutput = ComponentOutput.clone(
    name="field derivative component",
    tip='Compute a component of a Field derivative.',
    discussion='<para>Compute a single component of a &field; derivative on a &mesh;.</para>',
    srepr=_fieldderiv_shortrepr,
    column_names=single_column_name)

FieldDerivCompOutput.connect("field", FieldDerivOutput)
FieldDerivCompOutput.aliasParam('field:field',  'field')
FieldDerivCompOutput.aliasParam('field:derivative', 'derivative')

###

def _fluxcomp_shortrepr(self):
    flux = self.resolveAlias('flux').value
    fluxname = flux.name()
    if flux.ndof() > 1:
        comp = self.resolveAlias('component').value
        return "%s[%s]" % (fluxname, comp)
    else:
        return fluxname

FluxCompOutput = ComponentOutput.clone(
    name="flux component",
    tip='Compute a component of a Flux.',
    srepr=_fluxcomp_shortrepr,
    column_names=single_column_name,
    discussion=
    '<para>Compute a single component of a &flux; on a &mesh;.</para>')
FluxCompOutput.connect("field", FluxOutput)
FluxCompOutput.aliasParam('field:flux', 'flux')

###############

def _invariant(mesh, elements, coords, field, invariant):
    ## TODO: Use imap instead of map.  See comment at top of file.
    return map(outputval.ScalarOutputVal, itertools.imap(invariant, field))

def _invariant_shortrepr(self):
    field = self.findInput('field').shortrepr()
    invariant = self.resolveAlias('invariant').value.shortrepr()
    return "%s(%s)" % (invariant, field)

InvariantOutput = output.Output(
    name="invariant",
    callback=_invariant,
    otype=outputval.ScalarOutputValPtr,
    srepr=_invariant_shortrepr,
    instancefn = scalar_instancefn,
    column_names=single_column_name,
    inputs=[outputval.OutputValParameter('field')],
    params=[invariant.InvariantParameter("invariant",
                                            tip=parameter.emptyTipString)]
    )

FieldInvariantOutput = InvariantOutput.clone(
    name="field invariant",
    tip='Compute invariants of Fields.',
    discussion='<para>Compute invariants of a &field; on a &mesh;.</para>')
FieldInvariantOutput.connect("field", FieldOutput)
FieldInvariantOutput.aliasParam('field:field', 'field')

FluxInvariantOutput = InvariantOutput.clone(
    name="flux invariant",
    tip='Compute invariants of Fluxes.',
    discussion='<para>Compute invariants of a &flux; on a &mesh;.</para>')
FluxInvariantOutput.connect("field", FluxOutput)
FluxInvariantOutput.aliasParam('field:flux', 'flux')

FieldDerivInvariantOutput = InvariantOutput.clone(
    name="field derivative invariant",
    tip='Compute invariants of Field derivatives.',
    discussion='<para>Compute invariants of the derivative of a &field; on a &mesh;</para>')
FieldDerivInvariantOutput.connect("field", FieldDerivOutput)
FieldDerivInvariantOutput.aliasParam('field:field', 'field')
FieldDerivInvariantOutput.aliasParam('field:derivative', 'derivative')

#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#

from ooflib.common import strfunction

def _scalarFunctionOutput(mesh, elements, coords, f):
    ans = []
    t = mesh.getCurrentTime()
    prog = progress.getProgress("Function evaluation", progress.DEFINITE)
    ecount = 0 
    nel = mesh.nelements()
    for element, coordlist in itertools.izip(elements, coords):
        realcoords = itertools.imap(element.from_master, coordlist)
        ans.extend(outputval.ScalarOutputVal(f(coord, t)) for coord in realcoords)
        ecount += 1
        prog.setFraction((1.*ecount)/nel)
        prog.setMessage("%d/%d elements" % (ecount, nel))
    prog.finish()
    return ans

if config.dimension() == 2:
    _tip = "Function of x, y, and t."
else:
    _tip = "Function of x, y, z, and t."

def _scalarFunction_shortrepr(self):
    return self.resolveAlias("f").value.string()

ScalarFunctionOutput = output.Output(
    name="Function",
    callback=_scalarFunctionOutput,
    otype=outputval.ScalarOutputValPtr,
    instancefn=scalar_instancefn,
    srepr=_scalarFunction_shortrepr,
    column_names=single_column_name,
    params=[
        strfunction.XYTStrFunctionParameter(
            "f",
            default=strfunction.XYTStrFunction('1.0'),
            tip=_tip)
        ]
    )

def _vectorFunctionOutput(mesh, elements, coords, fx=None, fy=None, fz=None):
    ans = []
    for element, coordlist in itertools.izip(elements, coords):
        realcoords = map(element.from_master, coordlist)
        for coord in realcoords:
            val = outputval.VectorOutputVal(config.dimension())
            it = val.getIterator()
            # Although f has three components, the third one won't be
            # used if we're not in three dimensions.
            f = iter([fx, fy, fz])
            while not it.end(): # use size of val, not f!
                fi = f.next()   # python iterator
                val[it] = fi(coord)
                it.next()       # oof IteratorP from fieldindex.py
            ans.append(val)
        ## TODO: That was a real mess.  If OutputVal.getIterator
        ## returned a real Python iterator object, this could be
        ## rewritten as:
        ## f = (fx, fy)
        ## for coord in realcoords:
        ##     val = outputval.VectorOutputVal(2)
        ##     for i, fi in itertools.izip(val.getIterator(), f):
        ##         val[i] = fi(coord)
        ##     ans.append(val)
    return ans

def _vecfuncparam(component, components):
    return strfunction.XYStrFunctionParameter(
        "f"+component,
        default=strfunction.XYStrFunction('1.0'),
        tip="The %s component of the function as a Python function of %s" 
        %(component, components))

if config.dimension() == 2:
    _vecfuncparams=[_vecfuncparam(comp, 'x and y') for comp in 'xy']
else:
    _vecfuncparams=[_vecfuncparam(comp, 'x, y, and z') for comp in 'xyz']

def _vecfunc_shortrepr(self):
    if config.dimension() == 2:
        pnames = "xy"
    else:
        pnames = "xyz"
    return ("("
            + ",".join([self.resolveAlias('f'+p).value.string() for p in pnames])
            + ")")
def _vecfunc_column_names(self):
    if config.dimension() == 2:
        return ["fx", "fy"]
    else:
        return ["fx", "fy", "fz"]

def vector_instancefn(self):
    return outputval.VectorOutputVal(config.dimension()).zero()

VectorFunctionOutput = output.Output(
    name="Vector Function",
    callback=_vectorFunctionOutput,
    otype=outputval.VectorOutputValPtr,
    instancefn=vector_instancefn,
    srepr=_vecfunc_shortrepr,
    column_names=_vecfunc_column_names,
    params=_vecfuncparams
    )

#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#

def _pointSum(mesh, elements, coords, point1, point2, a, b):
    ans = [a*f+b*s for f,s in itertools.izip(point1, point2)]
    return ans

PointSumOutput = output.Output(
    name="point sum",
    callback=_pointSum,
    otype=(coord.Coord, primitives.Point),
    inputs=[coord.CoordParameter("point1"), coord.CoordParameter("point2")],
    params=[parameter.FloatParameter("a", default=1.0),
            parameter.FloatParameter("b", default=1.0)]
    )

#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#

# Take the difference between two outputs.

def _difference(mesh, elements, coords, minuend, subtrahend):
    minuends = minuend.evaluate(mesh, elements, coords)
    subtrahends = subtrahend.evaluate(mesh, elements, coords)
    return [x-y for x,y in itertools.izip(minuends, subtrahends)]

def _difference_shortrepr(self):
    return "(%s-%s)" % (self.resolveAlias('minuend').value.shortrepr(),
                      self.resolveAlias('subtrahend').value.shortrepr())

def _difference_instancefn(self):
    minuend = self.resolveAlias('minuend').value
    if minuend is None:
        return
    return minuend.outputInstance()


ScalarDifferenceOutput = output.Output(
    name="difference",
    callback=_difference,
    otype=outputval.ScalarOutputValPtr,
    instancefn = _difference_instancefn,
    column_names=single_column_name,
    # The minuend and subtrahend are *parameters*, not inputs, so that
    # they can be specified by the user at run time.
    params=[
        output.ScalarOutputParameter(
            'minuend',
            tip='The quantity from which the subtrahend is subtracted.'),
        output.ScalarOutputParameter(
            'subtrahend',
            tip='The quantity to subtract from the minuend.')],
    srepr=_difference_shortrepr,
    tip="Compute the difference between two quantities.")

# It's important that the ordering parameter for
# ScalarDifferenceOutput and AggregateDifferenceOutput be greater than
# the ordering for at least one other Output in each category.
# Putting the difference outputs first in the list leads to infinite
# recursion when initializing Output widgets.

output.defineScalarOutput('Difference', ScalarDifferenceOutput, ordering=1000)

def _aggdiff_column_names(self):
    sr = self.shortrepr()
    inst = self.outputInstance()
    if inst.dim() == 1:
        return [sr]
    it = inst.getIterator()
    names = []
    while not it.end():
        names.append("%s[%s]" % (sr, it.shortstring()))
        it.next()
    return names

AggregateDifferenceOutput = output.Output(
    name="difference",
    callback=_difference,
    otype=outputval.OutputValPtr,
    srepr=_difference_shortrepr,
    instancefn=_difference_instancefn,
    column_names=_aggdiff_column_names,
    params=[
        output.AggregateOutputParameter('minuend',
            tip='The quantity from which the subtrahend is subtracted.'),
        output.AggregateOutputParameter(
            'subtrahend',
            tip='The quantity to subtract from the minuend.')],
    tip="Compute the difference between two quantities.")

output.defineAggregateOutput('Difference', AggregateDifferenceOutput,
                             ordering=1000)


#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#

# The Concatenate Output allows two Outputs to be printed on the same
# line of the output file.  Its value type is the
# ConcatenatedOutputVal class, which defines a bunch of arithmetic
# operations that it just passes through to the OutputVals that it's
# concatenating.  ConcatenatedOutputVal is itself *not* an OutputVal.
# Maybe it should be, but that would mean defining it in C++.

## TODO: Allow more than two outputs to be concatenated, so that it's
## not necesary to nest the concatenations.  We'll need a Parameter
## class for multiple Outputs, and a widget for it.

## TODO: Allow concatenation of ScalarOutputs as well as
## AggregateOutputs?  (Better would be to get rid of the distinction
## between them, as in OOF3D.)  Simply changing
## AggregateOutputParameter to ValueOutputParameter in
## ConcatenateOutput's params doesn't work, because
## ValueOutputParameter's widget needs to find an EnumWidget for
## Scalar/Aggregate.

class ConcatenatedOutputVal(object):
    def __init__(self, *args):
        # args is a tuple of OutputVals
        self.args = args
    def value_list(self):
        # Convert each OutputVal to a list of floats and concatenate them
        vals = reduce(lambda a,b: a+b, [v.value_list() for v in self.args])
        return vals
    def dim(self):
        return sum(a.dim() for a in self.args())
    def zero(self):
        return ConcatenatedOutputVal(*(v.zero() for v in self.args))
    def one(self):
        return ConcatenatedOutputVal(*(v.one() for v in self.args))
    def value(self):
        return self.value_list()
    def __mul__(self, x):
        return ConcatenatedOutputVal(*(x*arg for arg in self.args))
    def __rmul__(self, x):
        return self.__mul__(x)
    def __add__(self, o):
        assert isinstance(o, ConcatenatedOutputVal)
        return ConcatenatedOutputVal(*(x+y for x,y, in zip(self.args, o.args)))
    def __sub__(self, o):
        assert isinstance(o, ConcatenatedOutputVal)
        return ConcatenatedOutputVal(*(x-y for x,y, in zip(self.args, o.args)))
    def __pow__(self, x):
        return ConcatenatedOutputVal(*(v**x for v in self.args))
    def __div__(self, x):
        return ConcatenatedOutputVal(*(v/x for v in self.args))
    def clone(self):
        return ConcatenatedOutputVal(*(v.clone() for v in self.args))
    def component_square(self):
        return ConcatenatedOutputVal(*(v.component_square() for v in self.args))
    def component_sqrt(self):
        return ConcatenatedOutputVal(*(v.component_sqrt() for v in self.args))
    def component_abs(self):
        return ConcatenatedOutputVal(*(v.component_abs() for v in self.args))

    def expandRange(self, vmin, vmax):
        mins = []
        maxes = []
        for a,vmn,vmx in zip(self.args, vmin, vmax):
            mn, mx = a.expandRange(vmn, vmx)
            mins.append(mn)
            maxes.append(mx)
        return mins, maxes
    def initRange(self):
        return [a.initRange() for a in self.args]

def _concatenate(mesh, elements, coords, first, second):
    firsts = first.evaluate(mesh, elements, coords)
    seconds = second.evaluate(mesh, elements, coords)
    return [ConcatenatedOutputVal(f, s)
            for f,s in itertools.izip(firsts, seconds)]

def _concatenate_shortrepr(self):
    return "%s and %s" % (self.resolveAlias('first').value.shortrepr(),
                          self.resolveAlias('second').value.shortrepr())

def _concatenate_instancefn(self):
    first = self.resolveAlias('first').value
    second = self.resolveAlias('second').value
    if first is None or second is None:
        return
    return ConcatenatedOutputVal(first.outputInstance(),
                                 second.outputInstance())

def _concatenate_columnnames(self):
    f = self.resolveAlias('first').value
    s = self.resolveAlias('second').value
    return f.column_names(f) + s.column_names(s)

def _concatenate_allowsArithmetic(self):
    f = self.resolveAlias('first').value
    s = self.resolveAlias('second').value
    return (f is not None and s is not None and
            f.allowsArithmetic() and s.allowsArithmetic())

ConcatenateOutput = output.Output(
    name="concatenate",
    callback=_concatenate,
    otype=ConcatenatedOutputVal,
    srepr=_concatenate_shortrepr,
    instancefn=_concatenate_instancefn,
    column_names=_concatenate_columnnames,
    arithmeticFilter=_concatenate_allowsArithmetic,
    params=[
        output.AggregateOutputParameter('first'),
        output.AggregateOutputParameter('second')],
    tip="Print multiple quantities on each line")

output.defineAggregateOutput('Concatenate', ConcatenateOutput,
                             ordering=1001)

#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#

# Scale values to lie between 0 and 1.

def _rescaleOutput(mesh, elements, coords, minimum, maximum, inputdata):
    minval = min(inputdata)
    maxval = max(inputdata)
    # TODO OPT: Doing this math in python on ScalarOutputVals is
    # inefficient.  Can it be done in C++ instead?  This is a low
    # priority until this function is actually used.
    def rescale(x, mn=minval, mx=maxval, tmin=minimum, tmax=maximum):
        if mx == mn:
            return 0.5*(tmin + tmax)    # arbitrary
        return tmin + (tmax-tmin)*(x-mn)/(mx-mn)
    ## TODO: Use imap instead of map.  See comment at top of file.
    return map(rescale, inputdata)

def _rescale_instancefn(self):
    return self.findInput("inputdata").instancefn()

def _rescale_shortrepr(self):
    inrepr = self.findInput('inputdata').value.shortrepr()
    min = self.resolveAlias('minimum').value
    max = self.resolveAlias('maximum').value
    return "Rescaled(%s, %s, %s)" % (inrepr, min, max)

RescaleOutput = output.Output(
    name="rescale",
    otype=outputval.ScalarOutputValPtr,
    callback=_rescaleOutput,
    instancefn=_rescale_instancefn,
    srepr=_rescale_shortrepr,
    column_names=single_column_name,
    params=[parameter.FloatParameter("minimum", default=0.),
            parameter.FloatParameter("maximum", default=1.)],
    inputs = [output.ScalarOutputParameter("inputdata")]
    )

#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#=-=#

# Multiply by a scalar

def _multOutput(mesh, elements, coords, values, factor, scalee):
    return [factor*x for x in scalee]

def _mult_instancefn(self):
    return self.findInput("scalee").instancefn()
                 

ScalarMultiplyOutput = output.Output(
    name="scalar multiply",
    callback=_multOutput,
    otype = outputval.OutputValPtr,
    instancefn=_mult_instancefn,
    params=[parameter.FloatParameter("factor", default=1.)],
    inputs=[outputval.OutputValParameter('scalee')],
    tip="Multiply the input by a constant scalar factor.")

NegateOutput = ScalarMultiplyOutput.clone(
    name="negate",
    params=dict(factor=-1),
    tip="Multiply the input by -1.")

