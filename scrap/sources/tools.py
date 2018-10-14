from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import scrap.sources.aaai as aaai
import scrap.sources.mlr as mlr
import scrap.sources.nips as nips

def get_proceedings(source, volume_year):
    source = source.lower().strip()
    volume_year = volume_year.lower().strip()

    if 'aaai' in source:
        return aaai.get_aaai_proceedings(volume_year)
    elif 'icml' in source or 'mlr' in source:
        return mlr.get_mlr_proceedings(volume_year)
    elif 'nips' in source:
        return nips.get_nips_proceedings(volume_year)
    else:
        print('Unknown proceedings source: {}. The scraper only supports: NIPS'
                ' , ICML/MLR and AAAI at the moment.')
        return None

