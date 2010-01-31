"""
Compiler stage 4: Code generation
---------------------------------

This module implements the generation of C++ code for the body of each
UFC function from an (optimized) intermediate representation (OIR).
"""

__author__ = "Anders Logg (logg@simula.no) and friends"
__date__ = "2009-12-16"
__copyright__ = "Copyright (C) 2009 " + __author__
__license__  = "GNU GPL version 3 or any later version"

# Last changed: 2010-01-31

# FFC modules
from ffc.log import info, begin, end, debug_code
from ffc.cpp import format, indent
from ffc.cpp import set_float_formatting, set_exception_handling

# FFC code generation modules
from ffc.evaluatebasis import _evaluate_basis, _evaluate_basis_all
from ffc.evaluatebasisderivatives import _evaluate_basis_derivatives, _evaluate_basis_derivatives_all
from ffc.evaluatedof import evaluate_dof_and_dofs, affine_weights
from ffc.interpolatevertexvalues import interpolate_vertex_values

# FFC specialized code generation modules
from ffc import quadrature
from ffc import tensor

# FIXME: Temporary
not_implemented = "// Not implemented, please fix me!"

def generate_code(ir, prefix, options):
    "Generate code from intermediate representation."

    begin("Compiler stage 4: Generating code")

    # FIXME: Document option -fconvert_exceptions_to_warnings
    # FIXME: Remove option epsilon and just rely on precision?

    # Set code generation options
    set_float_formatting(int(options["precision"]))
    set_exception_handling(options["convert_exceptions_to_warnings"])

    # Extract representations
    ir_elements, ir_dofmaps, ir_integrals, ir_forms = ir

    # Generate code for elements
    info("Generating code for %d elements" % len(ir_elements))
    code_elements = [_generate_element_code(ir, prefix, options) for ir in ir_elements]

    # Generate code for dofmaps
    info("Generating code for %d dofmaps" % len(ir_dofmaps))
    code_dofmaps = [_generate_dofmap_code(ir, prefix, options) for ir in ir_dofmaps]

    # Generate code for integrals
    info("Generating code for integrals")
    code_integrals = [_generate_integral_code(ir, prefix, options) for ir in ir_integrals]

    # Generate code for forms
    info("Generating code for forms")
    code_forms = [_generate_form_code(ir, prefix, options) for ir in ir_forms]

    end()

    return code_elements, code_dofmaps, code_integrals, code_forms

def _generate_element_code(ir, prefix, options):
    "Generate code for finite element from intermediate representation."

    # Skip code generation if ir is None
    if ir is None: return None

    # Prefetch formatting to speedup code generation
    ret = format["return"]
    classname = format["classname finite_element"]
    do_nothing = format["do nothing"]

    # Codes generated together
    (evaluate_dof_code, evaluate_dofs_code) = evaluate_dof_and_dofs(ir["evaluate_dof"])

    # Generate code
    code = {}
    code["classname"] = classname(prefix, ir["id"])
    code["members"] = ""
    code["constructor"] = do_nothing
    code["destructor"] = do_nothing
    code["signature"] = ret('"%s"' % ir["signature"])
    code["cell_shape"] = ret(format["cell"](ir["cell_shape"]))
    code["space_dimension"] = ret(ir["space_dimension"])
    code["value_rank"] = ret(ir["value_rank"])
    code["value_dimension"] = _value_dimension(ir["value_dimension"])
    code["evaluate_basis"] = _evaluate_basis(ir["evaluate_basis"])
    code["evaluate_basis_all"] = _evaluate_basis_all(ir["evaluate_basis"])
    code["evaluate_basis_derivatives"] = _evaluate_basis_derivatives(ir["evaluate_basis"])
    code["evaluate_basis_derivatives_all"] = _evaluate_basis_derivatives_all(ir["evaluate_basis"])
    code["evaluate_dof"] = evaluate_dof_code
    code["evaluate_dofs"] = evaluate_dofs_code
    code["interpolate_vertex_values"] = interpolate_vertex_values(ir["interpolate_vertex_values"])
    code["num_sub_elements"] = ret(ir["num_sub_elements"])
    code["create_sub_element"] = _create_foo(prefix, "finite_element", ir["create_sub_element"])

    # Postprocess code
    _postprocess_code(code, options)

    return code

