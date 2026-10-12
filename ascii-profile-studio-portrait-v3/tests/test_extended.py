"""Regression tests for SVG, portrait, public stats and API security."""
import io
import json
import sys
import tempfile
import threading
import unittest
from copy import deepcopy
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app
from generator import (crop_rectangle, generate, load_config, normalize_config, photo_to_ascii,
                       render_svg, locate_photo, write_config, resolve_stats)
from github_stats import fetch_stats


class SvgTest(unittest.TestCase):
    def setUp(self):
        self.c = load_config()

    def test_invalid_xml_characters_stripped(self):
        self.c['sections'] = [{'title': 'Olá\x00\x0b', 'rows': [{'label': 'A\x01', 'value': 'B\x02 & < > 🚀'}]}]
        output = render_svg(self.c)
        ET.fromstring(output)
        self.assertNotIn('\x00', output)
        self.assertNotIn('\x01', output)
        self.assertIn('B &amp; &lt; &gt; 🚀', output)

    def test_addition_deletion_color_are_used(self):
        self.c['theme']['addition'] = '#123abc'
        self.c['theme']['deletion'] = '#ed1234'
        self.c['sections'] = [{'title':'', 'rows': [{'label':'Código','value':'[[+33++]] / [[-9--]]'}]}]
        result = render_svg(self.c)
        self.assertIn('<tspan fill="#123abc">33++</tspan>', result)
        self.assertIn('<tspan fill="#ed1234">9--</tspan>', result)
        ET.fromstring(result)
        self.c['theme']['light']['addition'] = '#abcdef'
        self.assertIn('<tspan fill="#abcdef">33++</tspan>', render_svg(self.c, light=True))

    def test_layout_controls_modify_coordinates_and_bounds(self):
        baseline = render_svg(self.c)
        self.c['layout'].update(column_gap=80, label_width=440, min_height=850)
        changed = render_svg(self.c)
        self.assertNotEqual(baseline, changed)
        self.assertGreaterEqual(int(ET.fromstring(changed).get('height')), 850)

    def test_multiline_wrap_long_labels(self):
        self.c['sections']=[{'title': 'Título' * 15, 'rows':[{'label':'L'*150,'value':'X'*800+'\nY'}]}]
        ET.fromstring(render_svg(self.c))

    def test_nonfinite_values_normalized(self):
        self.c['portrait']['brightness'] = 'nan'
        self.c['layout']['line_height'] = 'inf'
        self.c['portrait']['columns'] = 9999
        normalized=normalize_config(self.c)
        self.assertEqual(normalized['portrait']['brightness'],1.0)
        self.assertEqual(normalized['portrait']['columns'],120)
        self.assertEqual(normalized['layout']['line_height'],1.33)

    def test_excessive_rows_rejected(self):
        self.c['sections'] = [{'rows':[{'label':'x','value':'y'}]*81}]
        with self.assertRaises(ValueError):
            normalize_config(self.c)

    def test_cached_github_markers(self):
        self.c['github']['cached']={'public_repos':1234,'followers':5}
        self.c['sections']=[{'title':'GitHub Stats','rows':[{'label':'Repo','value':'{{github.public_repos}}; {{github.followers}}; {{github.commits_year}}'}]}]
        result=render_svg(self.c)
        self.assertIn('1.234',result)
        self.assertIn('5; —',result)
        ET.fromstring(result)

    def test_custom_crop_and_modes(self):
        p=self.c['portrait']
        original=photo_to_ascii(locate_photo(self.c['profile']['photo']),p)
        p.update(zoom=2.1,center_x=.2,center_y=.9)
        different=photo_to_ascii(locate_photo(self.c['profile']['photo']),p)
        self.assertNotEqual(original,different)
        p['mode']='dither'
        self.assertNotEqual(different,photo_to_ascii(locate_photo(self.c['profile']['photo']),p))
        self.assertEqual(len(original),p['rows'])

    def test_crop_within_image(self):
        self.c['portrait'].update(zoom=4,center_x=1,center_y=0)
        l,t,r,b=crop_rectangle((800,600),self.c['portrait'])
        self.assertTrue(0<=l<r<=800 and 0<=t<b<=600)

    def test_failed_generation_does_not_replace_existing(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'dark_mode.svg'
            target.write_text('original')
            self.c['profile']['photo']='assets/not-existent.png'
            with self.assertRaises(ValueError):generate(self.c,Path(tmp))
            self.assertEqual(target.read_text(),'original')


class StatsTests(unittest.TestCase):
    def test_stats_count_across_pages_and_exclude_forks(self):
        def mock_github(endpoint):
            if endpoint=='users/demo':return {'public_repos':3,'followers':12,'html_url':'https://github.com/demo'}
            return [{'stargazers_count':8,'forks_count':2,'fork':False},
                    {'stargazers_count':9,'forks_count':10,'fork':True},
                    {'stargazers_count':7,'forks_count':1,'fork':False}]
        with patch('github_stats.github_get',side_effect=mock_github):
            response=fetch_stats('demo')
        self.assertEqual(response['cached']['stars_received'],15)
        self.assertEqual(response['cached']['forks_received'],3)
        self.assertIsNone(response['cached']['commits_year'])

    def test_large_repo_count_never_pretends_partial_is_total(self):
        with patch('github_stats.github_get',return_value={'public_repos':1001,'followers':10}):
            response=fetch_stats('demo')
        self.assertIsNone(response['cached']['stars_received'])

    def test_invalid_username_rejected_before_network(self):
        for username in ('', 'x'*50, '../hello', 'ends-'):
            with self.assertRaises(ValueError):fetch_stats(username)


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
        cls.server.allow_remote=False
        cls.port=cls.server.server_address[1]
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.thread.join(5);cls.server.server_close()

    def request(self,path,body=None,origin=None,content_type='application/json',host=None):
        url=f'http://127.0.0.1:{self.port}{path}'
        headers={}
        if body is not None:headers['Content-Type']=content_type
        if origin is not None:headers['Origin']=origin
        if host is not None:headers['Host']=host
        req=Request(url,data=body,headers=headers)
        try:
            with urlopen(req,timeout=8) as response:
                return response.status,response.read()
        except HTTPError as err:
            return err.code,err.read()

    def test_safe_get(self):
        status,body=self.request('/api/config')
        self.assertEqual(status,200)
        self.assertIn('portrait',json.loads(body))
        status,body=self.request('/static/app.js')
        self.assertEqual(status,200)
        self.assertIn(b'undo',body)

    def test_cross_site_origin_blocked(self):
        payload=json.dumps(load_config()).encode()
        status,_=self.request('/api/render',payload,origin='https://attacker.example')
        self.assertEqual(status,403)

    def test_host_rebinding_blocked(self):
        status,_=self.request('/api/config',host='attacker.example')
        self.assertEqual(status,403)

    def test_json_content_type_enforced(self):
        payload=json.dumps(load_config()).encode()
        status,_=self.request('/api/render',payload,content_type='text/plain')
        self.assertEqual(status,400)

    def test_export_uses_unsaved_config(self):
        conf=load_config()
        conf['sections']=[{'title':'Não salvo', 'rows':[{'label':'Projeto','value':'Valor temporário'}]}]
        status,body=self.request('/api/export',json.dumps({**conf,'variant':'dark'}).encode())
        self.assertEqual(status,200)
        self.assertIn('Valor temporário',body.decode())
        ET.fromstring(body)

    def test_photo_read_cannot_see_private_files(self):
        status,_=self.request('/api/photo-preview?path=../../etc/passwd')
        self.assertEqual(status,400)

    def test_invalid_image_does_not_change_files(self):
        status,_=self.request('/api/photo',b'not actually image',content_type='image/png')
        self.assertEqual(status,400)

    def test_reject_wrong_host_port(self):
        status,_=self.request('/api/config',host='127.0.0.1:1')
        self.assertEqual(status,403)

    def test_invalid_save_preserves_config(self):
        old=app.DEFAULT_CONFIG.read_bytes()
        conf=load_config()
        conf['profile']['photo']='assets/missing.png'
        status,_=self.request('/api/save',json.dumps(conf).encode())
        self.assertEqual(status,400)
        self.assertEqual(app.DEFAULT_CONFIG.read_bytes(),old)

    def test_export_portrait_uses_unsaved_photo_configuration(self):
        conf=load_config()
        conf['portrait']['columns']=62
        status, body=self.request('/api/export-portrait',json.dumps(conf).encode())
        self.assertEqual(status,200)
        root=ET.fromstring(body)
        self.assertTrue(root.tag.endswith('svg'))
        self.assertNotIn(b'<image ',body)
        self.assertIn(b'<tspan',body)

    def test_stats_route_mock(self):
        with patch('app.fetch_stats',return_value={'cached':{'public_repos':3},'updated_at':'demo'}):
            status,body=self.request('/api/stats',b'{"username":"demo"}')
        self.assertEqual(status,200)
        self.assertEqual(json.loads(body)['cached']['public_repos'],3)

    def test_real_photo_upload_returns_independent_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            pic=Image.new('RGB',(30,30),(150,80,90))
            buffer=io.BytesIO();pic.save(buffer,'PNG')
            status,body=self.request('/api/photo',buffer.getvalue(),content_type='image/png')
            self.assertEqual(status,200)
            filename=json.loads(body)['path']
            self.assertTrue(filename.startswith('assets/uploads/portrait-'))
            status,body=self.request('/api/photo-preview?path='+filename)
            self.assertEqual(status,200)
            Image.open(io.BytesIO(body)).verify()
            (app.ROOT/filename).unlink()


if __name__=='__main__':unittest.main()
