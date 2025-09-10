name: Understand-First task
description: Bug/feature with seeds + failure context to generate a focused lens and tour
title: "[UF] "
labels: ["understand-first"]
body:
  - type: textarea
    id: summary
    attributes:
      label: Summary
      description: What are you trying to fix or add?
  - type: textarea
    id: seeds
    attributes:
      label: Seeds (files/functions/keywords)
      description: e.g., path/to/file.py:fn, failing endpoint, stack trace function
  - type: textarea
    id: failing
    attributes:
      label: Failing logs / stack traces
  - type: textarea
    id: expected
    attributes:
      label: Expected behavior
  - type: textarea
    id: boundaries
    attributes:
      label: Boundary files touched
      description: OpenAPI, proto, SQL schema, env vars, feature flags
