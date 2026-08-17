## Kinopub compatibility and device evidence

For changes where the item applies, record these project-specific gates in addition to the generic PR evidence:

- [ ] Chrome 35/webOS compatibility impact was considered; changes affecting emitted JavaScript, dependencies, bundling, or browser APIs include `yarn build` and `yarn check:es5` validation.
- [ ] TV validation is explicitly classified as performed, still required, or not applicable, with runtime/test evidence never promoted to device evidence.
- [ ] Playback/HLS changes preserve the established recovery, buffer, quality, and loader-boundary invariants, or the PR records the new evidence that justifies replacing one.
- [ ] Diagnostics/reporting contain no full URLs, query strings, tokens, cookies, credentials, subtitle text, or personal viewing data, and new listeners/timers/observers/loaders have deliberate lifecycle cleanup.
- [ ] `ROADMAP.md`, diagnostics/manual-test docs, scenario guidance, or build/CI docs were reconciled when the facts they own changed.
