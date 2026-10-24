# Running Worklet 3 on the real Worklet 2 (C++ `wl2bridge`)

From the repo root, with the venv active (see `docs/wl2/HowToGetPybindInterface.md`):

```sh
source .venv/bin/activate            # python3 -m venv .venv first if needed
python -m pip install -r requirements.txt pybind11
make pybind                          # builds build/wl2bridge*.so
```

Run WL3 against it:

```sh
export WL3_CORPUS=data/crawler.json   # optional; this is the default
python -m wl3.cli.main --backend wl3.integration.wl2_backend:create_backend -q "python tutorial"
```

`wl3/integration/wl2_backend.py` puts `build/` on `sys.path`, imports `wl2bridge`
and calls `initialize(corpus)` once (about 6 s for 500 docs), then hands the
module to `Worklet2Adapter`. Nothing else in WL3 changes: the adapter is the
only layer that talks to Worklet 2.

Test: `python -m pytest tests/wl3` (`test_real_wl2_backend.py` is skipped if
`wl2bridge` is not built).

## Known upstream issues (not WL3)
- `data/crawler.json` has no `title` field, so titles show as "(untitled)".
- `CorpusReader.cpp` does not decode `\uXXXX` escapes, so `\u0000` separators
  appear as literal `u0000` in snippets.
