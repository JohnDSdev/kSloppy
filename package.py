"""Build an importable Krita Python-plugin ZIP. Run from any directory."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
root=Path(__file__).resolve().parent
output=root/'dist'/'kSloppy.zip'
output.parent.mkdir(exist_ok=True)
with ZipFile(output,'w',ZIP_DEFLATED) as archive:
    for path in sorted((root/'ksloppy').rglob('*'))+[root/'ksloppy.desktop']:
        if path.is_file() and '__pycache__' not in path.parts:
            archive.write(path,path.relative_to(root))
print(output)
