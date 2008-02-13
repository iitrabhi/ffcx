# Code generation format strings for UFC (Unified Form-assembly Code) v. 1.1.
# This code is released into the public domain.
#
# The FEniCS Project (http://www.fenics.org/) 2006-2008.

function_combined = """\
/// This class defines the interface for a general tensor-valued function.

class %(classname)s: public ufc::function
{%(members)s
public:

  /// Constructor
  %(classname)s() : ufc::function()
  {
%(constructor)s
  }

  /// Destructor
  virtual ~%(classname)s()
  {
%(destructor)s
  }

  /// Evaluate function at given point in cell
  virtual void evaluate(double* values,
                        const double* coordinates,
                        const ufc::cell& c) const
  {
%(evaluate)s
  }

};
"""

function_header = """\
/// This class defines the interface for a general tensor-valued function.

class %(classname)s: public ufc::function
{%(members)s
public:

  /// Constructor
  %(classname)s();

  /// Destructor
  virtual ~%(classname)s();

  /// Evaluate function at given point in cell
  virtual void evaluate(double* values,
                        const double* coordinates,
                        const ufc::cell& c) const;

};
"""

function_implementation = """\
/// Constructor
%(classname)s::%(classname)s() : ufc::function()
{
%(constructor)s
}

/// Destructor
%(classname)s::~%(classname)s()
{
%(destructor)s
}

/// Evaluate function at given point in cell
void %(classname)s::evaluate(double* values,
                             const double* coordinates,
                             const ufc::cell& c) const
{
%(evaluate)s
}
"""
