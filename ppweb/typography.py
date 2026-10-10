"""Optional transparent PNG display title from an explicitly approved local font.
This is typography rendering, NOT AI-original calligraphy; for unique hand lettering,
a separate approved image-design step is required.
"""
from pathlib import Path
from PIL import Image, ImageFont, ImageDraw


def render_title(text:str,font_file:Path,output:Path,ink=(35,35,30),max_width=1400):
    if not font_file.is_file() or font_file.suffix.lower() not in {'.ttf','.otf','.ttc'}:
        raise ValueError('A verified local TTF/OTF/TTC file is required')
    size=200
    while size>30:
        font=ImageFont.truetype(str(font_file),size)
        b=font.getbbox(text,stroke_width=0)
        if (b[2]-b[0]) < max_width-48:break
        size-=6
    width=min(max_width,max(160,b[2]-b[0]+48));height=max(90,b[3]-b[1]+48)
    img=Image.new('RGBA',(width,height),(0,0,0,0))
    d=ImageDraw.Draw(img)
    d.text((24-b[0],24-b[1]),text,font=font,fill=(*ink,255))
    output.parent.mkdir(parents=True,exist_ok=True)
    img.save(output,'PNG',optimize=True)
    return {'path':'assets/brand-title.png','width':width,'height':height,'kind':'typography-title'}
