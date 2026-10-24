# Prototype (dummy data)

Seeded, made-up data shaped like Oxford: wet winters, dry summers, and a spill on 23–24 Oct 2026. Nothing here is a real forecast.

```bash
python prototype/gen_dummy.py prototype/dummy.json   # regenerate dummy data (optional)
python prototype/build.py                            # -> prototype/index.html (git-ignored)
```

Open `prototype/index.html` in a browser. deck.gl 9.0.38 loads from jsDelivr.

**Status:** the 3D column map is superseded (see `docs/06-website-and-visuals.md`). Reuse the decomposition, reliability, storage-vs-sealing and anomaly components. When the real pipeline exists, emit JSON with the same fields as `dummy.json` and the charts work unchanged.
