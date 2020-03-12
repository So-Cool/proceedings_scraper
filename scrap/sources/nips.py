from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os
import pickle
import re

from scrap.scrap import (create_global_tempdir,
                         create_dir,
                         extract_html_class,
                         extract_html_tag,
                         load_webpage,
                         print_progress)
from scrap.scrap import ROOT_TEMPDIR

def get_nips_url(volume_or_year):
    nips_proceedings_repository = 'https://papers.nips.cc'
    webpage_text = load_webpage(nips_proceedings_repository)
    volumes_list = extract_html_tag(webpage_text, 'a')

    nips_pattern = re.compile(r'(?:Advances in )?Neural Information Processing Systems (?:(?P<volume>\d{1,2}) )?\(NIPS (?P<year>\d{4})\)', re.IGNORECASE)
    nips_by_year = {}
    nips_by_volume = {}
    for v in volumes_list:
        extract = nips_pattern.search(v.contents[0])
        if extract:
            year = extract.group('year')
            year = year.strip() if year is not None else year
            volume = extract.group('volume')
            volume = volume.strip() if volume is not None else volume
            url = nips_proceedings_repository + v.get('href').strip()
            if year is not None:
                nips_by_year[year] = (url, volume, year)
            if volume is not None:
                nips_by_volume[volume] = (url, volume, year)

    book_url = nips_by_year.get(volume_or_year)
    if book_url is None:
        book_url = nips_by_volume.get(volume_or_year)
        if book_url is None:
            raise Exception('Unknown NIPS volume or year {}'.format(volume_or_year))
        else:
            return book_url
    else:
        return book_url

def get_nips_paper(url):
    nips_proceedings_repository = 'https://papers.nips.cc'
    pdf_url, pdf_filename, zip_sup_url, zip_sup_filename = None, None, None, None
    paper_page = load_webpage(url)
    paper_page_a = extract_html_tag(paper_page, 'a')
    for a in paper_page_a:
        a_contents = a.contents[0].strip().lower()
        if a_contents == '[pdf]':
            pdf_url = nips_proceedings_repository + a.get('href').strip()
            pdf_filename = os.path.basename(pdf_url)
        elif a_contents == '[supplemental]':
            zip_sup_url = nips_proceedings_repository + a.get('href').strip()
            zip_sup_filename = os.path.basename(zip_sup_url)
    return pdf_url, pdf_filename, zip_sup_url, zip_sup_filename

def get_nips_proceedings(volume_or_year):
    nips_book_url, volume, year = get_nips_url(volume_or_year)

    meta_filename = '_metadata.pkl'
    proceedings_source = 'nips'
    proceedings_name = year.replace(' ', '_').strip()
    proceedings_dir = os.path.join(ROOT_TEMPDIR, proceedings_source, proceedings_name)

    meta_file = os.path.join(proceedings_dir, meta_filename)
    if os.path.exists(meta_file):
        print('Pickle found: {}\nReading pickle'.format(meta_file))
        with open(meta_file, 'rb') as pf:
            nips_data = pickle.load(pf)
    else:
        create_global_tempdir()
        create_dir(proceedings_dir)

        webpage_text = load_webpage(nips_book_url)
        nips_data = parse_nips_proceedings(webpage_text, year)

        with open(meta_file, 'wb') as pf:
            pickle.dump(nips_data, pf)

    return nips_data

def parse_nips_proceedings(nips_proceedings, volume_or_year):
    nips_proceedings_repository = 'https://papers.nips.cc'

    source = 'nips'
    volume = volume_or_year
    info = ''
    pdf_sup_filename = ''
    pdf_sup_url = ''

    papers = []
    lis = extract_html_class(nips_proceedings, 'main wrapper clearfix')[0].find_all('li')
    for li in lis:
        paper = {'source':source, 'volume':volume, 'info':info, 'pdf_sup_filename':pdf_sup_filename, 'pdf_sup_url':pdf_sup_url}
        authors = []
        title = None
        url = None
        for a in li.find_all('a'):
            a_class = a.get('class')
            a_class = '' if a_class is None else a_class[0].strip()
            if a_class == 'author':
                authors.append(a.contents[0].strip())
            elif title is None and url is None:  # paper
                title = ''.join([str(x).strip() for x in a.contents])
                url = nips_proceedings_repository + a.get('href').strip()
            else:
                raise Exception('Double title and author in the NIPS proceedings.')
        paper['title'] = title
        paper['authors'] = authors
        paper['url'] = url
        papers.append(paper)

    progress_length = len(papers)
    print_progress(0, progress_length, prefix='Progress:', suffix='Complete', bar_length=50)
    for i, paper in enumerate(papers):
        paper_url = paper.get('url', '')
        pdf_url, pdf_filename, zip_sup_url, zip_sup_filename = get_nips_paper(paper_url)
        paper['pdf_url'] = pdf_url
        paper['pdf_filename'] = pdf_filename
        paper['zip_sup_url'] = zip_sup_url
        paper['zip_sup_filename'] = zip_sup_filename
        print_progress(i+1, progress_length, prefix='Progress:', suffix='Complete', bar_length=50)

    return papers

