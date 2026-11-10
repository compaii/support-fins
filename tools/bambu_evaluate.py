#!/usr/bin/env python3
"""Bounded, offline Support Fins comparison for an existing Bambu project.

Never slices, sends, changes the input, or treats generation as print readiness.
"""
import argparse
import hashlib
import json
from pathlib import Path
import resource
import subprocess
import time
import xml.etree.ElementTree as ET
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
NS = {'m': 'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'}
SETTINGS = ('layer_height', 'wall_loops', 'sparse_infill_density',
            'sparse_infill_pattern', 'nozzle_diameter', 'filament_type',
            'filament_colour', 'nozzle_temperature', 'textured_plate_temp', 'fuzzy_skin')
CASES = {'auto': ['--mode', 'auto'], 'full': ['--mode', 'full', '--separate-walls', 'on'],
         'auto-no-pad': ['--mode', 'auto', '--pad-style', 'off']}
CAP = 64 * 1024 * 1024


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def checked_zip(path):
    z = ZipFile(path)
    if len(z.namelist()) != len(set(z.namelist())) or len(z.namelist()) > 512:
        z.close()
        raise ValueError('ambiguous or oversized project inventory')
    if sum(x.file_size for x in z.infolist()) > 256 * 1024 * 1024:
        z.close()
        raise ValueError('expanded project exceeds 256 MiB')
    return z


def preservation(source, output):
    """Check independent archive bytes and composed placement inputs, not labels."""
    with checked_zip(source) as a, checked_zip(output) as b:
        meshes = [n for n in a.namelist() if n.startswith('3D/Objects/') and n.endswith('.model')]
        if not meshes:
            raise ValueError('this evaluator requires explicit Bambu mesh resources')
        if any(n not in b.namelist() or a.read(n) != b.read(n) for n in meshes):
            raise ValueError('original mesh resources changed; independent geometry qualification required')
        sa = json.loads(a.read('Metadata/project_settings.config'))
        sb = json.loads(b.read('Metadata/project_settings.config'))
        if any(sa.get(k) != sb.get(k) for k in SETTINGS):
            raise ValueError('a selected process/material setting changed')
        ra = ET.fromstring(a.read('3D/3dmodel.model'))
        rb = ET.fromstring(b.read('3D/3dmodel.model'))
        items = [x.attrib for x in rb.findall('m:build/m:item', NS)]
        if any(x.attrib not in items for x in ra.findall('m:build/m:item', NS)):
            raise ValueError('an original build placement or identity changed')
        objects = {x.get('id'): x for x in rb.findall('m:resources/m:object', NS)}
        for obj in ra.findall('m:resources/m:object', NS):
            other = objects.get(obj.get('id'))
            if other is None or ET.tostring(obj) != ET.tostring(other):
                raise ValueError('an original resource/component transform changed')
    return {'original_mesh_resources': len(meshes), 'original_geometry_and_placements_unchanged': True,
            'selected_process_keys_unchanged': list(SETTINGS)}


def limits():
    resource.setrlimit(resource.RLIMIT_FSIZE, (CAP, CAP))
    resource.setrlimit(resource.RLIMIT_CPU, (120, 120))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('project', type=Path)
    ap.add_argument('output', type=Path, help='new disposable directory, maximum 64 MiB')
    ap.add_argument('--case', action='append', choices=CASES)
    ap.add_argument('--node', default='node')
    args = ap.parse_args()
    source = args.project.resolve(strict=True)
    if source.stat().st_size > CAP:
        ap.error('input exceeds 64 MiB')
    with checked_zip(source):
        pass
    args.output.mkdir(parents=True, exist_ok=False)
    start_hash = digest(source)
    report = {'input_sha256': start_hash, 'engine_commit': subprocess.check_output(
        ['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip(),
        'scope': 'Offline generation only. No slicing, printer operation, strength or removal acceptance.',
        'limits': {'directory_bytes': CAP, 'seconds_per_case': 125, 'node_heap_MiB': 1536},
        'retention': 'One comparison directory; retire generated drafts after qualification or rejection. No watcher.',
        'cases': []}
    failed = False
    for name in args.case or list(CASES):
        output = args.output / (name + '.3mf')
        cmd = [args.node, '--max-old-space-size=1536', str(ROOT / 'plugins/cli/support-fins.js'),
               str(source), '--preserve-project', '--disable-native-supports', '--json',
               '-o', str(output), *CASES[name]]
        before = resource.getrusage(resource.RUSAGE_CHILDREN)
        start = time.monotonic()
        row = {'case': name, 'sliced': False, 'ready_to_print': False}
        try:
            run = subprocess.run(cmd, capture_output=True, text=True, timeout=125,
                                 preexec_fn=limits, start_new_session=True)
            row.update(exit_code=run.returncode, elapsed_seconds=time.monotonic() - start)
            (args.output / (name + '.log')).write_text((run.stderr + run.stdout)[-65536:])
            if run.returncode:
                raise ValueError('generation failed; see bounded case log')
            result = json.loads(run.stdout)
            row['objects'] = result['objects']
            row['preservation'] = preservation(source, output)
            row['output_sha256'] = digest(output)
            row['unresolved_regions'] = sum(x['stats'].get('unserved') or 0 for x in result['objects'])
            row['coverage_certified'] = False  # Candidate faces/unserved counts are not contact coverage.
            row['qualification_note'] = 'Re-slice and inspect coverage, contacts and removal; never send this draft automatically.'
        except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
            row['error'] = str(exc)
            failed = True
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
        row['cpu_seconds'] = after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime
        report['cases'].append(row)
        if digest(source) != start_hash:
            raise RuntimeError('input changed during evaluation')
        if sum(p.stat().st_size for p in args.output.rglob('*') if p.is_file()) > CAP:
            raise RuntimeError('comparison directory exceeds retention bound')
        (args.output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps({k: row.get(k) for k in ('case', 'elapsed_seconds', 'cpu_seconds', 'unresolved_regions', 'error')}))
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
