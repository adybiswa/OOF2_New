# -*- python -*-

# This software was produced by NIST, an agency of the U.S. government,
# and by statute is not subject to copyright in the United States.
# Recipients of this software assume all responsibilities associated
# with its operation, modification and maintenance. However, to
# facilitate maintenance we ask that before distributing modified
# versions of this software, you first contact the authors at
# oof_manager@nist.gov. 

from ooflib.SWIG.common import switchboard
from ooflib.SWIG.engine import ooferror2
from ooflib.common import debug
from ooflib.common import labeltree
from ooflib.common import utils
from ooflib.common.IO import placeholder
from ooflib.common.IO.GUI import chooser
from ooflib.common.IO.GUI import gtklogger
from ooflib.common.IO.GUI import gtkutils
from ooflib.common.IO.GUI import oofGUI
from ooflib.common.IO.GUI import parameterwidgets
from ooflib.common.IO.GUI import regclassfactory
from ooflib.common.IO.GUI import tooltips
from ooflib.common.IO.GUI import whowidget
from ooflib.engine import analysisdomain
from ooflib.engine import namedanalysis
from ooflib.engine.IO import analyze
from ooflib.engine.IO import analyzemenu
from ooflib.engine.IO.GUI import outputdestinationwidget
from ooflib.engine.IO.GUI import outputwidget
from ooflib.engine.IO.GUI import sampleregclassfactory
import ooflib.engine.mesh

import gtk


# A page on which various aspects of the solved mesh can be queried --
# cross-section and statistical outputs will live here, with the
# ability to be put into files, and so forth. 

# Base class for AnalyzePage and BoundaryAnalysisPage.

class BaseAnalysisPage(oofGUI.MainPage):
    def buildBottomRow(self, mainbox):
        # Build the bottom row of widgets, containing the named
        # analysis buttons, the Destination chooser, and the Go
        # button.
        # Box along the bottom of the page, containing Named Analyses,
        # Destination, and Go.
        hbox = gtk.HBox()
        hbox.set_homogeneous(True)
        mainbox.pack_start(hbox, expand=0, fill=0, padding=3)

        # Named Analyses
        nameframe = gtk.Frame("Named Analyses")
        gtklogger.setWidgetName(nameframe, 'Name')
        nameframe.set_shadow_type(gtk.SHADOW_IN)
        hbox.pack_start(nameframe, expand=1, fill=1, padding=3)
        namebox = gtk.VBox(spacing=2)
        namebox.set_border_width(1)
        nameframe.add(namebox)
        
        # The namedOps_button isn't used as a button, really.  It's
        # just a place to click to bring up the menu of named analysis
        # operations.  There isn't room in the frame to make separate
        # buttons for all the operations and still display the name of
        # the current analysis, if any.
        self.namedOps_button = gtk.Button("Create/Delete/etc...")
        gtklogger.setWidgetName(self.namedOps_button, "Operations")
        namebox.pack_start(self.namedOps_button, expand=1, fill=1)
        gtklogger.connect(self.namedOps_button, 'button-press-event', 
                          self.namedOpsCB)
        # Construct the menu of operations.
        self.namedOpsPopUp = gtk.Menu()
        gtklogger.newTopLevelWidget(self.namedOpsPopUp, self.menuWidgetName)
        self.namedOpsPopUp.set_screen(self.namedOps_button.get_screen())
        gtklogger.connect_passive(self.namedOpsPopUp, 'deactivate')
        self.namedOpsMenuItems = {}
        for position, (name, callback, tip) in enumerate([
                ('Create', self.createCB, "Create a new named analysis."),
                ('Save', self.savenamedCB, "Save named analysis definitions."),
                ('Delete', self.deleteCB, "Delete a named analysis.")]):
            menuitem = gtk.MenuItem()
            self.namedOpsMenuItems[name] = menuitem
            gtklogger.setWidgetName(menuitem, name)
            label = gtk.Label(name + "...")
            tooltips.set_tooltip_text(label, tip)
            menuitem.add(label)
            self.namedOpsPopUp.insert(menuitem, position)
            gtklogger.connect(menuitem, 'activate', callback)
        self.namedOpsPopUp.show_all()
        # Display the name of the current analysis, if it has one.
        hbox4 = gtk.HBox()
        namebox.pack_start(hbox4, expand=0, fill=0)
        hbox4.pack_start(gtk.Label("Current:"), expand=0, fill=0)
        self.namedAnalysisChooser = chooser.ChooserWidget(
            [], callback=self.retrieveCB, name="Retrieve")
        hbox4.pack_start(self.namedAnalysisChooser.gtk, expand=1, fill=1)

        # reduce no. of calls to setNamedAnalysisChooser
        self.suppressRetrievalLoop = False

        # Destination
        destinationframe = gtk.Frame("Destination")
        destinationframe.set_shadow_type(gtk.SHADOW_IN)
        hbox.pack_start(destinationframe, expand=1, fill=1, padding=3)
        destbox = gtk.HBox()
        destbox.set_border_width(1)
        destinationframe.add(destbox)

        self.destwidget = outputdestinationwidget.TextDestinationWidget(
            name="Destination", framed=False)
        destbox.pack_start(self.destwidget.gtk, expand=1, fill=1, padding=2)
        
        # Go button
        self.go_button = gtkutils.StockButton(gtk.STOCK_EXECUTE, "Go")
        self.go_button.set_border_width(2)
        gtklogger.setWidgetName(self.go_button, 'Go')
        gtklogger.connect(self.go_button, "clicked", self.go_buttonCB)
        tooltips.set_tooltip_text(self.go_button,
                             "Send the output to the destination.")
        hbox.pack_start(self.go_button, fill=1, expand=1, padding=2)


    def namedOpsCB(self, gtkbutton, event):
        self.namedOpsPopUp.popup(None, None, None, event.button, event.time)
    
    def sensitizeBottomRow(self, createOK, namedOK):
        self.namedOpsMenuItems['Create'].set_sensitive(createOK)
        self.namedOpsMenuItems['Delete'].set_sensitive(namedOK)
        self.namedOpsMenuItems['Save'].set_sensitive(namedOK)

