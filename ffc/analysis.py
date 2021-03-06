# -*- coding: utf-8 -*-
# Copyright (C) 2007-2019 Anders Logg, Martin Alnaes, Kristian B. Oelgaard,
#                         Michal Habera and others
#
# This file is part of FFC (https://www.fenicsproject.org)
#
# SPDX-License-Identifier:    LGPL-3.0-or-later
"""Compiler stage 1: Analysis

This module implements the analysis/preprocessing of variational
forms, including automatic selection of elements, degrees and
form representation type.
"""

import logging
import os
import warnings
from collections import namedtuple
from typing import Dict, List, Tuple, Union

import numpy

import ufl

logger = logging.getLogger(__name__)


def analyze_ufl_objects(ufl_objects: Union[List[ufl.form.Form], List[ufl.FiniteElement], List],
                        parameters: Dict) -> Tuple[Tuple[ufl.algorithms.formdata.FormData], List, Dict, List]:
    """Analyze ufl object(s)

    Parameters
    ----------
    ufl_objects
    parameters

    Returns
    -------
    form_datas
        Form_data objects
    unique_elements
        Unique elements across all forms
    element_numbers
        Mapping to unique numbers for all elements
    unique_coordinate_elements

    """
    logger.info("Compiler stage 1: Analyzing UFL objects")

    form_datas = ()
    unique_elements = set()
    unique_coordinate_elements = set()

    if isinstance(ufl_objects[0], ufl.form.Form):
        forms = ufl_objects

        # Analyze forms
        form_datas = tuple(_analyze_form(form, parameters) for form in forms)

        # Extract unique elements across all forms
        for form_data in form_datas:
            unique_elements.update(form_data.unique_sub_elements)

        # Extract coordinate elements across all forms
        for form_data in form_datas:
            unique_coordinate_elements.update(form_data.coordinate_elements)
    elif isinstance(ufl_objects[0], ufl.FiniteElementBase):
        elements = ufl_objects

        # Extract unique (sub)elements
        unique_elements.update(ufl.algorithms.analysis.extract_sub_elements(elements))
    elif isinstance(ufl_objects[0], ufl.Mesh):
        meshes = ufl_objects

        # Extract unique (sub)elements
        unique_coordinate_elements = [mesh.ufl_coordinate_element() for mesh in meshes]
    else:
        raise TypeError("UFL objects not recognised.")

    # Make sure coordinate elements and their subelements are included
    unique_elements.update(ufl.algorithms.analysis.extract_sub_elements(unique_coordinate_elements))

    # Sort elements
    unique_elements = ufl.algorithms.sort_elements(unique_elements)
    unique_coordinate_elements = sorted(unique_coordinate_elements, key=lambda x: repr(x))

    # Compute element numbers
    element_numbers = {element: i for i, element in enumerate(unique_elements)}

    analyze_ufl_data = namedtuple(
        'analyze_ufl_data', ['form_data', 'unique_elements', 'element_numbers', 'unique_coordinate_elements'])
    return analyze_ufl_data(form_data=form_datas, unique_elements=unique_elements,
                            element_numbers=element_numbers,
                            unique_coordinate_elements=unique_coordinate_elements)


