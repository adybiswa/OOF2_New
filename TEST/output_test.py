# -*- python -*-

# This software was produced by NIST, an agency of the U.S. government,
# and by statute is not subject to copyright in the United States.
# Recipients of this software assume all responsibilities associated
# with its operation, modification and maintenance. However, to
# facilitate maintenance we ask that before distributing modified
# versions of this software, you first contact the authors at
# oof_manager@nist.gov. 

import unittest, os, string, sys
import memorycheck

from UTILS import file_utils
fp_file_compare = file_utils.fp_file_compare
reference_file = file_utils.reference_file
# Flag that says whether to generate missing reference data files.
# Should be false unless you really know what you're doing.
file_utils.generate = True

## TODO: Add tests for all different domain and sampling types.
## Include non-rectangular pixel groups and selections.

class OOF_Output(unittest.TestCase):
    def setUp(self):
        global femesh, cskeleton
        from ooflib.SWIG.engine import femesh, cskeleton
        global cmicrostructure
        from ooflib.SWIG.common import cmicrostructure
        global allWorkers, allWorkerCores
        from ooflib.common.worker import allWorkers, allWorkerCores
        global outputdestination
        from ooflib.engine.IO import outputdestination

    def tearDown(self):
        pass
    
    @memorycheck.check("microstructure")
    def PDFOutput(self):
        from ooflib.common.IO import gfxmanager
        # Load the output mesh, and draw a nice filled contour plot.
        OOF.File.Load.Data(filename=reference_file('output_data',
                                                 'position_mesh'))
        OOF.Windows.Graphics.New()
        OOF.LayerEditor.LayerSet.New(window='Graphics_1')
        OOF.LayerEditor.LayerSet.DisplayedObject(
            category='Mesh', object='microstructure:skeleton:mesh')
        OOF.LayerEditor.LayerSet.Add_Method(
            method=FilledContourDisplay(
            what=getOutput('Field:Component',
                           component='x',
                           field=Displacement),
            where=getOutput('original'),
            min=automatic, max=automatic, levels=11,
            nbins=5, colormap=ThermalMap()))
        OOF.LayerEditor.LayerSet.DisplayedObject(
            category='Microstructure', object='microstructure')
        OOF.LayerEditor.LayerSet.Add_Method(
            method=MicrostructureMaterialDisplay(
                no_material=Gray(value=0.0),
                no_color=RGBColor(red=0.0,green=0.0,blue=1.0)))
        OOF.LayerEditor.LayerSet.Send(window='Graphics_1')
        OOF.Graphics_1.File.Save_Image(filename="test.pdf",overwrite=True)

        # In Python 2.7 and above, the floating point numbers in the
        # comments in the pdf file have short reprs, (eg, 0.6 instead
        # of 0.59999999999999998).  That messes up the character
        # counts later in the file, so we have to use different
        # reference files for different floating point formats.  Check
        # float_repr_style instead of the Python version number
        # because not all platforms support the short reprs.
        try:
            shortform = sys.float_repr_style == 'short'
        except AttributeError:
            shortform = False
        if shortform:
            self.assert_(
                fp_file_compare(
                    'test.pdf', os.path.join('output_data','posmesh-short.pdf'),
                    1.0e-08, comment="%", pdfmode=True) )
        else:
            self.assert_(
                fp_file_compare(
                    'test.pdf', os.path.join('output_data','posmesh.pdf'),
                    1.0e-08, comment="%", pdfmode=True) )
        file_utils.remove('test.pdf')
            
        OOF.Graphics_1.File.Close()
        OOF.Material.Delete(name="material")
        
        
    @memorycheck.check("microstructure")
    def PositionOutputs(self):
        global position_output_args
        tolerance = 1.0e-08
        from ooflib.common import utils
        from ooflib.engine import mesh
        from ooflib.engine.IO import output
        from ooflib.SWIG.engine import mastercoord
        tree = output.positionOutputs
        outputpaths = tree.leafpaths()
        outputnames = [ string.join(x,':') for x in outputpaths ]
        OOF.File.Load.Data(filename=reference_file('output_data',
                                                 'position_mesh'))
        meshobj = mesh.meshes['microstructure:skeleton:mesh'].getObject()
        for name in outputnames:
            try:
                (param_args, results) = position_output_args[name]
            except KeyError:
                print >> sys.stderr,  "No test data for PositionOutput %s." % name
            else:
                outputobj = tree[name].object
                paramhier = outputobj.listAllParametersHierarchically(
                    onlySettable=1)
                params = utils.flatten_all(paramhier)
                # Actually set the settable parameters.
                pdict = {}
                for p in params:
                    pdict[p.name]=param_args[p.name]
                #
                outputclone = outputobj.clone(params=pdict)

                # The "Analyze" menu item doesn't do PositionOutputs,
                # so we do these directly.  Evaluate each element at
                # mastercoord (0,0).

                elset = meshobj.element_iterator()
                reslist = []
                while not elset.end():
                    lmnt = elset.element()
                    reslist += outputclone.evaluate(
                        meshobj, [lmnt],
                        [[mastercoord.MasterCoord(0.0,0.0)]])
                    elset.next()
                for (r1,r2) in zip(reslist, results):
                    self.assert_( (r1-r2)**2 < tolerance )
        del meshobj
        OOF.Material.Delete(name='material')
                
                
    @memorycheck.check("thermms", "electroms", "anisothermms", "electroms2",
                       "electroms2r", "isomesh")
    def outputs(self, treename, tree, args, tolerance):
        from ooflib.common import utils
        from ooflib.engine.IO import analyze

        outputpaths = tree.leafpaths()
        outputnames = [ string.join(x,':') for x in outputpaths ]

        OOF.File.Load.Data(filename=reference_file(
            'output_data', 'thermoelastic.mesh'))
        OOF.File.Load.Data(filename=reference_file(
            'output_data', 'electroelastic.mesh'))
        OOF.File.Load.Data(filename=reference_file(
            'output_data', 'anisothermoelastic.mesh'))

        # isotropic.mesh contains the all of the isotropic material
        # properties.
        OOF.File.Load.Data(filename=reference_file(
            'output_data', 'isotropic.mesh'))

        # The first electroelastic.mesh doesn't have a piezoelectric
        # coefficient that's useful for testing the Materials Constant
        # output, so these were added. 
        OOF.File.Load.Data(filename=reference_file(
            'output_data', 'electroelastic2.mesh'))
        OOF.File.Load.Data(filename=reference_file(
            'output_data', 'electroelastic2rotated.mesh'))
        
        for name in outputnames:
            try:
                testlist = args[name]
            except KeyError:
                print >> sys.stderr, "No test data for %s %s." % (treename,
                                                                  name)
            else:
                outputobj = tree[name].object
                paramhier = outputobj.listAllParametersHierarchically(
                    onlySettable=1)
                output_params = utils.flatten_all(paramhier)

                print >> sys.stderr, \
                      "Running test for %s %s." % (treename, name)
                
                for test in testlist:
                    meshname = test[0]
                    test_argdict = test[1]
                    comp_file = test[2]

                    output_param_dict = {}
                    for p in output_params:
                        output_param_dict[p.name]=test_argdict[p.name]

                    outputclone = outputobj.clone(params=output_param_dict)
                    
                    OOF.Mesh.Analyze.Direct_Output(
                        data=outputclone,
                        mesh=meshname,
                        time=latest,
                        domain=EntireMesh(),
                        sampling=GridSampleSet(x_points=10, y_points=10,
                                               show_x=True, show_y=True),
                        destination=OutputStream(filename='test.dat', mode='w')
                        )

                    outputdestination.forgetTextOutputStreams()

                    # Compare test.dat with the right comparison file.
                    print >> sys.stderr,  "Comparing test.dat to", \
                          reference_file('output_data', comp_file)
                    self.assert_(
                        fp_file_compare('test.dat',
                                        os.path.join('output_data', comp_file),
                                        tolerance ) )

                    file_utils.remove('test.dat')

                    # Check the average value of the output. As well
                    # as testing the averaging operation, it tests
                    # that constraints that are only applied weakly
                    # (such as plane stress) are satisfied weakly.
                    if outputclone.allowsArithmetic():
                        OOF.Mesh.Analyze.Average(
                            mesh=meshname,
                            data=outputclone,
                            time=latest,
                            domain=EntireMesh(),
                            sampling=ElementSampleSet(order=automatic),
                            destination=OutputStream(filename='test.dat',
                                                     mode='w')
                        )
                        outputdestination.forgetTextOutputStreams()

                        self.assert_(
                            fp_file_compare(
                                'test.dat',
                                os.path.join('output_data', 'avg_'+comp_file),
                                tolerance))
                        file_utils.remove('test.dat')

        OOF.Material.Delete(name='therm_left')
        OOF.Material.Delete(name='therm_centre')
        OOF.Material.Delete(name='therm_right')
        OOF.Material.Delete(name='electro_left')
        OOF.Material.Delete(name='electro_centre')
        OOF.Material.Delete(name='electro_right')
        OOF.Material.Delete(name='aniso_therm_centre')
        OOF.Material.Delete(name='therm_left_aniso')
        OOF.Material.Delete(name="electro_centre2")
        OOF.Material.Delete(name="electro_centre2r")
        OOF.Material.Delete(name="isomaterial")
        OOF.Property.Delete(property=
                            'Mechanical:StressFreeStrain:Isotropic:therm')
        OOF.Property.Delete(property=
                            'Couplings:ThermalExpansion:Isotropic:therm')
        OOF.Property.Delete(
            property= 'Mechanical:Elasticity:Anisotropic:Orthorhombic:aniso')
        OOF.Property.Delete(property="Orientation:none")
        OOF.Property.Delete(property="Orientation:ninety")

    def ScalarOutputs(self):
        global scalar_output_args
        tolerance = 1.0e-08
        from ooflib.engine.IO import output
        self.outputs("Scalar Outputs",
                     output.scalarOutputs,
                     scalar_output_args,
                     tolerance)

    def AggregateOutputs(self):
        global aggregate_output_args
        tolerance = 1.0e-08
        from ooflib.engine.IO import output
        self.outputs("Aggregate Outputs",
                     output.aggregateOutputs,
                     aggregate_output_args,
                     tolerance)
        

