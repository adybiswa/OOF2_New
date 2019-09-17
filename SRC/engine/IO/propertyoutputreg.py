# -*- python -*-

# This software was produced by NIST, an agency of the U.S. government,
# and by statute is not subject to copyright in the United States.
# Recipients of this software assume all responsibilities associated
# with its operation, modification and maintenance. However, to
# facilitate maintenance we ask that before distributing modified
# versions of this software, you first contact the authors at
# oof_manager@nist.gov.

from ooflib.SWIG.engine import corientation
from ooflib.SWIG.engine import outputval
from ooflib.SWIG.engine import symmmatrix
from ooflib.SWIG.engine.IO import propertyoutput
from ooflib.common import debug
from ooflib.common import enum
from ooflib.engine.IO import orientationmatrix
from ooflib.engine.IO import output
from ooflib.engine.IO import outputClones


# The PropertyOutputRegistration subclasses create an Output object
# for each registered PropertyOutput.  This bridges the gap between
# the C++ PropertyOutputs and the more general Python Outputs.

# This code is not in propertyoutput.spy because putting it there
# creates import loops.

#=--=##=--=##=--=##=--=##=--=##=--=##=--=##=--=##=--=##=--=##=--=##=--=#
    
# Scalar outputs

class ScalarPropertyOutputRegistration(propertyoutput.PORegBase):
    def __init__(self, name, initializer=None, parameters=[], ordering=0,
                 srepr=None, tip=None, discussion=None):
        propertyoutput.PropertyOutputRegistration.__init__(
            self, name,
            initializer or propertyoutput.ScalarPropertyOutputInit())
        op = output.Output(name=name,
                           callback=self.opfunc,
                           otype=outputval.ScalarOutputValPtr,
                           instancefn=outputClones.scalar_instancefn,
                           column_names=outputClones.single_column_name,
                           params=parameters,
                           srepr=srepr, tip=tip, discussion=discussion)
        output.defineScalarOutput(name, op, ordering=ordering)
        output.defineAggregateOutput(name, op, ordering=ordering)

#     def convert(self, results): # convert from ScalarOutputVal to Float
#         return [r.value() for r in results]
    
#=--=##=--=##=--=##=--=##=--=##=--=##=--=##=--=##=--=##=--=##=--=##=--=#

# ThreeVector outputs
## TODO 3D: These should add themselves as "Value" outputs, and there
## should be an "Invariant" output, also, since 3-vectors have a
## magnitude.  srepr's and column_name's need to be adjusted/provided.
## None of this is implemented yet because there are no
## ThreeVectorPropertyOutputs to test it on.

class ThreeVectorPropertyOutputRegistration(propertyoutput.PORegBase):
    def __init__(self, name, initializer=None, parameters=[], ordering=0,
                 srepr=None, tip=None, discussion=None):
        propertyoutput.PropertyOutputRegistration.__init__(
            self, name,
            initializer or propertyoutput.ThreeVectorPropertyOutputInit())
        op = output.Output(name=name,
                           callback=self.opfunc,
                           otype=outputval.OutputValPtr,
                           instancefn=outputClones.vector_instancefn,
                           params=parameters,
                           srepr=srepr, tip=tip,
                           discussion=discussion)
        output.defineAggregateOutput(name, op, ordering=ordering)

        compout = outputClones.ComponentOutput.clone(
            name=name+" Component",
            tip='Compute components of %s' % name,
            discussion=
            """
            <para>Compute the specified component of <link
            linkend='Output-%s'>%s</link> on a &mesh;.</para>
            """
            % (name, name))
        compout.connect('field', op)
        for param in parameters:
            compout.aliasParam('field:'+param.name, param.name)
        output.defineScalarOutput(name+":Component", compout, ordering=ordering)
        

#=--=##=--=##=--=##=--=##=--=##=--=##=--=##=--=##=--=##=--=##=--=##=--=#

def _symmmatrix3_instancefn(self):
    return symmmatrix.SymmMatrix3(0.,0.,0.,0.,0.,0.)

def _symmmatrix3_column_names(self):
    sr = self.shortrepr()
    names = []
    it = self.outputInstance().getIterator()
    while not it.end():
        names.append("%s[%s]" % (sr, it.shortstring()))
        it.next()
    return names

