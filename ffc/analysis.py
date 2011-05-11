"""
Compiler stage 1: Analysis
--------------------------

This module implements the analysis/preprocessing of variational
forms, including automatic selection of elements, degrees and
form representation type.
"""

# Copyright (C) 2007-2010 Anders Logg and Kristian B. Oelgaard
#
# This file is part of FFC.
#
# FFC is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# FFC is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with FFC. If not, see <http://www.gnu.org/licenses/>.
#
# Modified by Marie E. Rognes, 2010
#
# First added:  2007-02-05
# Last changed: 2011-05-02

# UFL modules
from ufl.common import istr, tstr
from ufl.integral import Measure
from ufl.finiteelement import MixedElement, EnrichedElement
from ufl.algorithms import estimate_max_polynomial_degree
from ufl.algorithms import estimate_total_polynomial_degree
from ufl.algorithms import sort_elements
from ufl.algorithms import compute_form_arities

# FIXME: Import error when trying to import extract_sub_elements
# FIXME: from ufl.algorithmms.
from ufl.algorithms.analysis import extract_elements, extract_sub_elements

# FFC modules
from ffc.log import log, info, begin, end, warning, debug, error, ffc_assert
from ffc.utils import all_equal
from ffc.quadratureelement import default_quadrature_degree
from ffc.utils import all_equal
from ffc.tensor import estimate_cost

def analyze_forms(forms, object_names, parameters, common_cell=None):
    """
    Analyze form(s), returning

       form_datas      - a tuple of form_data objects
       unique_elements - a tuple of unique elements across all forms
       element_data    - a dictionary of auxiliary element data
    """

    begin("Compiler stage 1: Analyzing form(s)")

    # Analyze forms
    form_datas = tuple(_analyze_form(form,
                                     object_names,
                                     parameters,
                                     common_cell) for form in forms)

    # Extract unique elements
    unique_elements = []
    for form_data in form_datas:
        for element in form_data.unique_sub_elements:
            if not element in unique_elements:
                unique_elements.append(element)

    # Sort elements
    unique_elements = sort_elements(unique_elements)

    # Compute element numbers
    element_numbers = _compute_element_numbers(unique_elements)

    # Compute element cells and degrees (when cell or degree is undefined)
    element_cells = _auto_select_cells(unique_elements)
    element_degrees = _auto_select_degrees(unique_elements)

    # Group auxiliary element data
    element_data = {"numbers": element_numbers,
                    "cells":   element_cells,
                    "degrees": element_degrees}

    end()

    return form_datas, unique_elements, element_data

def analyze_elements(elements, parameters):

    begin("Compiler stage 1: Analyzing form(s)")

    # Extract unique elements
    unique_elements = []
    element_numbers = {}
    for element in elements:
        # Get all (unique) nested elements.
        for e in _get_nested_elements(element):
            # Check if element is present
            if not e in element_numbers:
                element_numbers[e] = len(unique_elements)
                unique_elements.append(e)
    # Sort elements
    unique_elements = sort_elements(unique_elements)

    # Build element map
    element_numbers = _compute_element_numbers(unique_elements)

    # Update scheme for QuadratureElements
    scheme = parameters["quadrature_rule"]
    if scheme == "auto":
        scheme = "default"
    for element in unique_elements:
        if element.family() == "Quadrature":
            element._quad_scheme = scheme
    end()

    # Group auxiliary element data
    element_data = {"numbers": element_numbers}

    return (), unique_elements, element_data

def _compute_element_numbers(elements):
    "Build map from elements to element numbers."
    element_numbers = {}
    for (i, element) in enumerate(elements):
        element_numbers[element] = i
    return element_numbers

def _get_nested_elements(element):
    "Get unique nested elements (including self)."
    nested_elements = [element]
    for e in element.sub_elements():
        nested_elements += _get_nested_elements(e)
    return set(nested_elements)

def _analyze_form(form, object_names, parameters, common_cell=None):
    "Analyze form, returning preprocessed form."

    # Check that form is not empty
    ffc_assert(len(form.integrals()),
               "Form (%s) seems to be zero: cannot compile it." % str(form))

    # Compute form metadata
    form_data = form.compute_form_data(object_names, common_cell)

    info("")
    info(str(form_data))

    # Extract preprocessed form
    preprocessed_form = form_data.preprocessed_form

    # Check that all terms in form have same arity
    ffc_assert(len(compute_form_arities(preprocessed_form)) == 1,
               "All terms in form must have same rank.")

    # Attach integral meta data
    _attach_integral_metadata(form_data, common_cell, parameters)

    # Attach cell data
    _attach_cell_data(form_data, common_cell)

    return form_data