# Entries in the position_output_args dictionary are: Keys are the
# names of position outputs, and values a tuple consisting of a
# dictionary of parameter values for the output, and then a list of
# the expected results for this output applied to the standard
# 'position_mesh' at MasterCoord(0.0) in each element. 

position_output_args = {}
def build_position_output_args():
    from ooflib.common import primitives
    Point = primitives.Point
    global position_output_args
    position_output_args = {
        'original':({},[Point(0.125,0.125),
                        Point(0.375,0.125),
                        Point(0.625,0.125),
                        Point(0.875,0.125),
                        Point(0.125,0.375),
                        Point(0.375,0.375),
                        Point(0.625,0.375),
                        Point(0.875,0.375),
                        Point(0.125,0.625),
                        Point(0.375,0.625),
                        Point(0.625,0.625),
                        Point(0.875,0.625),
                        Point(0.125,0.875),
                        Point(0.375,0.875),
                        Point(0.625,0.875),
                        Point(0.875,0.875)]),
        'actual':({},[Point(0.132547,0.136804),
                      Point(0.377216,0.135438),
                      Point(0.622784,0.135438),
                      Point(0.867453,0.136804),
                      Point(0.142188,0.411169),
                      Point(0.380488,0.408743),
                      Point(0.619512,0.408743),
                      Point(0.857812,0.411169),
                      Point(0.144706,0.686449),
                      Point(0.381683,0.684979),
                      Point(0.618317,0.684979),
                      Point(0.855294,0.686449),
                      Point(0.14515,0.962084), 
                      Point(0.38182,0.961674),
                      Point(0.61818,0.961674), 
                      Point(0.85485,0.962084)]),
        'enhanced':({'factor':2.0},[Point(0.140094,0.148609),
                                    Point(0.379431,0.145877),
                                    Point(0.620569,0.145877),
                                    Point(0.859906,0.148609),
                                    Point(0.159377,0.447338),
                                    Point(0.385976,0.442487),
                                    Point(0.614024,0.442487),
                                    Point(0.840623,0.447338),
                                    Point(0.164412,0.747898),
                                    Point(0.388366,0.744958),
                                    Point(0.611634,0.744958),
                                    Point(0.835588,0.747898),
                                    Point(0.1653,1.04917),
                                    Point(0.388641,1.04835),
                                    Point(0.611359,1.04835),
                                    Point(0.8347,1.04917)])
        }
    

