"Code generator for tensor representation"

__author__ = "Anders Logg (logg@simula.no)"
__date__ = "2004-11-03 -- 2008-06-12"
__copyright__ = "Copyright (C) 2004-2008 Anders Logg"
__license__  = "GNU GPL version 3 or any later version"

# Modified by Kristian B. Oelgaard 2007
# Modified by Marie Rognes (meg@math.uio.no) 2007

# Python modules
from sets import Set

# FFC common modules
from ffc.common.constants import *

# FFC tensor representation modules
from ffc.compiler.representation.tensor.monomialtransformation import MonomialIndex

# FFC format modules
from ffc.compiler.format.removeunused import *

class UFLTensorGenerator:
    
    def generate_integrals(self, form_representation, format):
        "Generate code for all integrals."

        code = {}

        # Set represenation
        code["representation"] = "tensor"

        # Generate incremental code for now, might be an option later
        incremental = True

        # Generate code for cell integrals
        code.update(_generate_cell_integrals(form_representation, incremental, format))

        # Generate code for exterior facet integrals
        code.update(_generate_exterior_facet_integrals(form_representation, incremental, format))

        # Generate code for interior facet integrals
        code.update(_generate_interior_facet_integrals(form_representation, incremental, format))

        return code

def _generate_cell_integrals(form_representation, incremental, format):
    "Generate code for cell integrals."

    code = {}

    # Check if code needs to be generated
    if len(form_representation.cell_integrals) == 0:
        return code

    # Generate code for all sub domains
    debug("Generating code for cell integrals using tensor representation...")
    for (sub_domain, terms) in enumerate(form_representation.cell_integrals):
        if len(terms) > 0:
            code[("cell_integral", sub_domain)] = _generate_cell_integral(terms, incremental, format)
    debug("done")

    return code

def _generate_exterior_facet_integrals(form_representation, incremental, format):
    "Generate code for exterior facet integrals."

    # FIXME: Not implemented
    return {}

    # Check if code needs to be generated
    if not form_representation.exterior_facet_integrals:
        return {}

    # Generate code for all sub domains
    debug("Generating code for cell integrals using quadrature representation...")
    for i, integral in form_representation.exterior_facet_integrals.items():
        code[("exterior_facet_integral", subdomain)] = _generate_exterior_facet_integral(integral, i, format)
    debug("done")

    return code

def _generate_interior_facet_integrals(form_representation, incremental, format):
    "Generate code for interior facet integrals."

    # FIXME: Not implemented
    return {}

    # Check if code needs to be generated
    if not form_representation.interior_facet_integrals:
        return {}

    # Generate code for all sub domains
    debug("Generating code for cell integrals using quadrature representation...")
    for subdomain, integral in form_representation.interior_facet_integrals.items():
        code[("interior_facet_integral", subdomain)] = _generate_interior_facet_integral(integral, format)
    debug("done")

    return code

def _generate_cell_integral(terms, incremental, format):
    """Generate dictionary of code for cell integral from the given
    form representation according to the given format"""

    # Special case: zero contribution
    if len(terms) == 0:

        return {"tabulate_tensor": element_code, "members": ""}

    # FIXME: Temporary while testing
    cell_dimension = 2

    debug("")

    # Generate element code + set of used geometry terms
    element_code, geo_set, tensor_ops = _generate_element_tensor(terms, incremental, format)

    # Generate geometry code + set of used coefficients + set of jacobi terms
    geo_code, coeff_set, trans_set, geo_ops = _generate_geometry_tensors(terms, geo_set, format)
    total_ops = tensor_ops + geo_ops

    # Get Jacobian snippet
    jacobi_code = [format["generate jacobian"](cell_dimension, "cell")]

    # Remove unused declarations
    code = _remove_unused(jacobi_code, trans_set, format)

    # Add coefficient and geometry tensor declarations
    code.append(format["comment"]("Number of operations to compute element tensor = %d" % total_ops))
    code += geo_code

    # Add element code
    code += [""] + [format["comment"]("Compute element tensor")]
    code += element_code

    debug("Number of operations to compute tensor: %d" % total_ops)

    return {"tabulate_tensor": code, "members": ""}

