## Summary

<!-- What does this PR do and why? -->

## Type of Change

- [ ] Bug fix
- [ ] New feature
- [ ] Refactoring (no functional change)
- [ ] Documentation update
- [ ] Performance improvement

## Test Plan

<!-- How did you verify this works? -->

- [ ] Tested locally with `bench start`
- [ ] Frontend builds without errors (`yarn build`)
- [ ] Linters pass (`ruff check`, `prettier`)

## Checklist

- [ ] Commit messages follow conventional commits format
- [ ] No `frappe.db.sql` in new code (use `frappe.qb`)
- [ ] No `console.log` left in JS
- [ ] Permission checks on new whitelisted endpoints
- [ ] No hardcoded credentials or API keys