# Values of this dictionary are a list of tuples.  Each tuple
# specifies a filename from which to load a mesh, a dictionary of
# parameters for the output, and a filename against which to compare
# the output.
scalar_output_args = {}
def build_scalar_output_args():
    global scalar_output_args
    scalar_output_args = {
        'Field:Component':[
            ('thermms:thermskel:therm',
             {'field':Displacement,'component':'x'},
             'fcomp_displacement_x.dat'),

            ('thermms:thermskel:therm',
             {'field':Displacement,'component':'y'},
             'fcomp_displacement_y.dat'),

            ('thermms:thermskel:therm',
             {'field':Temperature,'component':''},
             'fcomp_temperature.dat'),

            ('electroms:electroskel:electro',
             {'field':Voltage,'component':''},
             'fcomp_voltage.dat')
            ],

        'Field:Invariant':[
            ('thermms:thermskel:therm',
             {'invariant':Magnitude(),'field':Displacement},
             'finvar_displacement_mag.dat')],

        'Field:Derivative:Component':[
            ('thermms:thermskel:therm',
             {'field':Displacement,
              'component':'x',
              'derivative':'x'},
             'fderivcomp_disp_xx.dat'),
            ('thermms:thermskel:therm',
             {'field':Displacement,
              'component':'x',
              'derivative':'y'},
             'fderivcomp_disp_xy.dat'),
            ('thermms:thermskel:therm',
             {'field':Displacement,
              'component':'y',
              'derivative':'x'},
             'fderivcomp_disp_yx.dat'),
            ('thermms:thermskel:therm',
             {'field':Displacement,
              'component':'y',
              'derivative':'y'},
             'fderivcomp_disp_yy.dat'),
            ('thermms:thermskel:therm',
             {'field':Temperature,
              'component':'',
              'derivative':'x'},
             'fderivcomp_temp_x.dat'),
            ('thermms:thermskel:therm',
             {'field':Temperature,
              'component':'',
              'derivative':'y'},
             'fderivcomp_temp_y.dat'),
            ('electroms:electroskel:electro',
             {'field':Voltage,
              'component':'',
              'derivative':'x'},
             'fderivcomp_voltage_x.dat'),
            ('electroms:electroskel:electro',
             {'field':Voltage,
              'component':'',
              'derivative':'y'},
             'fderivcomp_voltage_y.dat')
            ],

        'Field:Derivative:Invariant':[
            ('thermms:thermskel:therm',
             {'field':Displacement,
              'derivative':'x',
              'invariant':Magnitude()},
             'fderiv_invar_x_mag.dat'),
            ('thermms:thermskel:therm',
             {'field':Displacement,
              'derivative':'y',
              'invariant':Magnitude()},
             'fderiv_invar_y_mag.dat')
            ],

        # Just do a few representative stress components -- the full
        # stress will be examined in detail in the aggregate output
        # tests.
        'Flux:Component':[
            ('thermms:thermskel:therm',
             {'flux':Stress,'component':'xx'},
             'flux_comp_stress_xx.dat'),
            ('thermms:thermskel:therm',
             {'flux':Stress,'component':'xy'},
             'flux_comp_stress_xy.dat'),
            ('thermms:thermskel:therm',
             {'flux':Stress,'component':'yy'},
             'flux_comp_stress_yy.dat'),
            ('thermms:thermskel:therm',
             {'flux':Heat_Flux,'component':'x'},
             'flux_comp_heat_x.dat'),
            ('thermms:thermskel:therm',
             {'flux':Heat_Flux,'component':'y'},
             'flux_comp_heat_y.dat'),
            ('thermms:thermskel:therm',
             {'flux':Heat_Flux,'component':'z'},
             'flux_comp_heat_z.dat'),
            ('electroms:electroskel:electro',
             {'flux':Total_Polarization,'component':'x'},
             'flux_comp_polarization_x.dat'),
            ('electroms:electroskel:electro',
             {'flux':Total_Polarization,'component':'y'},
             'flux_comp_polarization_y.dat'),
            ('electroms:electroskel:electro',
             {'flux':Total_Polarization,'component':'z'},
             'flux_comp_polarization_z.dat')
            ],
        'Flux:Invariant':[
            ('thermms:thermskel:therm',
             {'flux':Stress,
              'invariant':MatrixTrace()},
             'flux_invar_stress_trace.dat'),
            ('thermms:thermskel:therm',
             {'flux':Stress,
              'invariant':Determinant()},
             'flux_invar_stress_det.dat'),
            ('thermms:thermskel:therm',
             {'flux':Stress,
              'invariant':SecondInvariant()},
             'flux_invar_stress_2nd.dat'),
            ('thermms:thermskel:therm',
             {'flux':Heat_Flux,
              'invariant':Magnitude()},
             'flux_invar_heat_mag.dat'),
            ('electroms:electroskel:electro',
             {'flux':Total_Polarization,
              'invariant':Magnitude()},
             'flux_invar_polarization_mag.dat')
            ],
        'XYFunction':[
            ('thermms:thermskel:therm',
             {'f':'x*y'},
             'xyfunction.dat')],
        'Energy':[
            ('thermms:thermskel:therm',
             {'etype':'Total'},
             'therm_e_total.dat'),
            ('thermms:thermskel:therm',
             {'etype':'Elastic'},
             'therm_e_elastic.dat'),
            ('electroms:electroskel:electro',
             {'etype':'Total'},
             'electro_e_total.dat'),
            ('electroms:electroskel:electro',
             {'etype':'Electric'},
             'electro_e_electric.dat')
            ],
        # Again, restricted to the few most relevant components --
        # full set will be covered in the aggregate output tests.
        'Strain:Component':[
            ('thermms:thermskel:therm',
             {'type':GeometricStrain(),'component':'xx'},
             'strain_therm_geom_xx.dat'),
            ('thermms:thermskel:therm',
             {'type':GeometricStrain(),'component':'xy'},
             'strain_therm_geom_xy.dat'),
            ('thermms:thermskel:therm',
             {'type':GeometricStrain(),'component':'yy'},
             'strain_therm_geom_yy.dat'),
            
            ('thermms:thermskel:therm',
             {'type':ElasticStrain(),'component':'xx'},
             'strain_therm_elastic_xx.dat'),
            ('thermms:thermskel:therm',
             {'type':ElasticStrain(),'component':'xy'},
             'strain_therm_elastic_xy.dat'),
            ('thermms:thermskel:therm',
             {'type':ElasticStrain(),'component':'yy'},
             'strain_therm_elastic_yy.dat'),
            
            ('thermms:thermskel:therm',
             {'type':ThermalStrain(),'component':'xx'},
             'strain_therm_thermal_xx.dat'),
            ('thermms:thermskel:therm',
             {'type':ThermalStrain(),'component':'xy'},
             'strain_therm_thermal_xy.dat'),
            ('thermms:thermskel:therm',
             {'type':ThermalStrain(),'component':'yy'},
             'strain_therm_thermal_yy.dat'),
            
            ('electroms:electroskel:electro',
             {'type':GeometricStrain(),'component':'xx'},
             'strain_electro_geom_xx.dat'),
            ('electroms:electroskel:electro',
             {'type':GeometricStrain(),'component':'xy'},
             'strain_electro_geom_xy.dat'),
            ('electroms:electroskel:electro',
             {'type':GeometricStrain(),'component':'yy'},
             'strain_electro_geom_yy.dat'),
                            
            ('electroms:electroskel:electro',
             {'type':ElasticStrain(),'component':'xx'},
             'strain_electro_elastic_xx.dat'),
            ('electroms:electroskel:electro',
             {'type':ElasticStrain(),'component':'xy'},
             'strain_electro_elastic_xy.dat'),
            ('electroms:electroskel:electro',
             {'type':ElasticStrain(),'component':'yy'},
             'strain_electro_elastic_yy.dat'),
                            
            ('electroms:electroskel:electro',
             {'type':PiezoelectricStrain(),'component':'xx'},
             'strain_electro_piezo_xx.dat'),
            ('electroms:electroskel:electro',
             {'type':PiezoelectricStrain(),'component':'xy'},
             'strain_electro_piezo_xy.dat'),
            ('electroms:electroskel:electro',
             {'type':PiezoelectricStrain(),'component':'yy'},
             'strain_electro_piezo_yy.dat')
            ],
        'Strain:Invariant':[
            ('thermms:thermskel:therm',
             {'type':GeometricStrain(),
              'invariant':MatrixTrace()},
             'strain_therm_geom_trace.dat'),
            
            ('thermms:thermskel:therm',
             {'type':GeometricStrain(),
              'invariant':Determinant()},
             'strain_therm_geom_det.dat'),
            
            ('thermms:thermskel:therm',
             {'type':GeometricStrain(),
              'invariant':SecondInvariant()},
             'strain_therm_geom_2nd.dat'),
            
            ('thermms:thermskel:therm',
             {'type':ElasticStrain(),
              'invariant':MatrixTrace()},
             'strain_therm_elastic_trace.dat'),
            
            ('thermms:thermskel:therm',
             {'type':ElasticStrain(),
              'invariant':Determinant()},
             'strain_therm_elastic_det.dat'),
            
            ('thermms:thermskel:therm',
             {'type':ElasticStrain(),
              'invariant':SecondInvariant()},
             'strain_therm_elastic_2nd.dat'),
            
            ('thermms:thermskel:therm',
             {'type':ThermalStrain(),
              'invariant':MatrixTrace()},
             'strain_therm_thermal_trace.dat'),
            
            ('thermms:thermskel:therm',
             {'type':ThermalStrain(),
              'invariant':Determinant()},
             'strain_therm_thermal_det.dat'),
            
            ('thermms:thermskel:therm',
             {'type':ThermalStrain(),
              'invariant':SecondInvariant()},
             'strain_therm_thermal_2nd.dat'),
            
            ('electroms:electroskel:electro',
             {'type':GeometricStrain(),
              'invariant':MatrixTrace()},
             'strain_electro_geom_trace.dat'),
            
            ('electroms:electroskel:electro',
             {'type':GeometricStrain(),
              'invariant':Determinant()},
             'strain_electro_geom_det.dat'),
            
            ('electroms:electroskel:electro',
             {'type':GeometricStrain(),
              'invariant':SecondInvariant()},
             'strain_electro_geom_2nd.dat'),
            
            ('electroms:electroskel:electro',
             {'type':ElasticStrain(),
              'invariant':MatrixTrace()},
             'strain_electro_elastic_trace.dat'),
            
            ('electroms:electroskel:electro',
             {'type':ElasticStrain(),
              'invariant':Determinant()},
             'strain_electro_elastic_det.dat'),
            
            ('electroms:electroskel:electro',
             {'type':ElasticStrain(),
              'invariant':SecondInvariant()},
             'strain_electro_elastic_2nd.dat'),
            
            ('electroms:electroskel:electro',
             {'type':PiezoelectricStrain(),
              'invariant':MatrixTrace()},
             'strain_electro_piezo_trace.dat'),
            
            ('electroms:electroskel:electro',
             {'type':PiezoelectricStrain(),
              'invariant':Determinant()},
             'strain_electro_piezo_det.dat'),
            
            ('electroms:electroskel:electro',
             {'type':PiezoelectricStrain(),
              'invariant':SecondInvariant()},
             'strain_electro_piezo_2nd.dat')
            ]
        
        }
    # scalar_output_args = {'Flux:Component':[
    #         ('thermms:thermskel:therm',
    #          {'flux':Stress,'component':'xx'},
    #          'flux_comp_stress_xx.dat')]}


