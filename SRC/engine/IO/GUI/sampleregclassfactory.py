# -*- python -*-

# This software was produced by NIST, an agency of the U.S. government,
# and by statute is not subject to copyright in the United States.
# Recipients of this software assume all responsibilities associated
# with its operation, modification and maintenance. However, to
# facilitate maintenance we ask that before distributing modified
# versions of this software, you first contact the authors at
# oof_manager@nist.gov. 

from ooflib.SWIG.common import switchboard
from ooflib.common import debug
from ooflib.common.IO.GUI import regclassfactory
from ooflib.engine import analysissample
from ooflib.engine import analysisdomain
from ooflib.engine.IO import analyze

# A special registered class factory for the sampling widget.  It
# notices when the domain and operation change, which can affect which
# samplings are allowed.

class SampleRCF(regclassfactory.RegisteredClassFactory):
    def __init__(self, obj=None, title=None, callback=None,
                 fill=0, expand=0, scope=None, name=None, widgetdict={},
                 domainClass=None, operationClass=None,
                 *args, **kwargs):
        self.sample_types = []
        self.directness = False

        regclassfactory.RegisteredClassFactory.__init__(
            self, analysissample.SampleSet.registry, obj,
            title, callback, fill, expand, scope,
            name, widgetdict, *args, **kwargs)

        self.sbcallbacks = []

        # If the domainClass arg is specified, then this widget will
        # only be used on a particular type of domain, and it won't be
        # necessary to synchronize with a Domain widget.
        if domainClass is None:
            # Find widget to synch with.
            self.domainWidget = self.findWidget(
                lambda w: (isinstance(w, regclassfactory.RegisteredClassFactory)
                           and w.registry is analysisdomain.Domain.registry))
            assert self.domainWidget is not None
            self.newDomain()
            self.sbcallbacks.append(
                switchboard.requestCallbackMain(self.domainWidget,
                                                self.domainCB))
        else:                   # domainClass was specified
            # Find the registration for the class
            ## TODO: Use domainClass.getRegistration instead of looping
            for reg in analysisdomain.Domain.registry:
                if reg.subclass is domainClass:
                    self.sample_types = reg.sample_types

        # Ditto for the operationClass.
        if operationClass is None:
            self.operationWidget = self.findWidget(
                lambda w: (isinstance(w, regclassfactory.RegisteredClassFactory)
                           and w.registry is analyze.DataOperation.registry))
            assert self.operationWidget is not None
            self.newOperation()
            self.sbcallbacks.append(
                switchboard.requestCallbackMain(self.operationWidget,
                                                self.operationCB))
        else: # operationClass is not None, set directness accordingly
            ## TODO: Use operationClass.getRegistration instead of looping
            for reg in analyze.DataOperation.registry:
                if reg.subclass is operationClass:
                    self.directness = reg.direct
                    break
        self.refresh(obj)

    def cleanUp(self):
        map(switchboard.removeCallback, self.sbcallbacks)
        regclassfactory.RegisteredClassFactory.cleanUp(self)
        
    # The "self.directness" reflects whether or not the output
    # operation requires direct output (i.e. is not statistical),
    # and self.sample_types reflects the available sample types
    # from the domain.
    #   Choose a sampling whose sample type is in the list, and which
    # is direct if the operation is direct.  If the operation
    # is not direct, then the sampling may or may not be direct, it's
    # allowed either way.  (This means you can average over points, also.)
    def includeRegistration(self, registration):
        return (registration.sample_type in self.sample_types
                and registration.direct == self.directness)

    def newDomain(self):
        domain_reg = self.domainWidget.getRegistration()
        if domain_reg:
            self.sample_types = domain_reg.sample_types
        else:
            self.sample_types = []

    def domainCB(self, *args):
        # The domain has changed, so the allowed samplings may have
        # changed.
        self.newDomain()
        self.refresh()

    def newOperation(self):
        op_reg = self.operationWidget.getRegistration()
        if op_reg:
            self.directness = op_reg.direct
        else:
            self.directness = False

    def operationCB(self, *args):
        # The output operation has changed, so
        # the allowed samplings may have changed.
        self.newOperation()
        self.refresh()

def _SamplingParameter_makeWidget(self, scope=None):
    return SampleRCF(self.value, name=self.name, scope=scope)

analysissample.SamplingParameter.makeWidget = _SamplingParameter_makeWidget
