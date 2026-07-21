/**
 * Small JS fixture for Understand-First Wave 15 best-effort analyzer tests.
 */
function add(a, b) {
  return a + b;
}

function compute(x, y) {
  const total = add(x, y);
  return total;
}

function classify(n) {
  if (n < 0) {
    return "neg";
  }
  for (let i = 0; i < n; i++) {
    if (i > 10 && i < 20) {
      return "mid";
    }
  }
  try {
    return String(n);
  } catch (err) {
    return "err";
  }
}

class Calculator {
  scale(v) {
    return add(v, 0);
  }

  run(a, b) {
    return this.scale(compute(a, b));
  }
}

const double = (n) => add(n, n);

module.exports = { add, compute, classify, Calculator, double };
