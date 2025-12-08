# GUI Integration Plan

## Goals
- Provide a unified, discoverable UI surface that connects existing chat/RAG flows with the Chungking & Wedding scenario controls.
- Keep FastAPI static asset serving simple while enabling iterative front-end updates without disrupting the API surface.
- Maintain test coverage so GUI entry points stay reachable as features expand.

## Current State
- FastAPI serves static assets from `app/static`, including `index.html` (chat) and the scenario page `chungking_wedding.html`.
- Scenario-specific JS drives `/api/chat`, but cross-page navigation and shared styling remain minimal.
- Tests cover HTTP availability (`tests/test_app.py`), yet there is no end-to-end check of the scenario UI behavior.

## Proposed Architecture
- Use the existing static hosting path (`/static`) and route definitions in `app/main.py` to expose a consolidated landing page with clear navigation tiles.
- Keep per-scenario logic in dedicated JS modules (e.g., `chungking_wedding.js`) while extracting shared helpers (fetch wrappers, transcript rendering) into a common script (e.g., `static/js/common.js`).
- Introduce a lightweight CSS baseline (`static/css/base.css`) to normalize layout across pages; allow scenario-specific overrides.
- Add a build-free workflow: author vanilla HTML/JS/CSS, validated by formatting and linting hooks, without introducing a bundler.

## Integration Steps
1. **Navigation**: Extend `index.html` to link prominently to scenario UIs; add in-app back-links from scenario pages.
2. **Shared Assets**: Create `static/js/common.js` and `static/css/base.css`; refactor scenario scripts/styles to import or rely on these shared assets.
3. **API Contracts**: Document and stabilize the `/api/chat` payload shape consumed by the UI; add type hints in JS (JSDoc) for request/response objects.
4. **State Management**: Centralize scenario selection, system prompts, and chat history handling in the shared helper to reduce duplication.
5. **Accessibility & UX**: Provide keyboard navigation, focus states, and loading/error indicators; ensure text contrast meets WCAG AA.
6. **Testing**: Expand `tests/test_app.py` with static-asset reachability checks for new pages and snapshots of key HTML elements. Consider Playwright smoke tests if browser tooling becomes available.

## Milestones
- **M1**: Shared base styles/scripts in place; navigation links wired between landing and scenario pages.
- **M2**: Scenario scripts refactored to use shared helpers; documented API contract.
- **M3**: Accessibility polish and error states implemented; tests updated for new assets.

## Risks & Mitigations
- **Asset Drift**: Without bundling, duplicated helpers can diverge — mitigated by consolidating shared utilities and documenting usage.
- **API Changes**: Uncoordinated backend adjustments could break the UI — mitigate with contract docs and targeted tests.
- **Testing Gaps**: Lack of browser automation may miss regressions — offset by stronger static checks and server-side HTML assertions.
