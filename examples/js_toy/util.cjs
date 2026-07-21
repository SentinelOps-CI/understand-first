/** CommonJS fixture. */
function pipe(x) {
  return double(x);
}

function double(n) {
  return n * 2;
}

module.exports = { pipe, double };