def generate_exterior_facet_integral(form_representation, sub_domain, format):
    """Generate dictionary of code for exterior facet integral from the given
    form representation according to the given format"""

    # FIXME: Temporary while testing
    cell_dimension = 2

    # Extract terms for sub domain
    terms = [[term for term in t if term.monomial.integral.sub_domain == sub_domain] for t in form_representation.exterior_facet_tensors]

    # Special case: zero contribution
    if all([len(t) == 0 for t in terms]):
        element_code = _generate_zero_element_tensor(form_representation.exterior_facet_tensors[0], format)
        return {"tabulate_tensor": (element_code, []), "members": ""}

    num_facets = len(terms)
    cases = [None for i in range(num_facets)]

    # Generate element code + set of used geometry terms
    geo_set = Set()
    debug("")
    tensor_ops = 0
    for i in range(num_facets):
        case, g_set, tensor_ops = _generate_element_tensor(terms[i], format)
        cases[i] = case
        geo_set = geo_set | g_set
        debug("Number of operations to compute element tensor for facet %d: %d"% (i, tensor_ops))

    # Generate code for geometry tensor (should be the same so pick first)
    # Generate set of used coefficients + set of jacobi terms
    geo_code, coeff_set, trans_set, geo_ops = _generate_geometry_tensors(terms[0], geo_set, format)
    debug("Number of operations to compute geometry terms (should be added): %d" % geo_ops)
    total_ops = tensor_ops + geo_ops

    # Generate code for manipulating coefficients (should be the same so pick first)
    coeff_code = _generate_coefficients(terms[0], coeff_set, format)

    # Get Jacobian snippet
    jacobi_code = [format["generate jacobian"](cell_dimension, "exterior facet")]

    # Remove unused declarations
    code = _remove_unused(jacobi_code, trans_set, format)

    code.append(format["comment"]("Number of operations to compute element tensor = %d" % total_ops))

    # Add coefficient and geometry tensor declarations
    code += coeff_code + geo_code

    # Add element code
    code += [""] + [format["comment"]("Compute element tensor for all facets")]

    return {"tabulate_tensor": (code, cases), "members": ""}

def generate_interior_facet_integral(form_representation, sub_domain, format):
    """Generate dictionary of code for interior facet integral from the given
    form representation according to the given format"""

    # Extract terms for sub domain
    terms = [[[term for term in t2 if term.monomial.integral.sub_domain == sub_domain] for t2 in t1] for t1 in form_representation.interior_facet_tensors]

    # Special case: zero contribution
    if all([len(t) == 0 for tt in terms for t in tt]):
        element_code = _generate_zero_element_tensor(form_representation.interior_facet_tensors[0][0], format)
        return {"tabulate_tensor": (element_code, []), "members": ""}

    num_facets = len(terms)
    cases = [[None for j in range(num_facets)] for i in range(num_facets)]

    # Generate element code + set of used geometry terms
    geo_set = Set()
    debug("")
    tensor_ops = 0
    for i in range(num_facets):
        for j in range(num_facets):
            case, g_set, tensor_ops = _generate_element_tensor(terms[i][j], format)
            cases[i][j] = case
            geo_set = geo_set | g_set
            debug("Number of operations to compute element tensor for facets (%d, %d): %d" % (i, j, tensor_ops))

    # Generate code for geometry tensor (should be the same so pick first)
    # Generate set of used coefficients + set of jacobi terms
    geo_code, coeff_set, trans_set, geo_ops = _generate_geometry_tensors(terms[0][0], geo_set, format)
    debug("Number of operations to compute geometry terms (should be added): %d" % geo_ops)
    total_ops = tensor_ops + geo_ops

    # Generate code for manipulating coefficients (should be the same so pick first)
    coeff_code = _generate_coefficients(terms[0][0], coeff_set, format)

    # Get Jacobian snippet
    jacobi_code = [format["generate jacobian"](form_representation.cell_dimension, "interior facet")]

    # Remove unused declarations
    code = _remove_unused(jacobi_code, trans_set, format)

    code.append(format["comment"]("Number of operations to compute element tensor = %d" % total_ops))

    # Add coefficient and geometry tensor declarations
    code += coeff_code + geo_code

    # Add element code
    code += [""] + [format["comment"]("Compute element tensor for all facet-facet combinations")]

    return {"tabulate_tensor": (code, cases), "members": ""}

