"""Public importer network boundary tests; no external requests."""
import io
import socket
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from fastapi import HTTPException
from PIL import Image
from backend import product_import as importer
from backend.store import Store


class ProductImportTests(unittest.TestCase):
    def destination(self,url,addresses=('93.184.216.34',)):
        records=[(socket.AF_INET,socket.SOCK_STREAM,6,'',(address,443)) for address in addresses]
        with patch.object(socket,'getaddrinfo',return_value=records):
            return importer._destination(url,time.monotonic()+10)

    def test_public_url_boundary_rejects_private_aliases_and_mixed_dns(self):
        for url in ['file:///etc/passwd','http://user:pass@example.com','http://localhost','http://x.local','http://example.com:8188','http://example.com\\@localhost','http://example.com/\nheader']:
            with self.subTest(url=url),self.assertRaises(ValueError):self.destination(url)
        for addresses in [('127.0.0.1',),('169.254.169.254',),('10.2.3.4',),('93.184.216.34','192.168.1.2'),('::ffff:127.0.0.1',),('64:ff9b::7f00:1',)]:
            with self.subTest(addresses=addresses),self.assertRaises(ValueError):self.destination('https://public.example',addresses)
        self.assertEqual(self.destination('https://example.com/a b#fragment')[0],'https://example.com/a%20b')

    def test_socket_is_pinned_to_validated_ip_with_original_tls_hostname(self):
        raw=MagicMock();context=MagicMock();connection=importer._PinnedConnection('shop.example',443,'93.184.216.34',True,3)
        with patch.object(socket,'create_connection',return_value=raw) as connect,patch('ssl.create_default_context',return_value=context):
            connection.connect()
        connect.assert_called_once_with(('93.184.216.34',443),3)
        context.wrap_socket.assert_called_once_with(raw,server_hostname='shop.example',do_handshake_on_connect=False)
        context.wrap_socket.return_value.do_handshake.assert_called_once()

    def response(self,status=200,headers=None,body=b''):
        response=MagicMock();response.status=status;headers=headers or {}
        response.getheader.side_effect=lambda name,default=None:headers.get(name,default)
        buffer=io.BytesIO(body);response.read1.side_effect=buffer.read
        return response

    def test_redirect_target_is_revalidated_before_connecting(self):
        connection=MagicMock();connection.getresponse.return_value=self.response(302,{'Location':'http://127.0.0.1/secret'})
        def lookup(host,*args,**kwargs):
            address='127.0.0.1' if host=='127.0.0.1' else '93.184.216.34'
            return [(socket.AF_INET,socket.SOCK_STREAM,6,'',(address,80))]
        with patch.object(socket,'getaddrinfo',side_effect=lookup),patch.object(importer,'_PinnedConnection',return_value=connection) as factory:
            with self.assertRaisesRegex(ValueError,'Private'):
                importer._fetch('https://shop.example',100,time.monotonic()+5,'text/html')
        self.assertEqual(factory.call_count,1);connection.abort.assert_called()

    def test_announced_streamed_and_compressed_response_limits(self):
        for response in [self.response(headers={'Content-Length':'33'}),self.response(body=b'x'*33),self.response(headers={'Content-Encoding':'gzip'})]:
            connection=MagicMock();connection.getresponse.return_value=response
            with patch.object(importer,'_destination',return_value=('http://example.com/','example.com',80,'93.184.216.34',False)),patch.object(importer,'_PinnedConnection',return_value=connection):
                with self.assertRaises(ValueError):importer._fetch('http://example.com',32,time.monotonic()+5,'text/html')
            response.close.assert_called_once();connection.abort.assert_called_once()

    def test_metadata_import_preserves_actual_image_and_deduplicates(self):
        image=io.BytesIO();Image.new('RGB',(64,64),'red').save(image,'PNG');pixels=image.getvalue()
        page=b'<title>Fallback</title><meta property="og:image" content="/wrong.png"><script type="application/ld+json">{"@type":"Product","name":"Actual lamp","description":"<b>Metal</b> lamp","image":"/product.png"}</script>'
        calls=[]
        def fetch(url,*args):
            calls.append(url)
            return (page,url,'text/html') if url.endswith('/product') else (pixels,url,'image/png')
        with tempfile.TemporaryDirectory(prefix='openframe-product-test-') as folder:
            store=Store(Path(folder))
            with patch.object(importer,'_fetch',side_effect=fetch):
                result=importer.import_product(store,'https://example.com/product')
                again=importer.import_product(store,'https://example.com/product')
            self.assertEqual(result['title'],'Actual lamp');self.assertEqual(result['description'],'Metal lamp')
            self.assertEqual(result['image_url'],'https://example.com/product.png')
            self.assertEqual(result['asset']['id'],again['asset']['id']);self.assertEqual(store.count('assets'),1)
            self.assertNotIn('https://example.com/wrong.png',calls)
            self.assertEqual(Path(store.get('assets',result['asset']['id'])['path']).read_bytes(),pixels)
            self.assertEqual(list((Path(folder)/'uploads').iterdir()),[])

    def test_unreadable_candidates_are_bounded_and_never_registered(self):
        page=('<script type="application/ld+json">{"@type":"Product","image":['+','.join('"/image%d.png"'%i for i in range(10))+']}</script>').encode()
        calls=[]
        def fetch(url,*args):
            calls.append(url);return (page,url,'text/html') if len(calls)==1 else (b'not an image',url,'image/png')
        with tempfile.TemporaryDirectory(prefix='openframe-product-test-') as folder:
            store=Store(Path(folder))
            with patch.object(importer,'_fetch',side_effect=fetch),self.assertRaises(HTTPException) as failure:
                importer.import_product(store,'https://example.com/product')
            self.assertEqual(failure.exception.status_code,422);self.assertEqual(len(calls),4);self.assertEqual(store.count('assets'),0)
            self.assertIn('manually',failure.exception.detail)
