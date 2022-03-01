import sys
from pathlib import Path
srcdirectory = Path(__file__).absolute().parent
sys.path.insert(0, srcdirectory)

#print("Running __main__")

from mumerge import mumerge
mumerge.main()
