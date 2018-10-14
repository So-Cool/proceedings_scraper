# %load_ext autoreload
# %autoreload 2

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import itertools
import os
import pandas as pd
import pickle
import PyPDF2
import re
import requests
import sys
import bs4

ROOT_TEMPDIR = os.path.expanduser('~/scraper_temp_pdfs/')
FIX_PYPDF2 = True

def subdict(dictionary, key_subset):
    subdict = {}
    for key in key_subset:
        if key in dictionary:
            subdict[key] = dictionary.get(key)
    return subdict

# Print iterations progress
# https://stackoverflow.com/questions/3173320/text-progress-bar-in-the-console
def printProgressBar (iteration, total, prefix='', suffix='', decimals=1, bar_length=100, fill='█'):
    """
    Call in a loop to create terminal progress bar
    @params:
        iteration   - Required  : current iteration (Int)
        total       - Required  : total iterations (Int)
        prefix      - Optional  : prefix string (Str)
        suffix      - Optional  : suffix string (Str)
        decimals    - Optional  : positive number of decimals in percent complete (Int)
        bar_length      - Optional  : character length of bar (Int)
        fill        - Optional  : bar fill character (Str)
    """
    percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
    filledLength = int(bar_length * iteration // total)
    bar = fill * filledLength + '-' * (bar_length - filledLength)
    print('\r%s |%s| %s%% %s' % (prefix, bar, percent, suffix), end = '\r')
    # Print New Line on Complete
    if iteration == total:
        print()
# Print iterations progress
# https://gist.github.com/aubricus/f91fb55dc6ba5557fbab06119420dd6a
def print_progress(iteration, total, prefix='', suffix='', decimals=1, bar_length=100):
    """
    Call in a loop to create terminal progress bar

    @params:
        iteration   - Required  : current iteration (Int)
        total       - Required  : total iterations (Int)
        prefix      - Optional  : prefix string (Str)
        suffix      - Optional  : suffix string (Str)
        decimals    - Optional  : positive number of decimals in percent complete (Int)
        bar_length  - Optional  : character length of bar (Int)
    """
    str_format = "{0:." + str(decimals) + "f}"
    percents = str_format.format(100 * (iteration / float(total)))
    filled_length = int(round(bar_length * iteration / float(total)))
    bar = '█' * filled_length + '-' * (bar_length - filled_length)

    sys.stdout.write('\r%s |%s| %s%s %s' % (prefix, bar, percents, '%', suffix)),

    if iteration == total:
        sys.stdout.write('\n')
    sys.stdout.flush()

from PyPDF2.utils import b_, u_
from PyPDF2.pdf import ContentStream, TextStringObject, FloatObject, NumberObject
if FIX_PYPDF2:
    class PageObject(PyPDF2.pdf.PageObject):
        # avoiding missing spaces between words needs fix to site-packages/PyPDF2/pdf.py
        # from https://github.com/mstamy2/PyPDF2/commit/08699cbf0bfd13a60722965105562f52577004f5 and then I experimentally
        # set constant in lines 2632-2633 from -600 to -100, which seems to make extractText() work okay on these PDFs
        # but you then have to clean up all the whitespace to make the result vaguely human readable (if that's required)
        def extractText(self, skip_intertwined_text=True):
            """
            Locate all text drawing commands, in the order they are provided in the
            content stream, and extract the text.  This works well for some PDF
            files, but poorly for others, depending on the generator used.  This will
            be refined in the future.  Do not rely on the order of text coming out of
            this function, as it will change if this function is made more
            sophisticated.

            :return: a unicode string object.
            """
            text = u_("")
            content = self["/Contents"].getObject()
            if not isinstance(content, ContentStream):
                content = ContentStream(content, self.pdf)
            # Note: we check all strings are TextStringObjects.  ByteStringObjects
            # are strings where the byte->string encoding was unknown, so adding
            # them to the text here would be gibberish.
            #
            indent = 0
            previous_width = 0
            skip_next = False
            for operands, operator in content.operations:
                if not operands:  # Empty operands list contributes no text
                    operands = [""]
                if operator == b_("Tj"):
                    _text = operands[0]
                    if isinstance(_text, TextStringObject):
                        text += _text
                elif operator == b_("T*"):
                    text += "\n"
                elif operator == b_("'"):
                    text += "\n"
                    _text = operands[0]
                    if isinstance(_text, TextStringObject):
                        text += operands[0]
                elif operator == b_('"'):
                    _text = operands[2]
                    if isinstance(_text, TextStringObject):
                        text += "\n"
                        text += _text
                elif operator == b_("TJ"):
                    if skip_intertwined_text and skip_next:
                        skip_next = False
                    else:
                        for i in operands[0]:
                            if isinstance(i, TextStringObject):
                                text += i
                                previous_width += len(i)
                            elif isinstance(i, FloatObject) or isinstance(i, NumberObject):
                                if text and (not text[-1] in " \n"):
                                    text += " " * int(i / -100)
                                    previous_width += int(i / -100)
                elif operator == b_("Td"):
                    indent = indent + operands[0]
                    if operands[1] == 0:
                        if int(operands[0] / 20) >= previous_width:
                            text += " " * (int(operands[0] / 20) - previous_width)
                        else:
                            skip_next = True
                            # If skip_intertwined_text is false, this will result in no space between the two 'lines'
                    else:
                        previous_width = 0
                        text += "\n" * max(0, int(operands[1] / -50)) + " " * max(0, int(indent / 20))
                elif operator == b_("Tm"):
                    indent = operands[4]
                    text += " " * max(0, int(indent / 20))
                elif operator == b_("TD") or operator == b_("Tm"):
                    if text and (not text[-1] in " \n"):
                        text += " "
            return text
    # PyPDF2.pdf.PageObject.extractText = _extractText
    PyPDF2.pdf.PageObject = PageObject

def create_dir(new_dir):
   if not os.path.exists(new_dir):
        os.makedirs(new_dir)

def create_global_tempdir(root_tempdir=ROOT_TEMPDIR):
    create_dir(root_tempdir)

# def create_specific_tempdir(tempdir):
    # tempdir_full_path = os.path.join(ROOT_TEMPDIR, tempdir)
    # create_dir(tempdir_full_path)

# Collect and parse first page
def load_webpage(url):
    page = requests.get(url)
    page_contents = page.text
    page.close()
    return page_contents

def extract_html_class(webpage, class_name):
    soup = bs4.BeautifulSoup(webpage, 'html.parser')
    papers_html = soup.find_all(class_=class_name)  # Extract tags with given class
    return papers_html

def extract_html_tag(webpage, tag_name):
    soup = bs4.BeautifulSoup(webpage, 'html.parser')
    papers_html = soup.find_all(tag_name)  # Extract tags with given class
    return papers_html

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
    paper_soup = bs4.BeautifulSoup(paper_webpage, 'html.parser')


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
    paper_soup = bs4.BeautifulSoup(paper_webpage, 'html.parser')
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

    aaai_soup = bs4.BeautifulSoup(aaai_proceedings, 'html.parser')
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
                title = a.contents[0].strip()
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

# TODO: parallelise the download
def download_proceedings(proceedings, download=['pdf', 'pdf_sup']):
    create_global_tempdir()
    proceedings_source = proceedings[0].get('source').replace(' ', '_')
    proceedings_name = proceedings[0].get('volume').replace(' ', '_')
    proceedings_dir = os.path.join(ROOT_TEMPDIR, proceedings_source, proceedings_name)
    create_dir(proceedings_dir)

    progress_length = len(proceedings)
    print_progress(0, progress_length, prefix='Progress:', suffix='Complete', bar_length=50)
    for progress, paper in enumerate(proceedings):
        for d in download:
            url = paper.get(d+'_url', None)
            if url is not None:
                target_filename = paper.get(d+'_filename')
                target_file = os.path.join(proceedings_dir, target_filename)

                # If the paper is already downloaded, skip it
                if not os.path.exists(target_file):
                    req = requests.get(url, allow_redirects=True)
                    req_content = req.content
                    req.close()

                    with open(target_file, 'wb') as f:
                        f.write(req_content)
        print_progress(progress+1, progress_length, prefix='Progress:', suffix='Complete', bar_length=50)

def pdf_to_string(path_to_pdf):
    contents_list = ['']
    contents_string = ''
    with open(path_to_pdf, 'rb') as pdf:
        pdfReader = PyPDF2.PdfFileReader(pdf)
        for page_number in range(pdfReader.numPages):
            page_obj = pdfReader.getPage(page_number)
            page_txt = page_obj.extractText()

            # Miquel's
            for word in page_txt:
                if word == contents_list[-1] and word == ' ':
                    pass
                else:
                    contents_list.append(word)
            # Simon's
            txt = re.sub(r'\-\s+', '', page_txt)
            txt = re.sub(r'\s+\-\s*', '-', txt)
            txt = re.sub(r'Œ', '-', txt)
            txt = re.sub(r'\s+', ' ', txt)
            contents_string += txt + ' '
    contents_list = ''.join(contents_list)
    return contents_list, contents_string

# TODO: parallelise the processing
def read_proceedings(proceedings, read=['pdf', 'pdf_sup'], save_df=True):
    proceedings_source = proceedings[0].get('source').replace(' ', '_')
    proceedings_name = proceedings[0].get('volume').replace(' ', '_')
    proceedings_dir = os.path.join(ROOT_TEMPDIR, proceedings_source, proceedings_name)

    df_pickle_path = os.path.join(proceedings_dir, '_proceedings.pkl')

    if os.path.exists(df_pickle_path):
        print('Pickle found: {}\nReading pickle'.format(df_pickle_path))
        dataset_df = pd.read_pickle(df_pickle_path)
    else:
        progress_length = len(proceedings)
        dataset = []
        print_progress(0, progress_length, prefix='Progress:', suffix='Complete', bar_length=50)
        for i, paper in enumerate(proceedings):
            dataset.append(paper.copy())
            for r in read:
                filename = paper.get(r+'_filename', None)
                if filename is None or filename == '':
                    cl, cs = '', ''
                else:
                    file_path = os.path.join(proceedings_dir, filename)
                    try:
                        cl, cs = pdf_to_string(file_path)
                    except PyPDF2.utils.PdfReadError as exception:
                        print('\nError processing `{}`. Skipping this file'.format(file_path))
                        print(exception)
                        cl, cs = '', ''

                dataset[-1][r+'_contents'] = cs
            print_progress(i+1, progress_length, prefix='Progress:', suffix='Complete', bar_length=50)

        dataset_df = pd.DataFrame(dataset)

        if save_df:
            print('Saving the data frame to pickle: {}'.format(df_pickle_path))
            dataset_df.to_pickle(df_pickle_path)
            # dataset_df.to_csv(os.path.join(proceedings_dir,'_proceedings.csv'), header=True, index=False)

    return dataset_df

def compile_regex(regex, ignorecase=True):
    if ignorecase:
        return re.compile(regex, re.IGNORECASE)
    else:
        return re.compile(regex)

def regex_in_proceedings(regex, proceedings_df, columns=['pdf', 'pdf_sup'], ignorecase=True):
    pattern = compile_regex(regex, ignorecase)
    f = lambda x: len(pattern.findall(x))

    count_df = {}
    for c in columns:
        count_df[c+'_regex'] = proceedings_df[c+'_contents'].apply(f)
    count_df = pd.DataFrame(count_df)
    count_df["total_regex"] = count_df[[c+'_regex' for c in columns]].sum(axis=1)

    return count_df

def regex_statistics(regex_df, columns=['pdf', 'pdf_sup']):
    columns_t = columns + ['total']

    regex_df_total = regex_df.shape[0]
    print_string = 'There are {} papers in this collection\n'.format(regex_df_total)
    for c in columns_t:
        c_name = '{}_regex'.format(c)
        c_df = regex_df[c_name]
        c_df_count = c_df[c_df > 0].shape[0]
        c_df_percent = 100*c_df_count/regex_df_total

        print_string += '    {} count is {} ({:.2f}%)\n'.format(c_name,
                                                                c_df_count,
                                                                c_df_percent)
    print(print_string)

def regexes_in_proceedings(regex_dict, proceedings_df, columns=['pdf', 'pdf_sup'], ignorecase=True):
    patterns = {regex_id:compile_regex(regex_dict[regex_id], ignorecase) for regex_id in regex_dict}

    count_df = {}
    # per column per regex
    for c in columns:
        for pattern_id in patterns:
            c_full = c+'_regex_{}'.format(pattern_id)
            count_df[c_full] = proceedings_df[c+'_contents'].apply(lambda x: len(patterns[pattern_id].findall(x)))

    count_df = pd.DataFrame(count_df)

    # total for a pdf
    for pattern_id in patterns:
        pattern_columns = [c+'_regex_{}'.format(pattern_id) for c in columns]
        count_df['total_regex_{}'.format(pattern_id)] = count_df[pattern_columns].sum(axis=1)

    return count_df

# TODO: does not contain
# You can get the matrix for the following entries: pdf, pdf_sup, total
# The default is: total
def regexes_to_matrix(regexes_counts, regexes_in=[], regexes_out=[], column_type='total'):
    if regexes_out: raise Exception('Not implemented.')  # TODO

    print('There are {} papers in this collection'.format(regexes_counts.shape[0]))

    lambda_in = lambda x: 1 if x>0 else 0
    lambda_out = lambda x: 1 if x==0 else 0
    lambda_both = lambda x: 1 if x>1 else 0

    if regexes_in:
        columns_in = ['{}_regex_{}'.format(column_type, regex) for regex in regexes_in]
    else:
        pattern = '{}_regex_'.format(column_type)
        columns_in = [i for i in regexes_counts.columns if i.startswith(pattern)]
    columns_out = ['{}_regex_{}'.format(column_type, regex) for regex in regexes_out]

    all_apply = [regexes_counts[i].apply(lambda_in) for i in columns_in]
    all_apply = pd.DataFrame(all_apply).T
    all_apply = all_apply.sum(axis=1)
    all_apply = all_apply.apply(lambda x: 1 if x>=len(columns_in) else 0).sum()
    print('All regexes apply to {} papers.'.format(all_apply))

    matrix = []
    matrix_list = list(itertools.combinations(columns_in, 1)) + list(itertools.combinations(columns_in, 2))
    for ml in matrix_list:
        if len(ml) == 1:
            x = y = ml[0]
            value = regexes_counts[x].apply(lambda_in).sum()
        elif len(ml) == 2:
            x, y = ml[0], ml[1]
            df_in_one = regexes_counts[x].apply(lambda_in)
            df_in_two = regexes_counts[y].apply(lambda_in)
            value = (df_in_one+df_in_two).apply(lambda_both).sum()
        else:
            raise Exception('The matrix can only contain pairs.')

        matrix.append((x, y, value))

    df = {}
    for x, y, v in matrix:
        if x in df:
            if y not in df[x]:
                df[x][y] = v
            else:
                if df[x][y] != v: raise Exception('Value mismatch')
        else:
            df[x] = {y:v}

        if y in df:
            if x not in df[y]:
                df [y][x] = v
            else:
                if df[y][x] != v: raise Exception('Value mismatch')
        else:
            df[y] = {x:v}

    df = pd.DataFrame(df)

    return df[df.index]