def _generate_dofmap_code(ir, prefix, options):
    "Generate code for dofmap from intermediate representation."

    # Skip code generation if ir is None
    if ir is None: return None

    # Prefetch formatting to speedup code generation
    ret = format["return"]
    classname = format["classname dof_map"]
    declare = format["declaration"]
    assign = format["assign"]
    do_nothing = format["do nothing"]
    switch = format["switch"]

    # Generate code
    code = {}
    code["classname"] = classname(prefix, ir["id"])
    code["members"] = "\nprivate:\n\n  " + declare("unsigned int", "_global_dimension")
    code["constructor"] = assign("_global_dimension", "0")
    code["destructor"] = do_nothing
    code["signature"] = ret('"%s"' % ir["signature"])
    code["needs_mesh_entities"] = _needs_mesh_entities(ir["needs_mesh_entities"])
    code["init_mesh"] = _init_mesh(ir["init_mesh"])
    code["init_cell"] = do_nothing
    code["init_cell_finalize"] = do_nothing
    code["global_dimension"] = ret("_global_dimension")
    code["local_dimension"] = ret(ir["local_dimension"])
    code["max_local_dimension"] = ret(ir["max_local_dimension"])
    code["geometric_dimension"] = ret(ir["geometric_dimension"])
    code["num_facet_dofs"] = ret(ir["num_facet_dofs"])
    code["num_entity_dofs"] = switch("d", [ret(num) for num in ir["num_entity_dofs"]], ret("0"))
    code["tabulate_dofs"] = _tabulate_dofs(ir["tabulate_dofs"])
    code["tabulate_facet_dofs"] = _tabulate_facet_dofs(ir["tabulate_facet_dofs"])
    code["tabulate_entity_dofs"] = _tabulate_entity_dofs(ir["tabulate_entity_dofs"])
    code["tabulate_coordinates"] = _tabulate_coordinates(ir["tabulate_coordinates"])
    code["num_sub_dof_maps"] = ret(ir["num_sub_dof_maps"])
    code["create_sub_dof_map"] = _create_foo(prefix, "dof_map", ir["create_sub_dof_map"])

    # Postprocess code
    _postprocess_code(code, options)

    return code

def _generate_integral_code(ir, prefix, options):
    "Generate code for integrals from intermediate representation."

    # Skip code generation if ir is None
    if ir is None: return None

    if ir["representation"] == "tensor":
        code = tensor.generate_integral_code(ir, prefix, options)
    elif ir["representation"] == "quadrature":
        code = quadrature.generate_integral_code(ir, prefix, options)
    else:
        error("Unknown representation: %s" % ir["representation"])

    # Indent code (unused variables should already be removed)
    _indent_code(code)

    return code

def _generate_form_code(ir, prefix, options):
    "Generate code for form from intermediate representation."

    # Skip code generation if ir is None
    if ir is None: return None

    # Prefetch formatting to speedup code generation
    ret = format["return"]
    classname = format["classname form"]
    do_nothing = format["do nothing"]

    # Generate code
    code = {}
    code["classname"] = classname(prefix, ir["id"])
    code["members"] = ""
    code["constructor"] = do_nothing
    code["destructor"] = do_nothing
    code["signature"] = ret('"%s"' % ir["signature"])
    code["rank"] = ret(ir["rank"])
    code["num_coefficients"] = ret(ir["num_coefficients"])
    code["num_cell_integrals"] = ret(ir["num_cell_integrals"])
    code["num_exterior_facet_integrals"] = ret(ir["num_exterior_facet_integrals"])
    code["num_interior_facet_integrals"] = ret(ir["num_interior_facet_integrals"])
    code["create_finite_element"] = _create_foo(prefix, "finite_element", ir["create_finite_element"])
    code["create_dof_map"] = _create_foo(prefix, "dof_map", ir["create_dof_map"])
    code["create_cell_integral"] = _create_foo_integral(ir, "cell", prefix)
    code["create_exterior_facet_integral"] = _create_foo_integral(ir, "exterior_facet", prefix)
    code["create_interior_facet_integral"] = _create_foo_integral(ir, "interior_facet", prefix)

    # Postprocess code
    _postprocess_code(code, options)
    #debug_code(code, "form")

    return code

#--- Code generation for non-trivial functions ---

def _value_dimension(ir):
    "Generate code for value_dimension."
    ret = format["return"]
    if ir == ():
        return ret(1)
    return format["switch"]("i", [ret(n) for n in ir], ret("0"))

def _needs_mesh_entities(ir):
    """
    Generate code for needs_mesh_entities. ir is a list of num dofs
    per entity.
    """
    ret = format["return"]
    boolean = format["bool"]
    return format["switch"]("d", [ret(boolean(c)) for c in ir], ret(boolean(False)))

def _init_mesh(ir):
    "Generate code for init_mesh. ir is a list of num dofs per entity."
    component = format["component"]
    entities = format["num entities"]
    dimension = format["inner product"](ir, [component(entities, d)
                                             for d in range(len(ir))])
    return "\n".join([format["assign"]("_global_dimension", dimension),
                      format["return"](format["bool"](False))])

def _tabulate_facet_dofs(ir):
    "Generate code for tabulate_facet_dofs."

    assign = format["assign"]
    component = format["component"]
    cases = ["\n".join(assign(component("dofs", i), dof)
                       for (i, dof) in enumerate(facet))
             for facet in ir]
    return format["switch"]("facet", cases)

