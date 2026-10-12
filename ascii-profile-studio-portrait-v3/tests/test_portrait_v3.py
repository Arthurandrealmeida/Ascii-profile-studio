"""Tests for high-definition text-only portrait rendering."""
import json
import sys
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET
from urllib.request import Request, urlopen
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from generator import load_config, portrait_cells, render_svg, render_portrait_svg, locate_photo, photo_to_ascii


class PortraitV3Tests(unittest.TestCase):
    def setUp(self):
        self.conf=load_config()

    def test_default_is_detailed_ascii(self):
        self.assertEqual(self.conf['portrait']['mode'], 'portrait')
        self.assertGreaterEqual(self.conf['portrait']['columns'], 60)
        self.assertTrue(self.conf['profile']['photo'].endswith('retrato_fiel.png'))

    def test_output_contains_text_glyphs_no_embedded_raster(self):
        svg = render_svg(self.conf)
        root=ET.fromstring(svg)
        self.assertTrue(root.tag.endswith('svg'))
        forbidden=['<image ', '<foreignObject', 'data:image/', '<feImage']
        for bad in forbidden:self.assertNotIn(bad, svg)
        self.assertGreater(svg.count('<tspan fill='), 500)

    def test_portrait_is_editable_true_character_grid(self):
        cells = portrait_cells(locate_photo(self.conf['profile']['photo']), self.conf['portrait'])
        self.assertEqual(len(cells), self.conf['portrait']['rows'])
        self.assertTrue(all(len(row)==self.conf['portrait']['columns'] for row in cells))
        self.assertTrue(all(len(ch)==1 and 0<=ink<=255 for row in cells for ch,ink in row))
        self.assertGreater(len(set(ink for row in cells for ch,ink in row if ch!=' ')), 20)

    def test_standalone_portrait_and_light_theme_valid(self):
        for light in (False, True):
            svg=render_portrait_svg(self.conf, light=light)
            root=ET.fromstring(svg)
            self.assertTrue(root.tag.endswith('svg'))
            self.assertNotIn('<image ',svg)
        self.assertNotEqual(render_portrait_svg(self.conf),render_portrait_svg(self.conf,light=True))

    def test_legacy_algorithms_untouched(self):
        path=locate_photo(self.conf['profile']['photo'])
        p=self.conf['portrait'].copy()
        p.update(columns=32,rows=25,mode='classic')
        before=photo_to_ascii(path,p)
        p['mode']='edges'
        after=photo_to_ascii(path,p)
        self.assertEqual(len(before),25)
        self.assertEqual(len(after),25)
        self.assertNotEqual(before,after)

    def test_adjustments_change_ascii_cells(self):
        p=self.conf['portrait'].copy()
        photo=locate_photo(self.conf['profile']['photo'])
        one=portrait_cells(photo,p)
        p['zoom']=2.1
        another=portrait_cells(photo,p)
        self.assertNotEqual(one,another)


if __name__=='__main__':unittest.main()
