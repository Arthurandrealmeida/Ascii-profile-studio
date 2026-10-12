"""Basic offline tests. Run with: python -m unittest discover -s tests"""
import unittest
from xml.etree import ElementTree as ET
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from generator import load_config, render_svg, normalize_config


class GeneratorTests(unittest.TestCase):
    def test_svg_valid_and_both_themes(self):
        conf = load_config()
        for light in (False, True):
            root = ET.fromstring(render_svg(conf, light=light))
            self.assertTrue(root.tag.endswith('svg'))
            self.assertIn('viewBox', root.attrib)

    def test_custom_fields_and_xml_escape(self):
        conf = load_config()
        conf['sections'] = [{'title':'Meu & trabalho', 'rows':[{'label':'Novo <campo>', 'value':'IA & software'}]}]
        svg = render_svg(conf)
        self.assertIn('Novo &lt;campo&gt;', svg)
        self.assertIn('IA &amp; software', svg)
        ET.fromstring(svg)

    def test_invalid_photo_path_rejected(self):
        conf = load_config()
        conf['profile']['photo'] = '../arquivo-privado.jpg'
        with self.assertRaises(ValueError): render_svg(conf)

    def test_section_replaced_without_uptime(self):
        conf = load_config()
        conf['sections'] = [{'title':'Projetos', 'rows':[{'label':'Eu gosto de', 'value':'Criar ferramentas'}]}]
        svg = render_svg(conf)
        self.assertIn('Criar ferramentas', svg)
        self.assertNotIn('Uptime', svg)

if __name__ == '__main__':
    unittest.main()