def _tabulate_dofs(ir):
    "Generate code for tabulate_dofs."

    # Prefetch formats
    add = format["addition"]
    iadd = format["iadd"]
    multiply = format["multiply"]
    assign = format["assign"]
    component = format["component"]
    entity_index = format["entity index"]
    num_entities_format = format["num entities"]

    # Extract representation
    (num_dofs_per_element, num_entities, need_offset) = ir

    # Declare offset if needed
    code = []
    offset_name = "0"
    if need_offset:
        offset_name = "offset"
        code.append(format["declaration"]("unsigned int", offset_name, 0))

    # Generate code for each element
    i = 0
    for num_dofs in num_dofs_per_element:

        # Generate code for each degree of freedom for each dimension
        for (dim, num) in enumerate(num_dofs):

            # Ignore if no dofs for this dimension
            if num == 0: continue

            for k in range(num_entities[dim]):
                v = multiply([num, component(entity_index, (dim, k))])
                for j in range(num):
                    value = add([offset_name, v, j])
                    code.append(assign(component("dofs", i), value))
                    i += 1

            # Update offset corresponding to mesh entity:
            if need_offset:
                addition = multiply([num, component(num_entities_format, dim)])
                code.append(iadd("offset", addition))

    return "\n".join(code)

def _tabulate_coordinates(ir):
    "Generate code for tabulate_coordinates."

    # Raise error if tabulate_coordinates is ill-defined
    if not ir:
        msg = "tabulate_coordinates is not defined for this element"
        return format["exception"](msg)

    # Extract formats:
    inner_product = format["inner product"]
    component = format["component"]
    precision = format["float"]
    assign = format["assign"]

    # Extract coordinates and cell dimension
    cell_dim = len(ir[0])

    # Aid mapping points from reference to physical element
    coefficients = affine_weights(cell_dim)

    # Start with code for coordinates for vertices of cell
    code = [format["cell coordinates"]]

    # Generate code for each point and each component
    for (i, coordinate) in enumerate(ir):

        w = coefficients(coordinate)
        for j in range(cell_dim):
            # Compute physical coordinate
            coords = [component("x", (k, j)) for k in range(cell_dim + 1)]
            value = inner_product(w, coords)

            # Assign coordinate
            code.append(assign(component("coordinates", (i, j)), value))

    return "\n".join(code)

def _tabulate_entity_dofs(ir):
    "Generate code for tabulate_entity_dofs."

    # Extract variables from ir
    entity_dofs, num_dofs_per_entity = ir

    # Prefetch formats
    assign = format["assign"]
    component = format["component"]

    # Add check that dimension and number of mesh entities is valid
    dim = len(num_dofs_per_entity)
    excpt = format["exception"]("d is larger than dimension (%d)" % (dim - 1))
    code = [format["if"]("d > %d" % (dim-1), excpt)]

    # Generate cases for each dimension:
    all_cases = ["" for d in range(dim)]
    for d in range(dim):

        # Ignore if no entities for this dimension
        if num_dofs_per_entity[d] == 0: continue

        # Add check that given entity is valid:
        num_entities = len(entity_dofs[d].keys())
        excpt = format["exception"]("i is larger than number of entities (%d)"
                                    % (num_entities - 1))
        check = format["if"]("i > %d" % (num_entities - 1), excpt)

        # Generate cases for each mesh entity
        cases = ["\n".join(assign(component("dofs", j), dof)
                           for (j, dof) in enumerate(entity_dofs[d][entity]))
                 for entity in range(num_entities)]

        # Generate inner switch with preceding check
        all_cases[d] = "\n".join([check, format["switch"]("i", cases)])

    # Generate outer switch
    code.append(format["switch"]("d", all_cases))

    return "\n".join(code)

#--- Utility functions ---

def _create_foo(prefix, class_name, postfix, numbers=None):
    "Generate code for create_<foo>."
    class_names = ["%s_%s_%d" % (prefix.lower(), class_name, i) for i in postfix]
    cases = [format["return"]("new " + name + "()") for name in class_names]
    default = format["return"](0)
    return format["switch"]("i", cases, default=default, numbers=numbers)

def _create_foo_integral(ir, integral_type, prefix):
    "Generate code for create_<foo>_integral."
    class_name = integral_type + "_integral_" + str(ir["id"])
    postfix = ir["create_" + integral_type + "_integral"]
    return _create_foo(prefix, class_name, postfix, numbers=postfix)

def _postprocess_code(code, options):
    "Postprocess generated code."
    _indent_code(code)
    _remove_code(code, options)

def _indent_code(code):
    "Indent code that should be indented."
    for key in code:
        if not key in ("classname", "members"):
            code[key] = indent(code[key], 4)

def _remove_code(code, options):
    "Remove code that should not be generated."
    for key in code:
        flag = "no-" + key
        if flag in options and options[flag]:
            msg = "// Function %s not generated (compiled with -f%s)" % (key, flag)
            code[key] = format["exception"](msg)