def _analyze_form(form: ufl.form.Form, parameters: Dict) -> ufl.algorithms.formdata.FormData:
    """Analyzes form and attaches metadata

    Parameters
    ----------
    form
    parameters

    Returns
    -------
    form_data
        Form data computed by UFL with metadata attached

    Note
    ----
    The main workload of this function is extraction of unique/default metadata
    from parameters, integral metadata or inherited fro UFL
    (in case of quadrature degree)

    """

    # Check that form is not empty
    if form.empty():
        logger.error("Form (%s) seems to be zero: cannot compile it." % str(form))
        raise RuntimeError("Form (%s) seems to be zero: cannot compile it." % str(form))

    # There is no support for custom integrals
    # We assume at this point, that lacking support for these
    # integrals is the same across both representations, tsfc and uflacs
    if _has_custom_integrals(form):
        raise RuntimeError("Form (%s) contains unsupported custom integrals." % str(form))

    #
    # ---- Extract representation across all integrals in this form
    #
    # The priority of representation determination is following
    #
    # 1. Enviromental variable FFC_FORCE_REPRESENTATION
    # 2. parameters["representation"]
    # 3. specified in metadata of integral
    representations = set(
        integral.metadata().get("representation", "auto") for integral in form.integrals())

    # Remove "auto" to see representations set by user
    representations.discard("auto")

    if parameters["representation"] in ["uflacs", "tsfc"]:
        representation = parameters["representation"]
    elif len(representations) == 1:
        # If user set just one representation return it
        representation = representations.pop()
    elif len(representations) == 0:
        # If user didnt set any default to uflacs
        representation = "uflacs"
    else:
        # Don't tolerate user requests for mixing representations in same
        # form due to restrictions in preprocessing
        raise RuntimeError("Cannot mix uflacs and tsfc representation in a single form.")

    # Hack to override representation with environment variable
    forced_r = os.environ.get("FFC_FORCE_REPRESENTATION")
    if forced_r:
        warnings.warn(
            "representation:    forced by $FFC_FORCE_REPRESENTATION to '{}'".format(forced_r))
        representation = forced_r

    logger.info("Found representation '{}' for form {}.".format(representation, str(form)))

    # Get complex mode
    complex_mode = "complex" in parameters.get("scalar_type", "double")

    # Compute form metadata
    if representation == "uflacs":
        form_data = ufl.algorithms.compute_form_data(
            form,
            do_apply_function_pullbacks=True,
            do_apply_integral_scaling=True,
            do_apply_geometry_lowering=True,
            preserve_geometry_types=(ufl.classes.Jacobian, ),
            do_apply_restrictions=True,
            do_append_everywhere_integrals=False,  # do not add dx integrals to dx(i) in UFL
            complex_mode=complex_mode)
    elif representation == "tsfc":
        # TSFC provides compute_form_data wrapper using correct kwargs
        from tsfc.ufl_utils import compute_form_data as tsfc_compute_form_data
        form_data = tsfc_compute_form_data(form, complex_mode=complex_mode)
    else:
        raise RuntimeError("Unexpected representation \"{}\" for form preprocessing.".format(representation))

    # Attach common representation to FormData
    # Again, representation is the same for all integrals in this Form
    form_data.representation = representation

    #
    # Determine unique quadrature degree, quadrature scheme and precision per
    # each integral data
    #
    for integral_data in form_data.integral_data:
        # Iterate through groups of integral data
        #
        # There is one integral data for all integrals with same domain,
        # itype, subdomain_id (but possibly different metadata)

        # Quadrature degree and quadrature scheme must be the same
        # for all integrals in this integral data group, i.e. must
        # be the same for for the same (domain, itype, subdomain_id)

        #
        # ----- Extract common quadrature degree
        #
        # The priority of quadrature degree determination is following
        #
        # 1. parameters["quadrature_degree"]
        # 2. specified in metadata of integral
        # 3. estimated by UFL
        quadrature_degrees = set([integral.metadata().get("quadrature_degree", "auto")
                                  for integral in integral_data.integrals])
        quadrature_degrees.discard("auto")

        # Find all estimated polynomial degrees by UFL for all integrals in this
        # integral data group
        estimated_quadrature_degrees = [integral.metadata()["estimated_polynomial_degree"]
                                        for integral in integral_data.integrals]

        if isinstance(parameters["quadrature_degree"], int):
            # Quadrature degree is forced by FFC paramaters
            qd = parameters["quadrature_degree"]
        elif len(quadrature_degrees) == 1:
            qd = quadrature_degrees.pop()
        elif len(quadrature_degrees) == 0:
            # If there are more integrals in this integral data group
            # and UFL estimated different degrees we pick maximum
            #
            # Quadrature degree is then unnecessary high for some integrals
            # in this integral data group, but no approximation error is introduced
            # TODO: Possibly add warning for user
            qd = max(estimated_quadrature_degrees)
        elif len(quadrature_degrees) > 1:
            raise RuntimeError("Only one quadrature degree allowed within integrals grouped by subdomain.")
        else:
            raise RuntimeError("Unable to determine quadrature degree.")

        tdim = integral_data.domain.topological_dimension()
        _check_quadrature_degree(qd, tdim)

        #
        # ----- Extract common quadrature rule
        #
        # The priority of quadrature rule determination is following
        #
        # 1. parameters["quadrature_rule"]
        # 2. specified in metadata of integral
        quadrature_rules = set([integral.metadata().get("quadrature_rule", None)
                                for integral in integral_data.integrals])
        quadrature_rules.discard(None)

        if isinstance(parameters["quadrature_rule"], str):
            qr = parameters["quadrature_rule"]
        elif len(quadrature_rules) == 1:
            qr = quadrature_rules.pop()
        elif len(quadrature_rules) == 0:
            qr = "default"
        elif len(quadrature_rules) > 1:
            raise RuntimeError("Only one quadrature scheme allowed within integrals grouped by subdomain.")
        else:
            raise RuntimeError("Unable to determine quadrature rule.")

        #
        # ----- Extract precision
        #
        # The priority of precision determination is following
        #
        # 1. parameters["precision"]
        # 2. specified in metadata of integral
        precisions = set([integral.metadata().get("precision", None)
                          for integral in integral_data.integrals])
        precisions.discard(None)

        if isinstance(parameters["precision"], int):
            p = parameters["precision"]
        elif len(precisions) == 1:
            p = precisions.pop()
        elif len(precisions) == 0:
            p = numpy.finfo("double").precision + 1  # == 16
        elif len(precisions) > 1:
            raise RuntimeError("Only one precision allowed within integrals grouped by subdomain.")
        else:
            raise RuntimeError("Unable to determine quadrature degree.")

        integral_data.metadata["quadrature_degree"] = qd
        integral_data.metadata["quadrature_rule"] = qr
        integral_data.metadata["precision"] = p

        # Reconstruct integrals to avoid modifying the input integral,
        # which would affect the signature computation if the integral
        # was used again in the user program.  Modifying attributes of
        # form_data.integral_data is less problematic since it's
        # lifetime is internal to the form compiler pipeline.
        for i, integral in enumerate(integral_data.integrals):
            integral_data.integrals[i] = integral.reconstruct(
                metadata={"quadrature_degree": qd, "quadrature_rule": qr, "precision": p})

    return form_data


def _has_custom_integrals(o) -> bool:
    """Check for custom integrals

    Note
    ----
    Presence of custom integral in integrals/forms is determining the
    representation to be used.

    """
    if isinstance(o, ufl.integral.Integral):
        return o.integral_type() in ufl.custom_integral_types
    elif isinstance(o, ufl.classes.Form):
        return any(_has_custom_integrals(itg) for itg in o.integrals())
    elif isinstance(o, (list, tuple)):
        return any(_has_custom_integrals(itg) for itg in o)
    else:
        raise NotImplementedError


def _check_quadrature_degree(degree: int, top_dim: int) -> None:
    """Check that quadrature degree does not result in a unreasonable high
    number of integration points.
    """
    num_points = ((degree + 1 + 1) // 2)**top_dim
    if num_points >= 100:
        warnings.warn(
            "Number of integration points per cell is : {}. Consider using 'quadrature_degree' to reduce number.".
            format(num_points))