# Dictionary for aggregate output tests -- has the same structure as
# the scalar output dictionary.
aggregate_output_args = {}
def build_aggregate_output_args():
    global aggregate_output_args
    aggregate_output_args = {
        'Field:Value':[('thermms:thermskel:therm',
                        {'field':Displacement},
                        'field_displacement.dat'),
                       ('thermms:thermskel:therm',
                        {'field':Temperature},
                        'field_temp.dat'),
                       ('electroms:electroskel:electro',
                        {'field':Voltage},
                        'field_voltage.dat')
                       ],
        'Field:Derivative':[('thermms:thermskel:therm',
                             {'field':Displacement,
                              'derivative':'x'},
                             'field_displacement_dx.dat'),
                            ('thermms:thermskel:therm',
                             {'field':Displacement,
                              'derivative':'y'},
                             'field_displacement_dy.dat'),
                            ('thermms:thermskel:therm',
                             {'field':Temperature,
                              'derivative':'x'},
                             'field_temperature_dx.dat'),
                            ('thermms:thermskel:therm',
                             {'field':Temperature,
                              'derivative':'y'},
                             'field_temperature_dy.dat'),
                            ('electroms:electroskel:electro',
                             {'field':Voltage,
                              'derivative':'x'},
                             'field_voltage_dx.dat'),
                            ('electroms:electroskel:electro',
                             {'field':Voltage,
                              'derivative':'y'},
                             'field_voltage_dy.dat')
                            ],
        'Field:Invariant':[('thermms:thermskel:therm',
                            {'field':Displacement,
                             'invariant':Magnitude()},
                            'field_displacement_mag.dat'),
                           ('thermms:thermskel:therm',
                            {'field':Temperature,
                             'invariant':Magnitude()},
                            'field_temperature_invar.dat'),
                           ('electroms:electroskel:electro',
                            {'field':Voltage,
                             'invariant':Magnitude()},
                            'field_voltage_invar.dat')
                           ],
        'Flux:Value':[('thermms:thermskel:therm',
                       {'flux':Stress},
                       'flux_therm_stress.dat'),
                      ('thermms:thermskel:therm',
                       {'flux':Heat_Flux},
                       'flux_therm_heatflux.dat'),
                      ('electroms:electroskel:electro',
                       {'flux':Stress},
                       'flux_electro_stress.dat'),
                      ('electroms:electroskel:electro',
                       {'flux':Heat_Flux},
                       'flux_electro_heatflux.dat')
                      ],
        'Energy':[('thermms:thermskel:therm',
                   {'etype':'Total'},
                   'agg_e_therm_total.dat'),
                  ('thermms:thermskel:therm',
                   {'etype':'Elastic'},
                   'agg_e_therm_elastic.dat'),
                  ('electroms:electroskel:electro',
                   {'etype':'Total'},
                   'agg_e_electro_total.dat'),
                  ('electroms:electroskel:electro',
                   {'etype':'Electric'},
                   'agg_e_electro_electric.dat')
                  ],
        'Strain:Value':[('thermms:thermskel:therm',
                         {'type':GeometricStrain()},
                         'agg_strain_therm_geometric.dat'),
                        ('thermms:thermskel:therm',
                         {'type':ElasticStrain()},
                         'agg_strain_therm_elastic.dat'),
                        ('thermms:thermskel:therm',
                         {'type':ThermalStrain()},
                         'agg_strain_therm_thermal.dat'),
                        ('electroms:electroskel:electro',
                         {'type':GeometricStrain()},
                         'agg_strain_electro_geometric.dat'),
                        ('electroms:electroskel:electro',
                         {'type':ElasticStrain()},
                         'agg_strain_electro_elastic.dat'),
                        ('electroms:electroskel:electro',
                         {'type':PiezoelectricStrain()},
                         'agg_strain_electro_piezo.dat')
                        ],
        # Invariant coverage is not complete, because the actual
        # outputs are the same objects as in the Scalar test -- just
        # make sure these outputs exist in the tree, and that
        # invocation as aggregates doesn't crash.
        'Strain:Invariant':[('thermms:thermskel:therm',
                             {'type':ElasticStrain(),
                              'invariant':MatrixTrace()},
                             'agg_strain_therm_elastic_trace.dat'),
                            
                            ('electroms:electroskel:electro',
                             {'type':PiezoelectricStrain(),
                              'invariant':MatrixTrace()},
                             'agg_strain_electro_piezo_trace.dat')
                            ],

        # Tests for all(?) Material Constants
        'Material Constants:Orientation':[
            ('thermms:thermskel:therm',
             {'format':'Abg'},'orientation_iso_thermo.dat'),
            ('anisothermms:thermskel:therm',
             {'format':'Abg'},'orientation_aniso_abg_thermo.dat'),
            ('anisothermms:thermskel:therm',
             {'format':'Axis'},'orientation_aniso_axis_thermo.dat'),
            ('anisothermms:thermskel:therm',
             {'format':'Quaternion'},'orientation_aniso_quat_thermo.dat'),
        ],
        'Material Constants:Mechanical:Elastic Modulus C':
        [
            ('thermms:thermskel:therm',
             {'components':['11', '12', '13', '22', '23',
                            '33', '44', '55', '66'],
              'frame':'Crystal'},
             'cijkl_iso_thermo.dat'),
            ('thermms:thermskel:therm',
             {'components':['11', '12', '13', '22', '23',
                            '33', '44', '55', '66'],
              'frame':'Lab'},
             'cijkl_iso_thermo.dat'),
            ('anisothermms:thermskel:therm',
             {'components':['11', '12', '13', '22', '23',
                            '33', '44', '55', '66'],
              'frame':'Crystal'},
             'cijkl_aniso_thermo.dat'),
            ('anisothermms:thermskel:therm',
             {'components':['11', '12', '13', '22', '23',
                            '33', '44', '55', '66'],
              'frame':'Lab'},
             'cijkl_aniso_thermo_lab.dat'),
            ('isomesh:skeleton:mesh',
             {'components':['11', '12', '13', '14', '15',
                            '22', '23', '24', '26', '33',
                            '35', '44', '46', '55', '66'],
              'frame':'Lab'},
             'isomesh_cijkl.dat'),
            ('isomesh:skeleton:mesh',
             {'components':['11', '12', '13', '14', '15',
                            '22', '23', '24', '26', '33',
                            '35', '44', '46', '55', '66'],
              'frame':'Crystal'},
             'isomesh_cijkl.dat')
        ],
        'Material Constants:Mechanical:Stress-free Strain epsilon0':
        [
            ('anisothermms:thermskel:therm',
             {'components':['11', '12', '13', '22', '33'],
              'frame':'Crystal'},
             'stressfreestrain_aniso_thermo.dat'),
            ('anisothermms:thermskel:therm',
             {'components':['11', '12', '13', '22', '33'],
              'frame':'Lab'},
             'stressfreestrain_aniso_thermo_lab.dat'),
            ('isomesh:skeleton:mesh',
             {"components":['11', '12', '13', '22', '33'],
              "frame":"Crystal"},
             'isomesh_strfreestrain.dat'),
            ('isomesh:skeleton:mesh',
             {"components":['11', '12', '13', '22', '33'],
              "frame":"Lab"},
             'isomesh_strfreestrain.dat')
            ],
        'Material Constants:Mechanical:Force Density F':
        [
            ('isomesh:skeleton:mesh', {}, 'isomesh_forcedensity.dat')
        ],
        'Material Constants:Mechanical:Mass Density':
        [
            ('isomesh:skeleton:mesh', {}, 'isomesh_massdensity.dat')
        ],
        'Material Constants:Mechanical:Viscosity':
        [
            ('isomesh:skeleton:mesh',
             {"components":['11', '22', '23', '33', '66'],
              "frame":"Crystal"},
             'isomesh_viscosity.dat'),
            ('isomesh:skeleton:mesh',
             {"components":['11', '22', '23', '33', '66'],
              "frame":"Lab"},
             'isomesh_viscosity.dat')
        ],
        'Material Constants:Mechanical:Damping':
        [
            ('isomesh:skeleton:mesh', {}, 'isomesh_damping.dat')
        ],

        'Material Constants:Thermal:Conductivity K':
        [
            ('thermms:thermskel:therm',
             {'components':['11', '12', '13', '22', '33'],
              'frame':'Crystal'},
             'heatcond_iso_thermo.dat'),
            ('thermms:thermskel:therm',
             {'components':['11', '12', '13', '22', '33'],
              'frame':'Lab'},
             'heatcond_iso_thermo.dat'),
            ('anisothermms:thermskel:therm',
             {'components':['11', '12', '13', '22', '33'],
              'frame':'Crystal'},
             'heatcond_aniso_thermo.dat'),
            ('anisothermms:thermskel:therm',
             {'components':['11', '12', '13', '22', '33'],
              'frame':'Lab'},
             'heatcond_aniso_thermo_lab.dat'),
            ('isomesh:skeleton:mesh',
             {"components":['13', '23', '33'],
             'frame':'Crystal'},
             'isomesh_thermcond.dat'),
            ('isomesh:skeleton:mesh',
             {"components":['13', '23', '33'],
             'frame':'Lab'},
             'isomesh_thermcond.dat'),
        ],
        'Material Constants:Thermal:Heat Capacity':
        [
            ('isomesh:skeleton:mesh',{}, 'isomesh_heatcap.dat')
        ],
        'Material Constants:ThermalHeat Source':
        [
            ('isomesh:skeleton:mesh', {}, 'isomesh_heatsource.dat')
        ],
        'Material Constants:Electric:Dielectric Permittivity epsilon':
        [
            ('isomesh:skeleton:mesh',
             {"components":['11', '22', '23', '33'],
              'frame':'Lab'},
             'isomesh_permittivity.dat'),
            ('isomesh:skeleton:mesh',
             {"components":['11', '22', '23', '33'],
              'frame':'Crystal'},
             'isomesh_permittivity.dat'),
        ],
        'Material Constants:Electric:Space Charge':
        [
            ('isomesh:skeleton:mesh', {}, 'isomesh_spacecharge.dat')
        ],
        'Material Constants:Couplings:Thermal Expansion alpha':
        [
            ('isomesh:skeleton:mesh',
             {"components":['12', '13', '22', '23'],
              "frame":"Lab"},
             'isomesh_thermexp.dat'),
            ('isomesh:skeleton:mesh',
             {"components":['12', '13', '22', '23'],
              "frame":"Crystal"},
             'isomesh_thermexp.dat'),
        ],
        'Material Constants:Couplings:Thermal Expansion T0':
        [
            ('isomesh:skeleton:mesh', {}, 'isomesh_thermexpT0.dat')
        ],
        'Material Constants:Couplings:Piezoelectric Coefficient D':
        [
            ('electroms2:electroskel:electro',
             {'components':['11', '12', '13', '15',
                            '24',
                            '31', '32', '33', '35'],
              'frame':'Crystal'},
             'piezo_xtal.dat'),
            ('electroms2:electroskel:electro',
             {'components':['11', '12', '13', '15',
                            '24',
                            '31', '32', '33', '35'],
              'frame':'Lab'},
             'piezo_lab.dat'),
            ('electroms2r:electroskel:electro',
             {'components':['11', '12', '13', '15',
                            '24',
                            '31', '32', '33', '35'],
              'frame':'Crystal'},
             'piezo_rot_xtal.dat'),
            ('electroms2r:electroskel:electro',
             {'components':['11', '12', '13', '15',
                            '24',
                            '31', '32', '33', '35'],
              'frame':'Lab'},
             'piezo_rot_lab.dat'),
        ],
        'Concatenate':
        [
            ('thermms:thermskel:therm',
             {'first':getOutput('Field:Value',field=Temperature),
              'second':getOutput('Field:Value',field=Displacement)},
             'concat_fields.dat'),
            ## This doesn't work because we can't average a nonscalar
            ## material constant.
            # ('thermms:thermskel:therm',
            #  {'first':getOutput('Field:Value',field=Temperature),
            #   'second':getOutput('Material Constants:Thermal:Conductivity K',
            #                      components=['11', '12'], frame="Crystal")},
            #  'concat_temp_kappa.dat')
            ('thermms:thermskel:therm',
             {'first':getOutput('Field:Value',field=Temperature),
              'second':getOutput('Concatenate',
                                 first=getOutput('Flux:Invariant',
                                                 invariant=Magnitude(),
                                                 flux=Heat_Flux),
                                 second=getOutput('Energy',etype='Total'))},
             'concat_triple.dat')
        ]
    }



