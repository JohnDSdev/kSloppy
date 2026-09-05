from krita import Krita
from .plugin import KSloppyExtension
Krita.instance().addExtension(KSloppyExtension(Krita.instance()))
