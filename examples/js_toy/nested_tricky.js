/**
 * Wave 17 fixture: patterns that confuse the regex adapter.
 *
 * - Nested function declaration ``handler`` inside ``makeHandler``
 * - Call inside a template literal: process(``...${helper()}...``)
 * - Object-method-like is NOT required; focus on nested + template.
 */
function helper() {
  return "ok";
}

function makeHandler() {
  function handler(ev) {
    return processEvent(ev);
  }
  return handler(helper());
}

function processEvent(ev) {
  const label = `event:${helper()}`;
  return label;
}

module.exports = { helper, makeHandler, processEvent };
