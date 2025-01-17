// -*- C++ -*-


/* This software was produced by NIST, an agency of the U.S. government,
 * and by statute is not subject to copyright in the United States.
 * Recipients of this software assume all responsibilities associated
 * with its operation, modification and maintenance. However, to
 * facilitate maintenance we ask that before distributing modified
 * versions of this software, you first contact the authors at
 * oof_manager@nist.gov. 
 */


#ifndef CIJKL_H
#define CIJKL_H

#include "engine/symmmatrix.h"
#include <iostream>
#include <string>
#include <vector>

class SymTensorIndex;
class COrientation;
class ListOutputVal;

class Cijkl {
private:
  SymmMatrix c;
public:
  Cijkl() : c(6) {}
  Cijkl(const Cijkl &that) : c(that.c) {}
	
  void clear() { c.clear(); }

  // provide all the possible ways of indexing the modulus tensor:
  double &operator()(int, int);
  double operator()(int, int) const;
  double &operator()(int, int, int, int);
  double operator()(int, int, int, int) const;
  double &operator()(const SymTensorIndex&, const SymTensorIndex&);
  double operator()(const SymTensorIndex&, const SymTensorIndex&) const;
	
  Cijkl transform(const COrientation*) const;
  friend SymmMatrix3 operator*(const Cijkl&, const SymmMatrix3&);

  friend std::ostream &operator<<(std::ostream&, const Cijkl&);
};

void copyOutputVals(const Cijkl&, ListOutputVal*,
		    const std::vector<std::string>&);


#endif
