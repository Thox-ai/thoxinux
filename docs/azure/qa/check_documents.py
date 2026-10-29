#!/usr/bin/env python3
"""Check local document references, PDF text bounds and rendered-page inventory."""
from pathlib import Path
from html.parser import HTMLParser
import json,xml.etree.ElementTree as ET
import fitz
from PIL import Image,ImageDraw

root=Path(__file__).resolve().parent.parent
page=root/'html/THOX_Ginux_Azure_Deployment_Guide.html'
class Parser(HTMLParser):
 def __init__(self):super().__init__();self.ids=set();self.refs=[]
 def handle_starttag(self,tag,attrs):
  values=dict(attrs)
  if 'id' in values:self.ids.add(values['id'])
  self.refs.extend(values[x] for x in ['href','src'] if x in values)
a=Parser();a.feed(page.read_text());bad=[]
for ref in a.refs:
 if ref.startswith('#'):
  if ref[1:] not in a.ids:bad.append(ref)
 elif not ref.startswith(('http:','https:')) and not (page.parent/ref).exists():bad.append(ref)
assert not bad,bad
ET.parse(root/'html/assets/azure-boundaries.svg')
doc=fitz.open(root/'THOX_Ginux_Azure_Deployment_Guide.pdf');tiles=[];bounds=[]
for i,p in enumerate(doc):
 assert len(p.get_text())>500,('Possible orphan/empty page',i+1)
 for block in p.get_text('dict')['blocks']:
  for line in block.get('lines',[]):
   x0,y0,x1,y1=line['bbox']
   if min(x0,y0)<0 or x1>p.rect.width+0.5 or y1>p.rect.height+0.5:bounds.append({'page':i+1,'bbox':line['bbox']})
 path=root/'qa'/f'page-{i+1}.png';p.get_pixmap(matrix=fitz.Matrix(1.2,1.2),alpha=False).save(path)
 image=Image.open(path).convert('RGB');image.thumbnail((318,450));tile=Image.new('RGB',(334,478),'#ddd');tile.paste(image,((334-image.width)//2,10));ImageDraw.Draw(tile).text((7,462),str(i+1),fill='black');tiles.append(tile)
assert not bounds,bounds
contact=Image.new('RGB',(1002,478*((len(tiles)+2)//3)),'white')
for i,image in enumerate(tiles):contact.paste(image,((i%3)*334,(i//3)*478))
contact.save(root/'qa/contact.png')
result={'pdf_pages':len(doc),'page_text_lengths':[len(p.get_text()) for p in doc],'pdf_text_bounds':'passed','html_ids':len(a.ids),'html_references_checked':len(a.refs),'bad_references':bad,'svg_xml':'passed','browser_layout':'not_run; static references and isolated controls only','technical_pdf_font':'DejaVu Sans Mono compatibility fallback; JetBrains Mono unavailable'}
(root/'qa/validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