#=--=##=--=##=--=##=--=##=--=##=--=##=--=##=--=##=--=##=--=##=--=##=--=#

# DataOperationFactory is a RegisteredClassFactory that only lists the
# operations consistent with the setting of the Scalar/Aggregate
# buttons on the Analysis page.
class DataOperationFactory(regclassfactory.RegisteredClassFactory):
    def __init__(self, page, *args, **kwargs):
        self.page = page
        regclassfactory.RegisteredClassFactory.__init__(self, *args, **kwargs)
    def includeRegistration(self, registration):
        return registration.acceptsOutput(self.page.getOutput())
        
#=--=##=--=##=--=##=--=##=--=##=--=##=--=##=--=##=--=##=--=##=--=##=--=#

pshrink = False # can the HPaneds shrink below the size of their contents?

class AnalyzePage(BaseAnalysisPage):
    def __init__(self):
        oofGUI.MainPage.__init__(
            self, name="Analysis", ordering=259,
            tip="Query the mesh, examine fields and fluxes.")
        
        self.timeparam = placeholder.TimeParameter('time', value=0.0)

        mainbox = gtk.VBox()
        self.gtk.add(mainbox)

        align = gtk.Alignment(xalign=0.5)
        mainbox.pack_start(align, expand=0, fill=0)
        centerbox = gtk.HBox(spacing=3)
        align.add(centerbox)
        self.meshwidget = whowidget.WhoWidget(ooflib.engine.mesh.meshes,
                                              scope=self)
        # The mesh widget callback is not required, because the field
        # and flux widgets in the "output" widget (which are members
        # of a parameter table, which is a component of the
        # OutputWidget) are context-sensitive and update themselves
        # automatically.
        label = gtk.Label("Microstructure=")
        label.set_alignment(1.0, 0.5)
        centerbox.pack_start(label, expand=0, fill=0)
        centerbox.pack_start(self.meshwidget.gtk[0], expand=0, fill=0)
        label = gtk.Label("Skeleton=")
        label.set_alignment(1.0, 0.5)
        centerbox.pack_start(label, expand=0, fill=0)
        centerbox.pack_start(self.meshwidget.gtk[1], expand=0, fill=0)
        label = gtk.Label("Mesh=")
        label.set_alignment(1.0, 0.5)
        centerbox.pack_start(label, expand=0, fill=0)
        centerbox.pack_start(self.meshwidget.gtk[2], expand=0, fill=0)

        align = gtk.Alignment(xalign=0.5)
        mainbox.pack_start(align, expand=0, fill=0)
        centerbox = gtk.HBox(spacing=3)
        align.add(centerbox)
        self.timeWidget = self.timeparam.makeWidget(scope=self)
        centerbox.pack_start(gtk.Label("Time:"), expand=0, fill=0)
        centerbox.pack_start(self.timeWidget.gtk, expand=0, fill=0)

        mainvpane = gtk.VPaned()
        mainbox.pack_start(mainvpane, expand=1, fill=1)
        self.topPane = gtk.HPaned()
        gtklogger.setWidgetName(self.topPane, 'top')
        mainvpane.pack1(self.topPane, resize=1, shrink=0)
        self.btmPane = gtk.HPaned()
        gtklogger.setWidgetName(self.btmPane, 'bottom')
        mainvpane.pack2(self.btmPane, resize=1, shrink=0)
        # The four panes (Output, Domain, Operation, and Sampling) are
        # contained in the top and bottom HPaneds.  The dividers
        # between the sub panes are synchronized with each other.
        # Since Paneds don't have a dedicated signal indicating that
        # their dividers have been moved, we have to use the the
        # generic 'notify' signal.
        self.paneSignals = {
            self.topPane : gtklogger.connect(self.topPane,
                                             'notify::position', 
                                             self.paneMovedCB,
                                             self.btmPane),
            self.btmPane : gtklogger.connect(self.btmPane,
                                             'notify::position',
                                             self.paneMovedCB,
                                             self.topPane)
            }

        self.outputframe = gtk.Frame(label="Output")
        self.outputframe.set_shadow_type(gtk.SHADOW_IN)
        output_scroll = gtk.ScrolledWindow()
        gtklogger.logScrollBars(output_scroll, "Output")
        output_scroll.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        self.outputframe.add(output_scroll)
        output_box = gtk.VBox()
        output_type_selector_box = gtk.HBox()
        output_box.pack_start(output_type_selector_box, expand=0, fill=0)

        self.scalar_output_button = gtk.RadioButton(label="Scalar")
        gtklogger.setWidgetName(self.scalar_output_button, 'ScalarMode')
        self.aggregate_output_button = gtk.RadioButton(
            group=self.scalar_output_button, label="Aggregate")
        gtklogger.setWidgetName(self.aggregate_output_button, 'AggregateMode')
        output_type_selector_box.pack_start(self.scalar_output_button,
                                            expand=0, fill=0)
        output_type_selector_box.pack_start(self.aggregate_output_button,
                                            expand=0, fill=0)
        self.scalarSignal = gtklogger.connect(self.scalar_output_button,
                                              "clicked",
                                              self.scalar_button_CB)
        self.aggregateSignal = gtklogger.connect(self.aggregate_output_button,
                                                 'clicked',
                                                 self.scalar_button_CB)

        # Both aggregate and scalar widgets are built here, and they
        # are switched by show/hide.
        ## TODO: Use the ValueOutputWidget here.  In incorporates both
        ## the aggregate and scalar widgets.
        self.scalar_output_button.set_active(1)
        self.scalar_output_obj = outputwidget.ScalarOutputParameterWidget(
            None, scope=self, name="Scalar")
        self.aggregate_output_obj = \
                                  outputwidget.AggregateOutputParameterWidget(
            None, scope=self, name="Aggregate")
        
        self.output_obj = self.scalar_output_obj
        output_box.pack_start(self.scalar_output_obj.gtk, expand=0, fill=0)
        output_box.pack_start(self.aggregate_output_obj.gtk, expand=0, fill=0)
        self.aggregate_output_obj.gtk.hide()
        
        output_scroll.add_with_viewport(output_box)
        self.topPane.pack1(self.outputframe, resize=1, shrink=pshrink)

        # Operation
        self.operationframe = gtk.Frame(label="Operation")
        self.operationframe.set_shadow_type(gtk.SHADOW_IN)
        op_scroll = gtk.ScrolledWindow()
        gtklogger.logScrollBars(op_scroll, "Operation")
        op_scroll.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        self.op_obj = DataOperationFactory(self,
            analyze.DataOperation.registry, scope=self, name="OperationRCF",
            callback = self.newOperationCB)
        self.operationframe.add(op_scroll)

        operation_box = gtk.VBox()
        operation_box.pack_start(self.op_obj.gtk, expand=0, fill=0)
        op_scroll.add_with_viewport(operation_box)
        self.btmPane.pack1(self.operationframe, resize=1, shrink=pshrink)

        # Domain
        self.domainframe = gtk.Frame(label="Domain")
        self.domainframe.set_shadow_type(gtk.SHADOW_IN)
        dom_scroll = gtk.ScrolledWindow()
        gtklogger.logScrollBars(dom_scroll, "Domain")
        dom_scroll.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        self.domain_obj = regclassfactory.RegisteredClassFactory(
            analysisdomain.Domain.registry, scope=self, name="DomainRCF",
            callback = self.newDomainCB)
        self.domainframe.add(dom_scroll)
        dom_scroll.add_with_viewport(self.domain_obj.gtk)
        self.topPane.pack2(self.domainframe, resize=1, shrink=pshrink)
        
        # Sampling.  The SampleRCF class uses the WidgetScope
        # mechanism to find the Operation and Domain widgets, so that
        # it can display only the relevant SampleSet classes. 
        self.sampleframe = gtk.Frame(label="Sampling")
        self.sampleframe.set_shadow_type(gtk.SHADOW_IN)
        sam_scroll = gtk.ScrolledWindow()
        gtklogger.logScrollBars(sam_scroll, "Sampling")
        sam_scroll.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        self.sample_obj = sampleregclassfactory.SampleRCF(
            scope=self, name="Sampling", callback=self.newSampleCB)
        self.sampleframe.add(sam_scroll)
        sam_scroll.add_with_viewport(self.sample_obj.gtk)
        self.btmPane.pack2(self.sampleframe, resize=1, shrink=pshrink)

        self.buildBottomRow(mainbox)
        
        # Whenever fields or fluxes are defined or undefined on the
        # mesh, we need to update the output object widget, and
        # possibly invalidate the currently-displayed data, once we
        # start displaying data.

        switchboard.requestCallbackMain(("new who", "Mesh"), self.new_mesh)
        switchboard.requestCallbackMain(("new who", "Skeleton"), self.new_skel)
        
        switchboard.requestCallbackMain(('validity', self.timeWidget),
                                        self.sensitize_widgets)
        switchboard.requestCallbackMain(('validity', self.domain_obj),
                                        self.sensitize_widgets)
        switchboard.requestCallbackMain(('validity', self.op_obj),
                                        self.sensitize_widgets)

        # If the Output changes, the allowed Operations change.
        # updateOperations calls sensitize_widgets too.
        switchboard.requestCallbackMain(self.aggregate_output_obj,
                                        self.updateOperations)
        switchboard.requestCallbackMain(self.scalar_output_obj,
                                        self.updateOperations)

        switchboard.requestCallbackMain(('validity', self.destwidget),
                                        self.sensitize_widgets)
        switchboard.requestCallbackMain("named analyses changed",
                                        self.analysesChanged)
        switchboard.requestCallbackMain("retrieve analysis",
                                        self.retrieve_analysis)
        switchboard.requestCallbackMain("mesh status changed",
                                        self.sensitize_widgets)

        switchboard.requestCallbackMain(self.domain_obj,
                                        self.setNamedAnalysisChooser)
        switchboard.requestCallbackMain(self.op_obj,
                                        self.setNamedAnalysisChooser)
        switchboard.requestCallbackMain(self.scalar_output_obj,
                                        self.setNamedAnalysisChooser)
        switchboard.requestCallbackMain(self.aggregate_output_obj,
                                        self.setNamedAnalysisChooser)
        switchboard.requestCallbackMain(self.sample_obj,
                                        self.setNamedAnalysisChooser)

    menuWidgetName = 'NamedOpsMenu'
    def show(self):
        # show() is called once, when the page is first created.
        # installed(), below, is called each time the user switches to
        # the page.
        debug.mainthreadTest()
        self.gtk.show_all()
        if self.scalar_output_button.get_active():
            self.aggregate_output_obj.gtk.hide()
        else:
            self.scalar_output_obj.gtk.hide()
        
    def installed(self):
        self.sensitize_widgets()
