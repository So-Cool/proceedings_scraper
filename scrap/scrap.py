# %load_ext autoreload
# %autoreload 2

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os
import pandas as pd
import PyPDF2
import re
import requests
import sys
import bs4

ROOT_TEMPDIR = os.path.expanduser('~/scraper_temp_pdfs/')
FIX_PYPDF2 = True

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

def extract_html_elemennt(webpage, class_name):
    soup = bs4.BeautifulSoup(webpage, 'html.parser')
    papers_html = soup.find_all(class_=class_name)  # Extract tags with given class
    return papers_html

def parse_mlr_proceedings(mlr_proceedings, volume):
    def print_error(url_type, title):
        print('Error processing {} url for: "{}"'.format(url_type, title))

    source = 'mlr'
    class_name = 'paper'
    webpage_class = extract_html_elemennt(mlr_proceedings, class_name)

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
    mlr_proceedings_url = 'http://proceedings.mlr.press/{}/'.format(volume)
    webpage_text = load_webpage(mlr_proceedings_url)
    mlrp_data = parse_mlr_proceedings(webpage_text, volume)
    return mlrp_data

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
                if filename is not None:
                    file_path = os.path.join(proceedings_dir, filename)
                    cl, cs = pdf_to_string(file_path)
                else:
                    cl, cs = '', ''
                dataset[-1][r+'_contents'] = cs
            print_progress(i+1, progress_length, prefix='Progress:', suffix='Complete', bar_length=50)

        dataset_df = pd.DataFrame(dataset)

        if save_df:
            print('Saving the data frame to pickle: {}'.format(df_pickle_path))
            dataset_df.to_pickle(df_pickle_path)
            # dataset_df.to_csv(os.path.join(proceedings_dir,'_proceedings.csv'), header=True, index=False)

    return dataset_df

def regex_in_proceedings(regex, proceedings_df, columns=['pdf', 'pdf_sup']):
    pattern = re.compile(regex, re.IGNORECASE)
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