class OOF_PlaneFluxRHS(unittest.TestCase):
    def setUp(self):
        OOF.Microstructure.New(name='microstructure', width=1.0, height=1.0,
                               width_in_pixels=10, height_in_pixels=10)
        OOF.Skeleton.New(
            name='skeleton', microstructure='microstructure',
            x_elements=4, y_elements=4,
            skeleton_geometry=QuadSkeleton(top_bottom_periodicity=False,
                                           left_right_periodicity=False))
        OOF.Material.New(name='material')
        OOF.Material.Add_property(name='material',
                                  property='Mechanical:Elasticity:Isotropic')
        OOF.Property.Parametrize.Mechanical.StressFreeStrain.Isotropic(
            epsilon0=0.1)
        OOF.Material.Add_property(
            name='material',
            property='Mechanical:StressFreeStrain:Isotropic')
        OOF.Material.Assign(material='material',
                            microstructure='microstructure', pixels=all)
        OOF.Mesh.New(name='mesh',
                     skeleton='microstructure:skeleton',
                     element_types=['T3_3', 'Q4_4'])
        OOF.Subproblem.Field.Define(
            subproblem='microstructure:skeleton:mesh:default',
            field=Displacement)
        OOF.Subproblem.Field.Activate(
            subproblem='microstructure:skeleton:mesh:default',
            field=Displacement)
        OOF.Subproblem.Equation.Activate(
            subproblem='microstructure:skeleton:mesh:default',
            equation=Force_Balance)
        OOF.Subproblem.Equation.Activate(
            subproblem='microstructure:skeleton:mesh:default',
            equation=Plane_Stress)
        OOF.Mesh.Boundary_Conditions.New(
            name='bc',
            mesh='microstructure:skeleton:mesh',
            condition=DirichletBC(field=Displacement,
                                  field_component='x',
                                  equation=Force_Balance,
                                  eqn_component='x',
                                  profile=ConstantProfile(value=0.0),
                                  boundary='bottomleft'))
        OOF.Mesh.Boundary_Conditions.New(
            name='bc<2>',
            mesh='microstructure:skeleton:mesh',
            condition=DirichletBC(field=Displacement,
                                  field_component='y',
                                  equation=Force_Balance,
                                  eqn_component='y',
                                  profile=ConstantProfile(value=0.0),
            boundary='bottomleft'))
        OOF.Mesh.Boundary_Conditions.New(
            name='bc<3>',
            mesh='microstructure:skeleton:mesh',
            condition=DirichletBC(field=Displacement,
                                  field_component='y',
                                  equation=Force_Balance,
                                  eqn_component='y',
                                  profile=ConstantProfile(value=0.0),
                                  boundary='bottomright'))

        
    def tearDown(self):
        OOF.Material.Delete(name="material")

    # Solve the system and examine the resulting strain.  Sufficient
    # proof that it worked is if the strain in the system is within
    # roundoff of (0.1,0.1,0.1).
    @memorycheck.check("microstructure")
    def StrainCheck(self):
        OOF.Subproblem.Set_Solver(
            subproblem='microstructure:skeleton:mesh:default',
            solver_mode=AdvancedSolverMode(
                nonlinear_solver=NoNonlinearSolver(),
                time_stepper=StaticDriver(),
                symmetric_solver=ConjugateGradient(
                    preconditioner=ILUPreconditioner(),tolerance=1e-13,
                    max_iterations=1000)))

        OOF.Mesh.Solve(mesh='microstructure:skeleton:mesh',
                       endtime=0.0)
        OOF.Mesh.Analyze.Direct_Output(
            mesh='microstructure:skeleton:mesh',
            time=latest,
            data=getOutput('Strain:Value',
                           type=GeometricStrain()),
            domain=EntireMesh(),
            sampling=GridSampleSet(x_points=3,
                                   y_points=3,
                                   show_x=True,
                                   show_y=True),
            destination=OutputStream(filename='plane_stress_rhs.out', mode='w'))

        outputdestination.forgetTextOutputStreams()

        self.assert_(fp_file_compare(
            'plane_stress_rhs.out',
            os.path.join('output_data','plane_stress_ref.dat'),
            1.0e-08)
                     )
        file_utils.remove('plane_stress_rhs.out')

