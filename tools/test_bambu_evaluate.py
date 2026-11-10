"""Evidence failures which must not be hidden by successful fin generation."""
import json
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile
from bambu_evaluate import preservation

CORE = 'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'


class Preservation(unittest.TestCase):
    def project(self, path, mesh='original', transform='1 0 0 0 1 0 0 0 1 10 20 0', layer='0.2', component='1'):
        with ZipFile(path, 'w') as z:
            z.writestr('3D/Objects/object_1.model', mesh)
            z.writestr('Metadata/project_settings.config', json.dumps({'layer_height': layer}))
            z.writestr('3D/3dmodel.model', f'<model xmlns="{CORE}"><resources><object id="2">'
                       f'<components><component objectid="{component}"/></components></object></resources>'
                       f'<build><item objectid="2" transform="{transform}"/></build></model>')

    def compare(self, **change):
        with tempfile.TemporaryDirectory() as d:
            a, b = Path(d) / 'a.3mf', Path(d) / 'b.3mf'
            self.project(a)
            self.project(b, **change)
            return preservation(a, b)

    def test_unchanged(self):
        self.assertTrue(self.compare()['original_geometry_and_placements_unchanged'])

    def test_changed_geometry(self):
        with self.assertRaisesRegex(ValueError, 'mesh resources changed'):
            self.compare(mesh='substituted')

    def test_changed_placement(self):
        with self.assertRaisesRegex(ValueError, 'placement'):
            self.compare(transform='1 0 0 0 1 0 0 0 1 11 20 0')

    def test_changed_component(self):
        with self.assertRaisesRegex(ValueError, 'component transform'):
            self.compare(component='9')

    def test_changed_layer(self):
        with self.assertRaisesRegex(ValueError, 'setting changed'):
            self.compare(layer='0.12')


if __name__ == '__main__':
    unittest.main()
