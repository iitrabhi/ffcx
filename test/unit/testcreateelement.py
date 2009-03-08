"Unit tests for FFC - ffc/fem/createelement.py"

__author__ = "Kristian Oelgaard (k.b.oelgaard@tudelft.nl)"
__date__ = "2009-03-07 -- 2009-03-07"
__copyright__ = "Copyright (C) 2009 Kristian Oelgaard"
__license__  = "GNU GPL version 3 or any later version"

import unittest
from ufl.finiteelement import *
from ffc.fem.createelement import *

class CreateElementTests(unittest.TestCase):

    def testSimpleElements(self):

        # FiniteElement
        element = FiniteElement("CG", "triangle", 2)
        ffc_element = FFCFiniteElement("CG", "triangle", 2)
        created_element = create_element(element)

#        print "\nelement:       ", element
#        print "ffc_element:     ", ffc_element
#        print "created_element: ", created_element
        self.assertEqual(ffc_element.__repr__(), created_element.__repr__())

        # MixedElement
        element1 = MixedElement([element, element])
        ffc_element1 = FFCMixedElement([ffc_element, ffc_element])
        created_element1 = create_element(element1)

#        print "\nelement1:       ", element1
#        print "ffc_element1:     ", ffc_element1
#        print "created_element1: ", created_element1
        self.assertEqual(ffc_element1.__repr__(), created_element1.__repr__())

        # VectorElement
        element2 = VectorElement("CG", "triangle", 2)
        ffc_element2 = FFCMixedElement([ffc_element, ffc_element])
        created_element2 = create_element(element2)

#        print "\nelement2:       ", element2
#        print "ffc_element2:     ", ffc_element2
#        print "created_element2: ", created_element2
        self.assertEqual(ffc_element2.__repr__(), created_element2.__repr__())

        # TensorElement
        element3 = TensorElement("CG", "triangle", 2, (3, 3))
        ffc_element3 = FFCMixedElement([ffc_element]*9)
        created_element3 = create_element(element3)

#        print "\nelement3:       ", element3
#        print "ffc_element3:     ", ffc_element3
#        print "created_element3: ", created_element3
        self.assertEqual(ffc_element3.__repr__(), created_element3.__repr__())

    def testQuadratureElements(self):

        # QuadratureElement
        element = FiniteElement("Quadrature", "triangle", 3)
        ffc_element = FFCQuadratureElement("triangle", 2)
        created_element = create_element(element)

#        print "\nelement:       ", element
#        print "ffc_element:     ", ffc_element
#        print "created_element: ", created_element
        self.assertEqual(ffc_element.__repr__(), created_element.__repr__())

        # MixedElement
        element1 = MixedElement([element, element])
        ffc_element1 = FFCMixedElement([ffc_element, ffc_element])
        created_element1 = create_element(element1)

#        print "\nelement1:       ", element1
#        print "ffc_element1:     ", ffc_element1
#        print "created_element1: ", created_element1
        self.assertEqual(ffc_element1.__repr__(), created_element1.__repr__())

        # VectorElement
        element2 = VectorElement("Quadrature", "triangle", 3)
        ffc_element2 = FFCMixedElement([ffc_element, ffc_element])
        created_element2 = create_element(element2)

#        print "\nelement2:       ", element2
#        print "ffc_element2:     ", ffc_element2
#        print "created_element2: ", created_element2
        self.assertEqual(ffc_element2.__repr__(), created_element2.__repr__())

        # TensorElement
        element3 = TensorElement("Quadrature", "triangle", 3, (3, 3))
        ffc_element3 = FFCMixedElement([ffc_element]*9)
        created_element3 = create_element(element3)

#        print "\nelement3:       ", element3
#        print "ffc_element3:     ", ffc_element3
#        print "created_element3: ", created_element3
        self.assertEqual(ffc_element3.__repr__(), created_element3.__repr__())

    def testComplexElements(self):

        # MixedElement
        element  = FiniteElement("Quadrature", "triangle", 3)
        element1 = FiniteElement("Quadrature", "triangle", 1)
        element2 = MixedElement([element, element1])
        ffc_element = FFCQuadratureElement("triangle", 2)
        ffc_element1 = FFCQuadratureElement("triangle", 1)
        ffc_element2 = FFCMixedElement([ffc_element, ffc_element1])
        created_element = create_element(element2)

#        print "\nelement2:       ", element2
#        print "ffc_element2:     ", ffc_element2
#        print "created_element: ", created_element
        self.assertEqual(ffc_element2.__repr__(), created_element.__repr__())

        element3 = FiniteElement("CG", "triangle", 1)
        ffc_element3 = FFCFiniteElement("CG", "triangle", 1)

        # MixedElement
        element4 = MixedElement([element3, element2])
        ffc_element4 = FFCMixedElement([ffc_element3, ffc_element2])
        created_element1 = create_element(element4)

#        print "\nelement4:       ", element4
#        print "ffc_element4:     ", ffc_element4
#        print "created_element1: ", created_element1
        self.assertEqual(ffc_element4.__repr__(), created_element1.__repr__())

if __name__ == "__main__":
    unittest.main()