#         # Compute an initial width for the HPanes that is big enough
#         # for the separators to be synchronized without shrinking the
#         # subpanes.
#         outputwidth = self.outputframe.size_request()[0]
#         opertnwidth = self.operationframe.size_request()[0]
#         domainwidth = self.domainframe.size_request()[0]
#         samplewidth = self.sampleframe.size_request()[0]
#         # Size of separator between the panes. Setting it cleverly
#         # doesn't seem to do anything different than setting it to a
#         # guess.
#         gutterwidth = min(
#             self.topPane.size_request()[0] - outputwidth - domainwidth,
#             self.btmPane.size_request()[0] - opertnwidth - samplewidth)
#         debug.fmsg("topPane", self.topPane.size_request(),
#                    "output", outputwidth, "domain", domainwidth)
#         debug.fmsg("btmPane", self.btmPane.size_request(), 
#                    "operation", opertnwidth, "sample", samplewidth)
#         debug.fmsg("gutterwidth=", gutterwidth)
# #         gutterwidth = 5
#         totalwidth = (max(outputwidth, opertnwidth) +
#                       max(domainwidth, samplewidth) +
#                       gutterwidth)
#         debug.fmsg("totalwidth", totalwidth)
#         self.topPane.set_size_request(totalwidth, -1)
#         self.btmPane.set_size_request(totalwidth, -1)
#         self.topPane.set_position(self.btmPane.get_position())

    # Synchronize the top and bottom panes
    synccount = 0               # suppresses recursion 
    def paneMovedCB(self, pane, gparamspec, otherpane):
        self.synccount += 1
        if self.synccount == 1:
            pos = pane.get_position()
            # Try to move the other pane to the position of the one
            # that just moved and triggered this callback.
            self._setPanePos(otherpane, pos)
            # The other pane may not have been able to move far
            # enough.  If it didn't make it, move this pane back to
            # keep them synchronized.  If this causes objectionable
            # flicker, just comment out the following line.