def _generate_geometry_tensors(terms, geo_set, format):
    "Generate list of declarations for computation of geometry tensors"

    # Generate code as a list of declarations
    code = []    

    # Iterate over all terms
    j = 0
    coeff_set = Set()
    trans_set = Set()
    num_ops = 0
    for (i, term) in enumerate(terms):

        # Get list of secondary indices (should be the same so pick first)
        secondary_indices = term.GK[0].secondary_multi_index.indices

        # Iterate over secondary indices
        for a in secondary_indices:

            # Skip code generation if term is not used
            if not format["geometry tensor access"](i, a) in geo_set:
                continue

            # Compute factorized values
            values = []
            jj = j
            for GK in term.GK:
                val, c_set, t_set, entry_ops = _generate_entry(GK, a, jj, format)
                values += [val]
                num_ops += entry_ops
                coeff_set = coeff_set | c_set
                trans_set = trans_set | t_set
                jj += 1

            # Sum factorized values
            if values:
                num_ops += len(values) - 1
            name = format["geometry tensor declaration"](i, a)
            value = format["add"](values)

            # Multiply with determinant factor
            # FIXME: dets = pick_first([GK.determinants for GK in term.GK])
            det = term.GK[0].determinant
            value = _multiply_value_by_det(value, term.GK[0].determinant, format, len(values) > 1)
            num_ops += 1

            # Add determinant to transformation set
            #!if dets:
            #!    d0 = [format["power"](format["determinant"](det.restriction),
            #!                          det.power) for det in dets]
            #!    trans_set.add(format["multiply"](d0))

            # Add declaration
            code += [(name, value)]

        j += len(term.GK)

    # Add comments
    code = [format["comment"]("Compute geometry tensors"), format["comment"]("Number of operations to compute declarations = %d" %num_ops)] + code

    # Add scale factor
    trans_set.add(format["scale factor"])

    return (code, coeff_set, trans_set, num_ops)

def _generate_element_tensor(terms, incremental, format):
    "Generate list of declarations for computation of element tensor"

    # Generate code as a list of declarations
    code = []

    # Get list of primary indices (should be the same so pick first)
    primary_indices = terms[0].A0.primary_multi_index.indices

    # Prefetch formats to speed up code generation
    format_element_tensor  = format["element tensor"]
    format_geometry_tensor = format["geometry tensor access"]
    format_add             = format["add"]
    format_add_equal       = format["add equal"]
    format_subtract        = format["subtract"]
    format_multiply        = format["multiply"]
    format_floating_point  = format["floating point"]
    format_epsilon         = format["epsilon"]

    # Generate code for geometry tensor entries

    gk_tensor = []
    for j in range(len(terms)):
        gk_tensor_j = []
        for a in terms[j].A0.secondary_multi_index.indices:
            gk_tensor_j.append((format_geometry_tensor(j, a), a))
        gk_tensor.append((gk_tensor_j, j))

    # Generate code for computing the element tensor
    k = 0
    num_dropped = 0
    num_ops = 0
    zero = format_floating_point(0.0)
    geo_set = Set()
    for i in primary_indices:
        name = format_element_tensor(i, k)
        value = None
        for (gka, j) in gk_tensor:
            A0 = terms[j].A0
            for (gk, a) in gka:                
                a0 = A0.A0[tuple(i + a)]
                if abs(a0) > format_epsilon:
                    if value and a0 < 0.0:
                        value = format_subtract([value, format_multiply([format_floating_point(-a0), gk])])
                        geo_set.add(gk)
                        num_ops += 1
                    elif value:
                        value = format_add([value, format_multiply([format_floating_point(a0), gk])])
                        geo_set.add(gk)
                        num_ops += 1
                    else:
                        value = format_multiply([format_floating_point(a0), gk])
                        geo_set.add(gk)
                    num_ops += 1
                else:
                    num_dropped += 1
        value = value or zero
        if incremental:
            code += [format_add_equal(name, value)]
        else:
            code += [(name, value)]
        k += 1

    code = [format["comment"]("Number of operations to compute tensor = %d" % num_ops)] + code
    return (code, geo_set, num_ops)

