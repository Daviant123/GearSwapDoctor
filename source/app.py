"""GearSwap Doctor - starts the application (gsd_app.py). Kept so "GearSwap Doctor.bat" and old shortcuts still work."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gsd_app import main  # noqa: E402

if __name__ == '__main__':
    main()
