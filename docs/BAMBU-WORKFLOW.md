# Bambu workflow evaluation in this fork

This fork keeps the upstream geometry engine and adds a repeatable offline
comparison before changing manufacturing practice. No command in this workflow
sends a printer job. Keep source CAD and the original Bambu project unchanged.

## Run a comparison

Requirements: Python 3 on Linux/macOS and Node 20.10 or newer. No Python packages,
network access, account or printer access are needed for this comparison.

```sh
python3 tools/bambu_evaluate.py input.3mf new-comparison-directory
python3 -m unittest discover -s tools -p 'test_bambu_evaluate.py' -v
```

The evaluator runs Auto, Full coverage and Auto without the optional bed pad.
Each produces a separate **draft** 3MF with native supports disabled on the
selected model, plus one bounded JSON report. It checks original mesh resources,
resource/component transforms, build identities and selected process/material
settings independently of the generator. Subtracted/rewritten meshes are refused
by this comparison rather than accepted by labels or volume alone.

Each case has a 125-second wall bound, a 120-second CPU bound, a 1.5 GiB Node heap
and a 64 MiB file bound. The comparison directory is capped at 64 MiB. Keep one
comparison per selected input; retire reproducible drafts after qualification or
rejection. The source project is never overwritten. No watcher/cache service is
installed.

Generation success is not coverage, slicer acceptance or physical acceptance.
`overFaces` is the **candidate** overhang face list, not the surfaces proven to be
supported. `unserved: 0` would also be insufficient to certify removability.

## Current measured example

On one 46,890-triangle functional holder at 45 degrees, with a 0.4 mm nozzle and
0.20 mm layers, a foreground comparison measured:

| Variant | Wall time | Reported unserved regions |
| --- | ---: | ---: |
| Auto | 2.52 s | 2 |
| Full coverage, separate walls | 8.63 s | 2 |
| Auto, no optional bed pad | 2.45 s | 2 |

Those are one-machine measurements, not performance guarantees.

An offline Bambu Studio 02.06 slice of Auto without the optional pad estimated
36.42 g / 2 h 48 min, versus 40.35 g / 3 h 16 min for the existing tree-support
project. However, the fin-only slice warned about **floating regions**. This is
not a qualified saving: missing necessary support can make an invalid job look
cheaper. Generated G-code contained no native Support feature paths. No print
was sent; surface finish, removal force and strength remain untested.
The private specimen and machine profile are deliberately not published here.
The repository retains generic negative tests for geometry, placement, component
and process changes.

## Hybrid supports: design requirement, not an implemented feature

The intended hybrid would keep native supports enabled for the model, add fins
with native support generation disabled on the fins themselves, and block native
supports **only where actual fin contact/coverage has been demonstrated**. It
must preserve existing support prohibitions/enforcers and protect functional
interfaces. Simply painting `overFaces` is incorrect.

The remaining work is a geometric contact/coverage map, verified Bambu facet
painting for the installed client, and source-bound reslicing which demonstrates
both residual support and removal access. Do not use a blocker volume which also
hides a different unsupported roof above it. Compare actual generated toolpaths,
material and time against the unmodified project before any authorized specimen.
Nothing in this document authorizes a print or replacement of a submitted job.

## Rust decision

Do not equate a rewrite with a better support algorithm. First measure the
geometry stages and difficult meshes, then use identical fixtures for contact,
coverage, build transforms and extraction. Rust may be useful for a measured hot
path, memory bounds or a standalone executable; the browser/CLI/project adapters
can keep their existing contracts. The current example spends seconds generating
fins, so a full rewrite is not yet justified as the first material-saving change.