class SymmMatrix3PropertyOutputRegistration(propertyoutput.PORegBase):
    def __init__(self, name, initializer=None, parameters=[], ordering=0,
                 srepr=None, tip=None, discussion=None):
        propertyoutput.PropertyOutputRegistration.__init__(
            self, name,
            initializer or symmmatrix.SymmMatrix3PropertyOutputInit())
        op = output.Output(name=name,
                           callback=self.opfunc,
                           otype=outputval.OutputValPtr,
                           instancefn=_symmmatrix3_instancefn,
                           srepr=srepr,
                           column_names=_symmmatrix3_column_names,
                           params=parameters,
                           tip=tip, discussion=discussion)
        output.defineAggregateOutput(name+":Value", op, ordering=ordering)

        def comprepr(s):
            comp = s.resolveAlias("component").value
            # We have to pass s to op.shortrepr so that the shortrepr
            # will be computed for the actual Output, not the Output
            # defined above.  The actual output will be a clone of the
            # one defined there.
            return "%s[%s]" % (op.shortrepr(s), comp)

        compout = outputClones.ComponentOutput.clone(
            name=name+" Component",
            tip='Compute components of %s' % name,
            srepr=comprepr,
            discussion=
            """
            <para>Compute the specified component of %s on a &mesh;.</para>
            """
            % name)
        compout.connect('field', op)
        for param in parameters:
            compout.aliasParam('field:' + param.name, param.name)
        output.defineScalarOutput(name+":Component", compout, ordering=ordering)

        def invariantrepr(s):
            invariant = s.resolveAlias("invariant").value.shortrepr()
            # See comment above about op.shortrepr(s)
            return "%s(%s)" % (invariant, op.shortrepr(s))
        
        invout = outputClones.InvariantOutput.clone(
            name=name+" Invariant",
            srepr=invariantrepr,
            tip='Compute invariants of %s' % name,
            discussion="""
            <para>Compute the specified invariant of %s on a &mesh;.</para>
            """
            % name)
        invout.connect('field', op)
        for param in parameters:
            invout.aliasParam('field:' + param.name, param.name)
        output.defineScalarOutput(name+":Invariant", invout, ordering=ordering)
        output.defineAggregateOutput(name+":Invariant", invout, 
                                     ordering=ordering)


#=--=##=--=##=--=##=--=##=--=##=--=##=--=##=--=##=--=##=--=##=--=##=--=#

def _orientation_instancefn(self):
    fmt = self.findParam("format").value
    reg = orientationmatrix.getRegistrationForName(fmt)
    return reg()

def _orientation_column_names(self):
    fmt = self.findParam("format").value
    reg = orientationmatrix.Orientation.getRegistrationForName(fmt)
    if reg:
        return [p.name for p in reg.params]

def _orientation_srepr(self):
    fmt = self.findParam("format").value # an Enum
    return fmt.name

class OrientationPropertyOutputRegistration(propertyoutput.PORegBase):
    def __init__(self, name, initializer=None, parameters=[], ordering=0,
                 tip=None, discussion=None):
        param = enum.EnumParameter(
            "format",
            orientationmatrix.OrientationEnum,
            tip="How to print the orientation.")
        propertyoutput.PropertyOutputRegistration.__init__(
            self, name,
            initializer or corientation.OrientationPropertyOutputInit())
        op = output.Output(name=name,
                           callback=self.opfunc,
                           otype=corientation.COrientationPtr,
                           instancefn=_orientation_instancefn,
                           srepr=_orientation_srepr,
                           column_names=_orientation_column_names,
                           params=[param] + parameters,
                           tip=tip, discussion=discussion)
        output.defineAggregateOutput(name, op, ordering=ordering)
                           
#=--=##=--=##=--=##=--=##=--=##=--=##=--=##=--=##=--=##=--=##=--=##=--=#

# ModulusPropertyOutputs need to have a "components" parameter that
# lists the components to be printed and a "frame" parameter that says
# whether the components should be printed in the lab frame or the
# crystal frame.  The type of the "components" parameter depends on
# the type of the modulus.

def _modulus_instance_fn(self):
    listarg = self.findParam("components").value
    return outputval.ListOutputVal(len(listarg))

def _modulus_srepr(self):
    listarg = self.findParam("components").value
    return "%s(%s)" % (self.name, str(listarg)[1:-1])

def _modulus_column_names(self):
    listarg = self.findParam("components").value
    return ["%s_%s"%(self.symbol, component) for component in listarg]

class ModulusPropertyOutputRegistration(propertyoutput.PORegBase):
    def __init__(self, name, symbol, initializer=None, parameters=[],
                 ordering=1, tip=None, discussion=None):
        propertyoutput.PropertyOutputRegistration.__init__(
            self, name,
            initializer or propertyoutput.ListOutputInit())
        op = output.Output(name=name,
                           callback=self.opfunc,
                           otype=outputval.ListOutputValPtr,
                           instancefn=_modulus_instance_fn,
                           srepr=_modulus_srepr,
                           column_names=_modulus_column_names,
                           params=parameters,
                           tip=tip, discussion=discussion,
                           symbol=symbol # C for elastic modulus, etc. For srepr
        )
        output.defineAggregateOutput(name, op, ordering=ordering)
