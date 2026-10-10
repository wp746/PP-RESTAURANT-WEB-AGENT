import io
import json
import zipfile
from pathlib import Path
from PIL import Image
import pytest

from ppweb.io import extract_zip,InputError,collect_text,locate_merchant_manifest,extract_basic_facts,optimize_images
from ppweb.publish import bootstrap_existing, merge_store,PublishError
from ppweb.quality import validate_site,QualityError
from ppweb.cli import demo_design,build_document


def test_zip_path_traversal_rejected(tmp_path):
    z=tmp_path/'x.zip'
    with zipfile.ZipFile(z,'w') as f:f.writestr('../evil.txt','secret')
    with pytest.raises(InputError):extract_zip(z,tmp_path/'out')


def test_zip_uncompressed_limit(tmp_path):
    z=tmp_path/'x.zip'
    with zipfile.ZipFile(z,'w') as f:f.writestr('large.txt','a'*1024*1024)
    with pytest.raises(InputError):extract_zip(z,tmp_path/'out',max_mb=0.1)


def test_missing_manifest_cannot_forge_approval(tmp_path):
    d=tmp_path/'d';d.mkdir();(d/'信息.txt').write_text('店名：测试肥肠鸡\n品类：川渝菜\n电话：1234',encoding='utf-8')
    docs=collect_text([d/'信息.txt'],d)
    facts,evidence=extract_basic_facts(docs,{})
    assert facts['name']=='测试肥肠鸡'
    assert 'approved_for_publication' not in facts
    assert evidence['name']=='信息.txt'


def test_preserve_existing_merchant_when_adding(tmp_path):
    root=tmp_path/'sites';root.mkdir()
    (root/'index.html').write_text('<h1>directory</h1>')
    old=root/'old-shop';old.mkdir();(old/'index.html').write_text('OLD SITE 123')
    shop=tmp_path/'new';shop.mkdir();(shop/'index.html').write_text('NEW SITE')
    (shop/'public-store.json').write_text('{"name":"新店","category":"餐饮"}')
    merge_store(root,shop,'new-shop',replace=False)
    assert (root/'old-shop/index.html').read_text()=='OLD SITE 123'
    assert (root/'new-shop/index.html').read_text()=='NEW SITE'
    assert '/old-shop/' in (root/'index.html').read_text()
    assert '/new-shop/' in (root/'index.html').read_text()


def test_guard_missing_site_state(tmp_path):
    shop=tmp_path/'shop';shop.mkdir();(shop/'index.html').write_text('ok')
    with pytest.raises(PublishError):merge_store(tmp_path/'empty',shop,'a-shop',False)


def test_demo_assembles_and_audits(tmp_path):
    img=Image.new('RGB',(300,300),(130,32,24))
    dir=tmp_path/'assets';dir.mkdir();img.save(dir/'image-001.webp')
    parts=demo_design({'name':'测试店','category':'川渝菜'},[{'path':'assets/image-001.webp'}])
    doc=build_document(parts,'测试店')
    assert 'data-pp-brand-site' in doc
    assert '<style>' in doc and '<script>' in doc
    assert validate_site(parts['html'],parts['css'],parts['js'],tmp_path)['static']=='pass'


def test_reject_external_and_dead_links(tmp_path):
    parts=demo_design({'name':'测试店','category':'餐饮'},[])
    parts['html']=parts['html'].replace('</body>','<a href="#">dead</a><img src="https://tracker.io/x.jpg"></body>')
    with pytest.raises(QualityError):validate_site(parts['html'],parts['css'],parts['js'],tmp_path)


def test_existing_dir_replace_requires_explicit(tmp_path):
    r=tmp_path/'sites';r.mkdir();(r/'index.html').write_text('home')
    s=r/'shop';s.mkdir();(s/'index.html').write_text('old')
    incoming=tmp_path/'new';incoming.mkdir();(incoming/'index.html').write_text('new')
    with pytest.raises(PublishError):merge_store(r,incoming,'shop',False)
    assert (s/'index.html').read_text()=='old'