def _generate_entry(GK, a, i, format):
    "Generate code for the value of entry a of geometry tensor G"

    coeff_set = Set()
    trans_set = Set()

    # Compute product of factors outside sum
    factors = []
    num_ops = 0
    for j in range(len(GK.coefficients)):
        c = GK.coefficients[j]
        if not c.index.index_type == MonomialIndex.EXTERNAL:
            #coefficient = format["coefficient"](c.number, i, j, c.index(secondary=a))
            coefficient = format["coefficient"](c.number, c.index(secondary=a))
            coeff_set.add(coefficient)
            factors += [coefficient]

    for t in GK.transforms:
        if not (t.index0.index_type == MonomialIndex.EXTERNAL or t.index1.index_type == MonomialIndex.EXTERNAL):
            trans = format["transform"](t.transform_type,
                                        t.index0(secondary=a),
                                        t.index1(secondary=a), 
                                        t.restriction)
            factors += [trans]
            trans_set.add(trans)

    if factors:
        num_ops += len(factors) - 1

    monomial = format["multiply"](factors)
    if monomial: f0 = [monomial]
    else: f0 = []

    # Compute sum of monomials inside sum
    terms = []
    for b in GK.external_multi_index.indices:
        factors = []
        for j in range(len(GK.coefficients)):
            c = GK.coefficients[j]
            if c.index.index_type == MonomialIndex.EXTERNAL:
                #coefficient = format["coefficient"](c.number, i, j, c.index([], a, [], b))
                coefficient = format["coefficient"](c.number, c.index(secondary=a))
                coeff_set.add(coefficient)
                factors += [coefficient]
        for t in GK.transforms:
            if t.index0.index_type == MonomialIndex.EXTERNAL or t.index1.index_type == MonomialIndex.EXTERNAL:
                trans = format["transform"](t.transform_type,
                                            t.index0(secondary=a, external=b),
                                            t.index1(secondary=a, external=b),
                                            t.restriction)
                factors += [trans]
                trans_set.add(trans)
        if factors:
            num_ops += len(factors) - 1
        terms += [format["multiply"](factors)]

    if terms:
        num_ops += len(terms) - 1

    sum = format["add"](terms)
    if sum: sum = format["grouping"](sum)
    if sum: f1 = [sum]
    else: f1 = []

    fs = f0 + f1
    if not fs: fs = ["1.0"]
    else:
        num_ops += len(fs) - 1

    # Compute product of all factors
    return (format["multiply"](fs), coeff_set, trans_set, num_ops)

def _multiply_value_by_det(value, det, format, is_sum):
    if not det.power == 0:
        d = [format["power"](format["determinant"](det.restriction), det.power)]
    else:
        d = []
    if value == "1.0":
        v = []
    elif is_sum:
        v = [format["grouping"](value)]
    else:
        v = [value]
    return format["multiply"](d + [format["scale factor"]] + v)

def _remove_unused(code, set, format):
    "Remove unused variables so that the compiler will not complain"

    # Normally, the removal of unused variables should happen at the
    # formatting stage, but since the code for the tensor contraction
    # may grow to considerable size, we make an exception and remove
    # unused variables here when we know the names of the used
    # variables. No searching necessary and much, much, much faster.
    
    if code:
        # Generate body of code, using the format
        lines = format["generate body"](code)

        # Generate auxiliary code line that uses all members of the set (to trick remove_unused)
        line_set = format["add equal"]("A", format["multiply"](set))
        lines += "\n" + line_set

        # Remove unused Jacobi declarations
        code = remove_unused(lines)

        # Delete auxiliary line
        code = code.replace("\n" + line_set, "")

        return [code]
    else:
        return code