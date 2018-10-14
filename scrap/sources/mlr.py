from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os
import pickle

from scrap.scrap import (create_global_tempdir,
                         create_dir,
                         extract_html_class,
                         extract_html_tag,
                         load_webpage)
from scrap.scrap import ROOT_TEMPDIR

def parse_mlr_proceedings(mlr_proceedings, volume):
    def print_error(url_type, title):
        print('Error processing {} url for: "{}"'.format(url_type, title))

    source = 'mlr'
    class_name = 'paper'
    webpage_class = extract_html_class(mlr_proceedings, class_name)

    # Pull text from all instances of <a> tag within BodyText div
    papers = []
    for webpage_class_text in webpage_class:
        title = webpage_class_text.find(class_='title').contents[0].strip()

        authors = webpage_class_text.find(class_='authors').contents[0].\
                replace('\n', '').split(',')
        authors = [author.strip() for author in authors]

        info = webpage_class_text.find(class_='info').contents[0].strip()

        links = webpage_class_text.find(class_='links').find_all('a')
        url = None
        pdf_main = None
        pdf_main_filename = None
        pdf_sup = None
        pdf_sup_filename = None
        zip_sup = None
        zip_sup_filename = None
        for link in links:
            link_contents = link.contents[0].lower()
            link_href = link.get('href')
            if 'abs' in link_contents:
                if url is None:
                    url = link_href
                else:
                    print_error('abs', title)
            elif 'download pdf' in link_contents:
                if pdf_main is None:
                    pdf_main = link_href
                    pdf_main_filename = os.path.basename(link_href)
                else:
                    print_error('pdf', title)
            elif 'supplementary pdf' in link_contents:
                if pdf_sup is None:
                    pdf_sup = link_href
                    pdf_sup_filename = os.path.basename(link_href)
                else:
                    print_error('pdf_sup', title)
            elif 'supplementary zip' in link_contents:
                if zip_sup is None:
                    zip_sup = link_href
                    zip_sup_filename = os.path.basename(link_href)
                else:
                    print_error('zip_sup', title)
            else:
                print('Unknown type of link {} for {}'.format(link_contents, title))

        papers.append(dict(title=title, authors=authors, info=info, url=url,
                           source=source, volume=volume,
                           pdf_url=pdf_main, pdf_filename=pdf_main_filename,
                           pdf_sup_url=pdf_sup, pdf_sup_filename=pdf_sup_filename,
                           zip_sup_url=zip_sup, zip_sup_filename=zip_sup_filename))

    return papers

def get_mlr_proceedings(volume):
    meta_filename = '_metadata.pkl'
    proceedings_source = 'mlr'
    proceedings_name = volume.replace(' ', '_').strip()
    proceedings_dir = os.path.join(ROOT_TEMPDIR, proceedings_source, proceedings_name)

    meta_file = os.path.join(proceedings_dir, meta_filename)
    if os.path.exists(meta_file):
        print('Pickle found: {}\nReading pickle'.format(meta_file))
        with open(meta_file, 'rb') as pf:
            mlrp_data = pickle.load(pf)
    else:
        create_global_tempdir()
        create_dir(proceedings_dir)

        mlr_proceedings_url = 'http://proceedings.mlr.press/{}/'.format(volume)
        webpage_text = load_webpage(mlr_proceedings_url)
        mlrp_data = parse_mlr_proceedings(webpage_text, volume)

        with open(meta_file, 'wb') as pf:
            pickle.dump(mlrp_data, pf)

    return mlrp_data