#             self._setPanePos(pane, otherpane.get_position())
        elif self.synccount > 1:
            self.synccount = 0
    def _setPanePos(self, pane, pos):
        self.paneSignals[pane].block()
        try:
            pane.set_position(pos)
        finally:
            self.paneSignals[pane].unblock()
    def currentMeshContext(self):
        meshname = self.meshwidget.get_value()
        try:
            return ooflib.engine.mesh.meshes[meshname]
        except KeyError:
            return None
        
    def sensitize_widgets(self, *args):
        debug.mainthreadTest()
        meshctxt = self.currentMeshContext()
        meshok = meshctxt and not meshctxt.outOfSync()
        go_sensitive = bool(meshok and 
                            self.op_obj.isValid() and
                            self.output_obj.isValid() and 
                            self.destwidget.isValid() and
                            self.domain_obj.isValid() and 
                            self.sample_obj.isValid() and
                            self.timeWidget.isValid())
        self.go_button.set_sensitive(go_sensitive)
        namedok = len(namedanalysis.bulkAnalysisNames()) > 0
        self.sensitizeBottomRow(go_sensitive, namedok)
        self.namedAnalysisChooser.gtk.set_sensitive(namedok)

    def getOutput(self):
        return self.output_obj.get_value()

    def analysesChanged(self, *args):
        self.sensitize_widgets()
        self.setNamedAnalysisChooser()

    # GUI callback for the button that switches the widget.  Also
    # switches "self.output_obj", so it can be mindlessly read by the
    # "go"-button callback.
    def scalar_button_CB(self, gtkobj):
        debug.mainthreadTest()
        # This callback is called when the radio buttons are both set
        # and unset, which means that it's called twice for each user
        # action, which is unnecessary.
        if not gtkobj.get_active():
            return
        if gtkobj is self.scalar_output_button:
            self.output_obj = self.scalar_output_obj
            self.aggregate_output_obj.gtk.hide()
            self.scalar_output_obj.show()
        else:
            self.output_obj = self.aggregate_output_obj
            self.scalar_output_obj.gtk.hide()
            self.aggregate_output_obj.show()
        self.op_obj.refresh()
        self.sensitize_widgets()

    def updateOperations(self, gtkobj):
        self.op_obj.refresh()
        self.sensitize_widgets()

    def scalarMode(self):
        return self.output_obj is self.scalar_output_obj
    def aggregateMode(self):
        return self.output_obj is self.aggregate_output_obj
        
    # Switchboard, ("new who", "Mesh")
    def new_mesh(self, mesh):
        path = labeltree.makePath(mesh)
        self.meshwidget.set_value(path)
        self.sensitize_widgets()

    def new_skel(self, skeleton):       # switchboard ("new who", "Skeleton")
        # Switch automatically to a new Skeleton only if there is no
        # current Mesh.
        if not self.meshwidget.get_value(): # no mesh
            self.meshwidget.set_value(skeleton)

    # Callback from "operation" registered callback.
    def newOperationCB(self, registration):
        self.sensitize_widgets()

    def newDomainCB(self, registration):
        self.sensitize_widgets()

    def newSampleCB(self, registration):
        self.sensitize_widgets()

    #=--=##=--=##=--=##=--=##=--=##=--=##=--=##=--=##=--=##=--=##=--=#

    # Manipulation of named analyses.

    def setNamedAnalysisChooser(self, *args):
        if self.suppressRetrievalLoop:
            return
        # Display the name for the current analysis if the current
        # settings happen to match a named analysis.  Call this
        # whenever anything on the page changes.
        
        self.namedAnalysisChooser.update(['']
                                         + namedanalysis.bulkAnalysisNames())

        # If the get_value calls fail, the widgets aren't in a valid
        # state, and therefore there's no current name.
        # findNamedBulkAnalysis returns "" if it can't find a match.
        try:
            currentname = namedanalysis.findNamedBulkAnalysis(
                self.op_obj.get_value(),
                self.output_obj.get_value(),
                self.domain_obj.get_value(),
                self.sample_obj.get_value())
        except:
            currentname = ""
        self.namedAnalysisChooser.set_state(currentname)
        gtklogger.checkpoint("named analysis chooser set")

    def createCB(self, gtkobj):  # create a named analysis
        menuitem = analyzemenu.namedanalysismenu.Create
        if parameterwidgets.getParameters(menuitem.get_arg('name'),
                                          title='Name an analysis operation',
                                          scope=self):
            menuitem.callWithDefaults(
                operation=self.op_obj.get_value(),
                data=self.output_obj.get_value(),
                domain=self.domain_obj.get_value(),
                sampling=self.sample_obj.get_value())
        
    def deleteCB(self, gtkobj): # delete named analysis
        menuitem = analyzemenu.namedanalysismenu.Delete
        if parameterwidgets.getParameters(menuitem.get_arg('name'), 
                                          title='Delete a named analysis',
                                          scope=self):
            menuitem.callWithDefaults()

    def retrieveCB(self, gtkobj, name): # retrieve named analysis
        if name:                        # can be empty
            menuitem = analyzemenu.namedanalysismenu.RetrieveNamedAnalysis
            menuitem.get_arg('name').value = name
            menuitem.callWithDefaults()

    def retrieve_analysis(self, name): # switchboard "retrieve analysis"
        analysis = namedanalysis.getNamedBulkAnalysis(name)
        self.suppressRetrievalLoop = True
        try:
            self.op_obj.set(analysis.operation, interactive=False)
            if analysis.data.isScalarOutput():
                self.scalar_output_button.set_active(1) # sets output_obj
            elif analysis.data.isAggregateOutput():
                self.aggregate_output_button.set_active(1) # sets output_obj
            else:
                raise ooferror2.ErrPyProgrammingError("Unclassifiable output?")
            self.output_obj.set_value(analysis.data)
            self.domain_obj.set(analysis.domain, interactive=False)
            self.sample_obj.set(analysis.sampling, interactive=False)
        finally:
            self.suppressRetrievalLoop = False
        gtklogger.checkpoint("retrieved named analysis")
        # If this call was triggered by the namedAnalysisChooser,
        # setting the chooser's value is redundant but harmless. If
        # the call was triggered by a script, setting the chooser's
        # value is required.
        self.setNamedAnalysisChooser()

    def savenamedCB(self, gtkobj): # save named analysis defs to a file
        menuitem = analyzemenu.namedanalysismenu.SaveAnalysisDefs
        if parameterwidgets.getParameters(title="Save Analysis Definitions",
                                          ident="SaveAnalysis",
                                          *menuitem.params):
            menuitem.callWithDefaults()

    #=--=##=--=##=--=##=--=##=--=##=--=##=--=##=--=##=--=##=--=##=--=#

    # "Go" button callback -- fill in the basic parameters, and
    # perform the action.
    def go_buttonCB(self, gtkobj):
        op_reg = self.op_obj.get_value()
        regname = op_reg.getRegistration().name()
        menuitem = analyzemenu.ops_menu.getItem(
            utils.space2underscore(regname))

        menuitem.callWithDefaults(mesh=self.meshwidget.get_value(),
                                  time=self.timeWidget.get_value(),
                                  data=self.output_obj.get_value(),
                                  domain=self.domain_obj.get_value(),
                                  sampling=self.sample_obj.get_value(),
                                  destination=self.destwidget.get_value())
        

        
analyzepage = AnalyzePage()
