# %load_ext autoreload
# %autoreload 2
# import sys
# sys.path.append('..')

from .scrap import (download_proceedings,
                    read_proceedings,
                    regexes_in_proceedings,
                    regexes_to_matrix,
                    regex_in_proceedings,
                    regex_statistics,
                    subdict)
from .sources.tools import get_proceedings

__version__ = '0.0.1'