# Check that the out-of-plane stresses are zero for plane stress.
# This only checks the *average* stress, because the plane stress
# condition is only enforced weakly.
class OOF_AnisoPlaneStress(unittest.TestCase):
    @memorycheck.check("microstructure")
    def Avg(self):
        OOF.Microstructure.New(
            name='microstructure',
            width=1.0, height=1.0, width_in_pixels=10, height_in_pixels=10)
        OOF.Material.New(
            name='material', material_type='bulk')
        OOF.Material.Assign(
            material='material', microstructure='microstructure', pixels=all)
        OOF.Property.Copy(
            property='Mechanical:Elasticity:Anisotropic:Tetragonal',
            new_name='instance')
        OOF.Property.Parametrize.Mechanical.Elasticity.Anisotropic.Tetragonal.instance(
            cijkl=TetragonalRank4TensorCij(
                c11=1, c12=0.1, c13=0.2, c33=0.3, c44=0.4, c66=0.6, c16=0.2))
        OOF.Material.Add_property(
            name='material', 
            property='Mechanical:Elasticity:Anisotropic:Tetragonal:instance')
        OOF.Property.Copy(
            property="Orientation", new_name='instance')
        OOF.Material.Add_property(
            name='material', property='Orientation:instance')
        OOF.Property.Parametrize.Orientation.instance(
            angles=Abg(alpha=45,beta=12,gamma=-37))
        OOF.Skeleton.New(
            name='skeleton',
            microstructure='microstructure',
            x_elements=20, y_elements=20,
            skeleton_geometry=TriSkeleton(
                left_right_periodicity=False,
                top_bottom_periodicity=False,
                arrangement='liberal'))
        OOF.Mesh.New(
            name='mesh',
            skeleton='microstructure:skeleton',
            element_types=['D2_2', 'T3_3', 'Q4_4'])
        OOF.Subproblem.Field.Define(
            subproblem='microstructure:skeleton:mesh:default',
            field=Displacement)
        OOF.Subproblem.Field.Activate(
            subproblem='microstructure:skeleton:mesh:default', 
            field=Displacement)
        OOF.Subproblem.Equation.Activate(
            subproblem='microstructure:skeleton:mesh:default',
            equation=Force_Balance)
        OOF.Subproblem.Equation.Activate(
            subproblem='microstructure:skeleton:mesh:default',
            equation=Plane_Stress)
        OOF.Mesh.Boundary_Conditions.New(
            name='bc',
            mesh='microstructure:skeleton:mesh',
            condition=DirichletBC(
                field=Displacement,field_component='x',
                equation=Force_Balance,eqn_component='x',
                profile=ContinuumProfileXTd(
                    function='0',timeDerivative='0',timeDerivative2='0'),
                boundary='left'))
        OOF.Mesh.Boundary_Conditions.New(
            name='bc<2>', 
            mesh='microstructure:skeleton:mesh',
            condition=DirichletBC(
                field=Displacement,field_component='x',
                equation=Force_Balance,eqn_component='x',
                profile=ContinuumProfileXTd(
                    function='0.1',timeDerivative='0',timeDerivative2='0'),
                boundary='right'))
        OOF.Mesh.Boundary_Conditions.New(
            name='bc<3>', 
            mesh='microstructure:skeleton:mesh',
            condition=DirichletBC(
                field=Displacement,field_component='y',
                equation=Force_Balance,eqn_component='y',
                profile=ContinuumProfileXTd(
                    function='0.0',timeDerivative='0',timeDerivative2='0'),
                boundary='top'))
        OOF.Mesh.Boundary_Conditions.New(
            name='bc<4>', 
            mesh='microstructure:skeleton:mesh', 
            condition=DirichletBC(
                field=Displacement,field_component='y',
                equation=Force_Balance,eqn_component='y',
                profile=ContinuumProfileXTd(
                    function='0.0',timeDerivative='0',timeDerivative2='0'),
                boundary='bottom'))
        OOF.Subproblem.Set_Solver(
            subproblem='microstructure:skeleton:mesh:default',
            solver_mode=AdvancedSolverMode(
                nonlinear_solver=NoNonlinearSolver(),
                time_stepper=StaticDriver(),
                symmetric_solver=ConjugateGradient(
                    preconditioner=ILUPreconditioner(),tolerance=1.e-13,
                    max_iterations=1000)))
        OOF.Mesh.Solve(
            mesh='microstructure:skeleton:mesh',
            endtime=0.0)
        OOF.Mesh.Analyze.Average(
            mesh='microstructure:skeleton:mesh', 
            data=getOutput('Flux:Value',flux=Stress),
            time=latest,
            domain=EntireMesh(),
            sampling=ElementSampleSet(order=automatic),
            destination=OutputStream(filename='test.dat',mode='w'))
        self.assert_(
            fp_file_compare(
                'test.dat',
                os.path.join('output_data', 'aniso_planestress.dat'),
                1.e-8))
        file_utils.remove('test.dat')
        outputdestination.forgetTextOutputStreams()
    def tearDown(self):
        OOF.Property.Delete(
            property='Mechanical:Elasticity:Anisotropic:Tetragonal:instance')
        OOF.Property.Delete(
            property='Orientation:instance')
        OOF.Material.Delete(name='material')

