from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os
import pickle

from scrap.scrap import (create_global_tempdir,
                         create_dir,
                         load_webpage,
                         print_progress,
                         soup_up)
from scrap.scrap import ROOT_TEMPDIR

def get_aaai_proceedings(year):
    # http://www.aaai.org/Library/AAAI/aaai-library.php
    meta_filename = '_metadata.pkl'
    proceedings_source = 'aaai'
    proceedings_name = year.replace(' ', '_').strip()
    proceedings_dir = os.path.join(ROOT_TEMPDIR, proceedings_source, proceedings_name)

    meta_file = os.path.join(proceedings_dir, meta_filename)
    if os.path.exists(meta_file):
        print('Pickle found: {}\nReading pickle'.format(meta_file))
        with open(meta_file, 'rb') as pf:
            aaai_data = pickle.load(pf)
    else:
        create_global_tempdir()
        create_dir(proceedings_dir)

        aaai_proceedings_url = 'http://www.aaai.org/Library/AAAI/aaai{}contents.php'.format(proceedings_name[2:4])
        webpage_text = load_webpage(aaai_proceedings_url)

        aaai_data = parse_aaai_proceedings(webpage_text, year)

        with open(meta_file, 'wb') as pf:
            pickle.dump(aaai_data, pf)

    return aaai_data

def get_new_urti_aaai(aaai_page):
    # Get url
    url = aaai_page.get('href')
    if url is not None:
        if url.endswith('.php'):
            url = None
        else:
            url = url.replace('/view/', '/viewPaper/')
            if not url.startswith('https') and url.startswith('http'):
                url = 'https{}'.format(url[4:])
    title = ' '.join(aaai_page.text.strip().split())
    return url, title

def parse_new_aaai(paper_url):
    paper_webpage = load_webpage(paper_url)
    paper_soup = soup_up(paper_webpage)


    # Track/ info
    track = paper_soup.find_all('div', {'id': 'breadcrumb'})[0].find_all('a')
    info = track[-2].contents[0].strip()

    # Title
    title = paper_soup.find_all('div', {'id': 'title'})
    title = title[0].contents[0].strip()

    # Authors
    authors = paper_soup.find_all('div', {'id': 'author'})
    authors = [a.strip() for a in authors[0].text.split(',')]

    # Abstract
    abstract = paper_soup.find_all('div', {'id': 'abstract'})
    abstract = abstract[0].find_all('div')[0].text.strip()

    # PDF url and file name
    pdf = paper_soup.find_all('div', {'id': 'paper'})
    pdf_url = None
    pdf_filename = None
    for p in pdf[0].find_all('a'):
        if 'pdf' in p.text.lower():
            pdf_url = p.get('href')
            break
    if pdf_url is not None:
        pdf_url = pdf_url.replace('/view/', '/download/')
        pdf_filename = '{}.pdf'.format('-'.join(pdf_url.split('/')[-2:]))

    return info, title, authors, pdf_url, pdf_filename

def get_old_urti_aaai(aaai_page):
    # Get url
    url = aaai_page.get('href')
    # Old style url has to end with `.php`
    if url is not None:
        url = os.path.normpath(os.path.join('/www.aaai.org/Library/AAAI/', url))
        if not url.endswith('.php') or not 'library' in url.lower():
            url = None
        else:
            url = 'http:/' + url
    title = ' '.join(aaai_page.text.strip().split())
    return url, title

def parse_old_aaai(paper_url):
    paper_webpage = load_webpage(paper_url)
    paper_soup = soup_up(paper_webpage)
    try:
        paper_soup = paper_soup.find_all('div', {'id': 'abstract'})[0]
    except IndexError:
        print('\nSkipping (unreadable web page): {}'.format(paper_url))
        return None, None, None, None, None

    title_and_url = paper_soup.find_all('h1')[0]
    title_and_url_ = title_and_url.find_all('a')
    if title_and_url_:
        title_and_url = title_and_url_[0]

        # Title
        title = title_and_url.text.strip()

        # PDF url and file name
        pdf_url = title_and_url.get('href')
        pdf_filename = None
        if pdf_url is not None:
            base_dir = os.path.dirname(paper_url)
            https_in = False
            if base_dir.startswith('https'):
                https_in = True
                base_dir = base_dir[7:]
            else:
                https_in = False
                base_dir = base_dir[6:]
            pdf_url = os.path.normpath(os.path.join(base_dir, pdf_url))
            if https_in:
                pdf_url = 'https:/' + pdf_url
            else:
                pdf_url = 'http:/' + pdf_url

            pdf_filename = os.path.basename(pdf_url)
    else:
        # Title
        title = title_and_url.text.strip()
        pdf_url = None
        pdf_filename = None

    paper_p = paper_soup.find_all('p')
    # Track/ info
    info = paper_p[2].contents[-1].encode('utf-8').decode('utf-8')

    # Authors
    authors = paper_p[0].text.strip()
    authors = [a.strip() for a in authors.split(',')]

    # Abstract
    abstract = paper_p[1].text.strip()

    return info, title, authors, pdf_url, pdf_filename

def parse_aaai_proceedings(aaai_proceedings, year):
    source = 'aaai'
    volume = year.strip()
    year_int = int(year)

    aaai_soup = soup_up(aaai_proceedings)
    aaai_content = aaai_soup.find_all('div', {'class': 'content'})[0]

    pdf_sup = None
    pdf_sup_filename = None
    zip_sup = None
    zip_sup_filename = None
    papers = []

    aaai_papers = aaai_content.find_all('a')
    progress_length = len(aaai_papers)
    print_progress(0, progress_length, prefix='Progress:', suffix='Complete', bar_length=50)
    for i, aaai_i in enumerate(aaai_papers):
        if year_int < 2010:
            # Use old proceedings format
            url, title = get_old_urti_aaai(aaai_i)
            if url is None:
                print_progress(i+1, progress_length, prefix='Progress:', suffix='Complete', bar_length=50)
                continue
            info, title, authors, pdf_url, pdf_filename = parse_old_aaai(url)
        else:
            # Use new proceedings format
            url, title = get_new_urti_aaai(aaai_i)
            if url is None:
                print_progress(i+1, progress_length, prefix='Progress:', suffix='Complete', bar_length=50)
                continue
            info, title, authors, pdf_url, pdf_filename = parse_new_aaai(url)
        if pdf_url is not None:
            papers.append(dict(title=title, authors=authors, info=info, url=url,
                               source=source, volume=volume,
                               pdf_url=pdf_url, pdf_filename=pdf_filename,
                               pdf_sup_url=pdf_sup, pdf_sup_filename=pdf_sup_filename,
                               zip_sup_url=zip_sup, zip_sup_filename=zip_sup_filename))
        else:
            print('\nSkipping (no pdf url): {}'.format(url))
        print_progress(i+1, progress_length, prefix='Progress:', suffix='Complete', bar_length=50)

    return papers