def _attach_integral_metadata(form_data, common_cell, parameters):
    "Attach integral metadata"

    # Recognized metadata keys
    metadata_keys = ("representation", "quadrature_degree", "quadrature_rule")

    # Iterate over integral collections
    quad_schemes = []
    for (domain_type, domain_id, integrals, metadata) in form_data.integral_data:

        # Iterate over integrals
        integral_metadatas = []
        for integral in integrals:

            # Get metadata for integral
            integral_metadata = integral.measure().metadata() or {}
            for key in metadata_keys:
                if not key in integral_metadata:
                    integral_metadata[key] = parameters[key]

            # Check metadata
            r  = integral_metadata["representation"]
            qd = integral_metadata["quadrature_degree"]
            qr = integral_metadata["quadrature_rule"]
            if not r in ("quadrature", "tensor", "auto"):
                info("Valid choices are 'tensor', 'quadrature' or 'auto'.")
                error("Illegal choice of representation for integral: " + str(r))
            if not qd  == "auto":
                qd = int(qd)
                if not qd >= 0:
                    info("Valid choices are nonnegative integers or 'auto'.")
                    error("Illegal quadrature degree for integral: " + str(qd))
            if not qr in ("default", "canonical", "auto"):
                info("Valid choices are 'default', 'canonical' or 'auto'.")
                error("Illegal choice of quadrature rule for integral: " + str(qr))

            # Automatic selection of representation
            if r == "auto":
                r = _auto_select_representation(integral,
                                                form_data.unique_sub_elements)
                info("representation:    auto --> %s" % r)
                integral_metadata["representation"] = r
            else:
                info("representation:    %s" % r)

            # Automatic selection of quadrature degree
            if qd == "auto":
                qd = _auto_select_quadrature_degree(integral,
                                                    r,
                                                    form_data.unique_sub_elements)
                info("quadrature_degree: auto --> %d" % qd)
                integral_metadata["quadrature_degree"] = qd
            else:
                info("quadrature_degree: %d" % qd)

            # Automatic selection of quadrature rule
            if qr == "auto":
                # Just use default for now.
                qr = "default"
                info("quadrature_rule:   auto --> %s" % qr)
                integral_metadata["quadrature_rule"] = qr
            else:
                info("quadrature_rule:   %s" % qr)
            quad_schemes.append(qr)

            # Append to list of metadata
            integral_metadatas.append(integral_metadata)

        # Extract common metadata for integral collection
        if len(integrals) == 1:
            metadata.update(integral_metadatas[0])
        else:

            # Check that representation is the same
            # FIXME: Why must the representation within a sub domain be the same?
            representations = [md["representation"] for md in integral_metadatas]
            if not all_equal(representations):
                r = "quadrature"
                info("Integral representation must be equal within each sub domain, using %s representation." % r)
            else:
                r = representations[0]

            # Check that quadrature degree is the same
            # FIXME: Why must the degree within a sub domain be the same?
            quadrature_degrees = [md["quadrature_degree"] for md in integral_metadatas]
            if not all_equal(quadrature_degrees):
                qd = max(quadrature_degrees)
                info("Quadrature degree must be equal within each sub domain, using degree %d." % qd)
            else:
                qd = quadrature_degrees[0]

            # Check that quadrature rule is the same
            # FIXME: Why must the rule within a sub domain be the same?
            quadrature_rules = [md["quadrature_rule"] for md in integral_metadatas]
            if not all_equal(quadrature_rules):
                qr = "canonical"
                info("Quadrature rule must be equal within each sub domain, using %s rule." % qr)
            else:
                qr = quadrature_rules[0]

            # Update common metadata
            metadata["representation"] = r
            metadata["quadrature_degree"] = qd
            metadata["quadrature_rule"] = qr

    # Update scheme for QuadratureElements
    if not all_equal(quad_schemes):
        scheme = "canonical"
        info("Quadrature rule must be equal within each sub domain, using %s rule." % qr)
    else:
        scheme = quad_schemes[0]
    for element in form_data.sub_elements:
        if element.family() == "Quadrature":
            element._quad_scheme = scheme

def _attach_cell_data(form_data, common_cell):
    "Attach cell data"
    common_cell = _extract_common_cell(form_data.unique_sub_elements, common_cell)
    form_data.cell = common_cell
    form_data.geometric_dimension = common_cell.geometric_dimension()
    form_data.topological_dimension = common_cell.topological_dimension()
    form_data.num_facets = common_cell.num_facets()
    return form_data

