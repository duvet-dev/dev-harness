# Task 1 — Fix GitHealthChecker function-vs-object mismatch

**Status:** 📋 Pending
**Wave:** 32-health-fixes
**Dependencies:** None
**Effort:** 0.2h

## Description

In `src/harness/health.py:23-37`, `_build_service()` imports `read_active_engagement` as a function and passes it directly to `GitHealthChecker`:

```python
from harness.domain.engagement.lifecycle import read_active_engagement
# ...
_git_checker = GitHealthChecker(_git, read_active_engagement, _FreshnessStore())
```

But `GitHealthChecker.__init__` expects `engagement_store` to be an object with a `.read_active_engagement(root)` method (see docstring at `git_health_service.py:38-39`). It calls `self._engagements.read_active_engagement(root)` at lines 61 and 132. Since `self._engagements` is a function, this produces:
`'function' object has no attribute 'read_active_engagement'`

## Fix

Wrap the function in an adapter class in `health.py`:

```python
class _EngagementStore:
    def read_active_engagement(self, root: Path):
        return read_active_engagement(root)
```

Then replace:
```python
_git_checker = GitHealthChecker(_git, read_active_engagement, _FreshnessStore())
```
with:
```python
_git_checker = GitHealthChecker(_git, _EngagementStore(), _FreshnessStore())
```

The `_EngagementStore` should be defined right after `_read_yml` or in the `_build_service()` function scope alongside `_FreshnessStore`.

## Acceptance Criteria

- [ ] `harness shell` no longer shows "Cannot verify branch match: 'function' object has no attribute 'read_active_engagement'"
- [ ] `harness health` branch-match check still functions correctly