class OOF_BadMaterial(unittest.TestCase):
    @memorycheck.check("microstructure")
    def Analyze(self):
        from ooflib.SWIG.engine import ooferror2
        OOF.Microstructure.New(
            name='microstructure',
            width=1.0, height=1.0,
            width_in_pixels=10, height_in_pixels=10)
        OOF.Material.New(
            name='material', material_type='bulk')
        OOF.Material.Assign(
            material='material',
            microstructure='microstructure',
            pixels=every)
        OOF.Material.Add_property(
            name='material',
            property='Mechanical:Elasticity:Anisotropic:Cubic')
        OOF.Material.Add_property(
            name='material', property='Orientation')
        OOF.Skeleton.New(
            name='skeleton',
            microstructure='microstructure',
            x_elements=4, y_elements=4,
            skeleton_geometry=QuadSkeleton(
                left_right_periodicity=False,top_bottom_periodicity=False))
        OOF.Mesh.New(
            name='mesh',
            skeleton='microstructure:skeleton',
            element_types=['D2_2', 'T3_3', 'Q4_4'])
        OOF.Subproblem.Field.Define(
            subproblem='microstructure:skeleton:mesh:default',
            field=Displacement)
        OOF.Subproblem.Field.Activate(
            subproblem='microstructure:skeleton:mesh:default',
            field=Displacement)
        OOF.Mesh.Field.In_Plane(
            mesh='microstructure:skeleton:mesh',
            field=Displacement)
        OOF.Subproblem.Equation.Activate(
            subproblem='microstructure:skeleton:mesh:default',
            equation=Force_Balance)
        # This shouldn't raise an exception
        OOF.Mesh.Analyze.Average(
            mesh='microstructure:skeleton:mesh', 
            time=latest,
            data=getOutput('Flux:Component',component='xx',flux=Stress),
            domain=EntireMesh(),
            sampling=ElementSampleSet(order=automatic),
            destination=MessageWindowStream())
        # Remove the Orientation property, so the Material is no
        # longer self-consistent.
        OOF.Material.Remove_property(
            name='material', 
            property='Orientation')
        self.assertRaises(
            ooferror2.ErrBadMaterial,
            OOF.Mesh.Analyze.Average,
            mesh='microstructure:skeleton:mesh',
            time=latest,
            data=getOutput('Flux:Component', component='xx',flux=Stress),
            domain=EntireMesh(),
            sampling=ElementSampleSet(order=automatic),
            destination=MessageWindowStream())
        # Re-add the Orientation.
        OOF.Material.Add_property(
            name='material', property='Orientation')
        OOF.Mesh.Analyze.Average(
            mesh='microstructure:skeleton:mesh', 
            time=latest,
            data=getOutput('Flux:Component',component='xx',flux=Stress),
            domain=EntireMesh(),
            sampling=ElementSampleSet(order=automatic),
            destination=MessageWindowStream())
    def tearDown(self):
        OOF.Material.Delete(name='material')