def _get_sub_elements(element):
    "Get sub elements."
    sub_elements = [element]
    if isinstance(element, MixedElement):
        for e in element.sub_elements():
            sub_elements += _get_sub_elements(e)
    elif isinstance(element, EnrichedElement):
        for e in element._elements:
            sub_elements += _get_sub_elements(e)
    return sub_elements

def _extract_common_cell(elements, common_cell):
    "Extract common cell for elements"
    if common_cell is None:
        cells = [e.cell() for e in elements]
        cells = [c for c in cells if not c.is_undefined()]
        if len(cells) == 0:
            error("""\
Unable to extract common element; missing cell definition in form.""")
        common_cell = cells[0]
    return common_cell

def _extract_common_degree(elements):
    "Extract common degree for all elements"
    common_degree = max([e.degree() for e in elements])
    if common_degree is None:
        common_degree = default_quadrature_degree
    return common_degree

def _auto_select_cells(elements, common_cell=None):
    """
    Automatically select cell for all elements of the form in cases
    where this has not been specified by the user. This feature is
    used by DOLFIN to allow the specification of Expressions with
    undefined cells.
    """

    # Extract common cell
    common_cell = _extract_common_cell(elements, common_cell)

    # Set missing cells
    element_cells = {}
    for element in elements:
        cell = element.cell()
        if cell.is_undefined():
            info("Adjusting element cell from %s to %s." % \
                     (istr(cell), str(common_cell)))
            element_cells[element] = common_cell

    return element_cells

def _auto_select_degrees(elements):
    """
    Automatically select degree for all elements of the form in cases
    where this has not been specified by the user. This feature is
    used by DOLFIN to allow the specification of Expressions with
    undefined degrees.
    """

    # Extract common degree
    common_degree = _extract_common_degree(elements)

    # Degree must be at least 1 (to work with Lagrange elements)
    common_degree = max(1, common_degree)

    # Set missing degrees
    element_degrees = {}
    for element in elements:
        # Adjust degree
        degree = element.degree()
        if degree is None:
            info("Adjusting element degree from %s to %d" % \
                     (istr(degree), common_degree))
            element_degrees[element] = common_degree

    return element_degrees

def _auto_select_representation(integral, elements):
    """
    Automatically select a suitable representation for integral.
    Note that the selection is made for each integral, not for
    each term. This means that terms which are grouped by UFL
    into the same integral (if their measures are equal) will
    necessarily get the same representation.
    """

    # Get ALL sub elements, needed to check for restrictions of EnrichedElements.
    sub_elements = []
    for e in elements:
        sub_elements += _get_sub_elements(e)

    # Use quadrature representation if we have a quadrature element
    if len([e for e in sub_elements if e.family() == "Quadrature"]):
        return "quadrature"

    # Use quadrature representation if any elements are restricted to
    # UFL.Measure. This is used when integrals are computed over discontinuities.
    if len([e for e in sub_elements if isinstance(e.domain_restriction(), Measure)]):
        return "quadrature"

    # Estimate cost of tensor representation
    tensor_cost = estimate_cost(integral)
    debug("Estimated cost of tensor representation: " + str(tensor_cost))

    # Use quadrature if tensor representation is not possible
    if tensor_cost == -1:
        return "quadrature"

    # Otherwise, select quadrature when cost is high
    if tensor_cost <= 3:
        return "tensor"
    else:
        return "quadrature"

def _auto_select_quadrature_degree(integral, representation, elements):
    "Automatically select a suitable quadrature degree for integral."

    # Use maximum quadrature element degree if any for quadrature representation
    if representation == "quadrature":
        quadrature_degrees = [e.degree() for e in elements if e.family() == "Quadrature"]
        if quadrature_degrees:
            debug("Found quadrature element(s) with the following degree(s): " + str(quadrature_degrees))
            ffc_assert(min(quadrature_degrees) == max(quadrature_degrees), \
                       "All QuadratureElements in an integrand must have the same degree: %s" \
                       % str(quadrature_degrees))
            debug("Selecting quadrature degree based on quadrature element: " + str(quadrature_degrees[0]))
            return quadrature_degrees[0]

    # Otherwise estimate total degree of integrand
    q = estimate_total_polynomial_degree(integral, default_quadrature_degree)
    debug("Selecting quadrature degree based on total polynomial degree of integrand: " + str(q))

    return q
