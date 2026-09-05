"""Install plugin in an isolated Krita profile and run a real GUI smoke test."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
root=Path(__file__).resolve().parents[1]
output=root/'test-output';output.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix='ksloppy-krita-') as temp:
    base=Path(temp);data=base/'data';config=base/'config';config.mkdir()
    plugins=data/'krita'/'pykrita';plugins.mkdir(parents=True)
    shutil.copytree(root/'ksloppy',plugins/'ksloppy')
    shutil.copy(root/'ksloppy.desktop',plugins)
    runner=plugins/'ksloppy_test';runner.mkdir()
    shutil.copy(root/'tests'/'krita_smoke.py',runner/'smoke.py')
    (runner/'__init__.py').write_text('from PyQt5.QtCore import QTimer\nfrom .smoke import run\nQTimer.singleShot(2500, run)\n')
    (plugins/'ksloppy_test.desktop').write_text('[Desktop Entry]\nType=Service\nServiceTypes=Krita/PythonPlugin\nX-KDE-Library=ksloppy_test\nX-Python-2-Compatible=false\nName=kSloppy Test\n')
    (config/'kritarc').write_text('[python]\nenable_ksloppy=true\nenable_ksloppy_test=true\n\n[General]\nOpenGLRenderer=none\n')
    env=dict(os.environ,XDG_DATA_HOME=str(data),XDG_CONFIG_HOME=str(config),KSLOPPY_TEST_OUTPUT=str(output))
    with (output/'krita.log').open('w') as log:
        subprocess.run(['xvfb-run','-a','krita','--nosplash'],env=env,stdout=log,stderr=subprocess.STDOUT,timeout=120,check=True)
    result=json.loads((output/'result.json').read_text())
    print(json.dumps(result,indent=2))
    if not result['ok']:raise SystemExit(1)