class OOF_MiscOutput(OOF_Output):
    @memorycheck.check("microstructure")
    def Range(self):
        OOF.Microstructure.New(
            name='microstructure', 
            width=1.0, height=1.0,
            width_in_pixels=10, height_in_pixels=10)
        OOF.Skeleton.New(
            name='skeleton',
            microstructure='microstructure', 
            x_elements=4, y_elements=4, 
            skeleton_geometry=QuadSkeleton(
                left_right_periodicity=False,top_bottom_periodicity=False))
        OOF.Mesh.New(
            name='mesh',
            skeleton='microstructure:skeleton',
            element_types=['D2_2', 'T3_3', 'Q4_4'])
        OOF.Subproblem.Field.Define(
            subproblem='microstructure:skeleton:mesh:default',
            field=Temperature)
        OOF.Mesh.Set_Field_Initializer(
            mesh='microstructure:skeleton:mesh',
            field=Temperature, 
            initializer=FuncScalarFieldInit(function='x'))
        OOF.Mesh.Apply_Field_Initializers(
            mesh='microstructure:skeleton:mesh')
        OOF.Mesh.Analyze.Range(
            mesh='microstructure:skeleton:mesh',
            time=latest,
            data=getOutput(
                'Field:Component',component='',field=Temperature),
            domain=EntireMesh(),
            sampling=GridSampleSet(
                x_points=10,y_points=10,
                show_x=True,show_y=True),
            destination=OutputStream(filename='test.dat', mode='w'))
        self.assert_(
            fp_file_compare(
                'test.dat',
                os.path.join('output_data', 'range.dat'),
                1.e-8))
        file_utils.remove('test.dat')
        outputdestination.forgetTextOutputStreams()


# Routine to do regression-type testing on the items in this file.
# Tests must be run in the order they appear in the list.  This
# routine will stop after the first failure.

def run_tests():

    test_set = [
        OOF_Output("PDFOutput"),
        OOF_Output("PositionOutputs"),
        OOF_Output("ScalarOutputs"),
        OOF_Output("AggregateOutputs"),
        OOF_PlaneFluxRHS("StrainCheck"),
        OOF_AnisoPlaneStress("Avg"),
        OOF_BadMaterial("Analyze"),
        OOF_MiscOutput("Range"),
        ]

    #test_set = [OOF_Output("AggregateOutputs")]
    
    build_position_output_args()
    build_scalar_output_args()
    build_aggregate_output_args()

    logan = unittest.TextTestRunner()
    for t in test_set:
        print >> sys.stderr,  "\n *** Running test: %s\n" % t.id()
        res = logan.run(t)
        if not res.wasSuccessful():
            return 0
    return 1


###################################################################
# The code below this line should be common to all testing files. #
###################################################################

if __name__=="__main__":
    # If directly run, then start oof, and run the local tests, then quit.
    import sys
    try:
        os.remove("test.dat")
    except:
        pass
    try:
        import oof2
        sys.path.append(os.path.dirname(oof2.__file__))
        from ooflib.common import oof
    except ImportError:
        print "OOF is not correctly installed on this system."
        sys.exit(4)
    sys.argv.append("--text")
    sys.argv.append("--quiet")
    sys.argv.append("--seed=17")
    oof.run(no_interp=1)

    success = run_tests()

    OOF.File.Quit()
    
    if success:
        print "All tests passed."
    else:
        print "Test failure."
