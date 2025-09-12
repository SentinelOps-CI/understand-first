## Understand-First Analysis

### Repository Scan
- **Functions analyzed**: {{functions_count}}
- **Modules processed**: {{modules_count}}

### Understanding Lens
- **Functions in lens**: {{lens_functions}}
- **Analysis focused on**: Changed files in this PR

### Code Changes Analysis
- **Functions added**: {{added_functions}}
- **Functions removed**: {{removed_functions}}
- **Functions modified**: {{modified_functions}}

### Hot Path Analysis
{{#if runtime_traced}}
- **Runtime traces**: Available
- **Hot functions**: {{hot_functions_count}}
{{else}}
- **Runtime traces**: Not available (run `u trace` to enable)
{{/if}}

### Understanding Tour
An interactive tour has been generated to help reviewers understand the changes.

**Download**: [Understanding Tour]({{tour_url}})

### Code Quality Insights
{{#if high_complexity_functions}}
- **High complexity functions**: {{high_complexity_count}} (complexity > 10)
  {{#each high_complexity_functions}}
  - `{{name}}()` (complexity: {{complexity}})
  {{/each}}
{{/if}}

{{#if side_effect_functions}}
- **Functions with side effects**: {{side_effect_count}}
  {{#each side_effect_functions}}
  - `{{name}}()` (effects: {{side_effects}})
  {{/each}}
{{/if}}

### Key Functions to Review
{{#each key_functions}}
- **`{{name}}()`** - {{description}}
  - Complexity: {{complexity}}
  - Callers: {{callers_count}}
  - Callees: {{callees_count}}
  {{#if side_effects}}
  - Side effects: {{side_effects}}
  {{/if}}
{{/each}}

### Reviewer Checklist
- [ ] I have reviewed the understanding analysis
- [ ] I understand the complexity and side effects of changes
- [ ] I have verified the changes align with the understanding tour
- [ ] I confirm this change maintains code quality standards
- [ ] I have checked for potential breaking changes in dependencies

### Understanding Requirements
{{#if requires_documentation}}
- [ ] **Documentation needed**: High complexity or side effects detected
- [ ] **Tests needed**: Functions with side effects should have comprehensive tests
{{/if}}

{{#if requires_breaking_change_review}}
- [ ] **Breaking change review**: Functions removed or significantly modified
{{/if}}

### Additional Resources
- [Understanding Tour]({{tour_url}})
- [Code Map]({{map_url}})
- [Contract Verification]({{contracts_url}})
