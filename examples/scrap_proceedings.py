import sys
import argparse
import numpy as np
import matplotlib.pyplot as plt

sys.path.append('../')

import scrap

parser = argparse.ArgumentParser(description='Proceedings scrapper.')
parser.add_argument('proceedings', metavar='P', type=str, nargs='+',
                                       help='Proceedings list')

args = parser.parse_args()
print('Searching in proceedings: {}'.format(args.proceedings))

sources_dict = {
    'neurips': [str(x) for x in reversed(range(1987, 2020))],
    'mlr': ['v{}'.format(x) for x in reversed(range(1, 119))],
    'aaai': [str(x) for x in reversed(range(1980, 2020))],
}

sources_dict = {key: value for key, value in sources_dict.items() if key in
                args.proceedings}

regexes = {
    'calibration': r'calibration',
    'uncertainty': r'uncertainty',
    'cost-sensitive': r'cost-sensitive',
    'confidence': r'confidence',
}

perc = {proc_name: {reg: [] for reg in regexes.keys()} for proc_name in
          sources_dict.keys()}
count = {proc_name: {reg: [] for reg in regexes.keys()} for proc_name in
          sources_dict.keys()}

for source, volumes in sources_dict.items():
    for volume in volumes:
        print('Proceeding {}, volume {}'.format(source, volume))
        for reg in regexes.keys():
            perc[source][reg].append(np.NaN)
            count[source][reg].append(np.NaN)
        print('Downloading list of papers')
        try:
            proc_info_list = scrap.get_proceedings(source, volume)
        except Exception as e:
            print('There was an error while getting the papers list')
            print(e)

        if len(proc_info_list) == 0:
            continue

        print('Downloading pdfs')
        try:
            scrap.download_proceedings(proc_info_list)
        except Exception as e:
            print('There was an error while downloading the papers')
            print(e)

        print('Converting to text')
        try:
            proc_text = scrap.read_proceedings(proc_info_list)
        except Exception as e:
            print('There was an error while converting to text')
            print(e)
            print(sys.exc_info)
            exit()

        print('Counting regular expressions')
        regexes_counts = scrap.regexes_in_proceedings(regexes, proc_text)

        if len(proc_text) == 0:
            continue

        for reg in regexes.keys():
            print('Converting counts into a matrix')
            matrix_counts = scrap.regexes_to_matrix(regexes_counts,
                                                    regexes_in=[reg])
            print('Matrix counts')
            print(matrix_counts)

            match_count = matrix_counts.iloc[0][0]
            perc[source][reg][-1] = match_count / len(proc_text)
            count[source][reg][-1] = len(proc_text)

    fig = plt.figure(figsize=(7, 3))
    ax = fig.add_subplot()
    ax.set_title('{} Proceedings'.format(source.upper()))
    ax.set_ylabel('# explored articles (bars)')
    ax.bar(list(range(len(volumes))),
            list(reversed(count[source][reg])), fill=False, color='k')
    ax.set_xticks(list(range(len(volumes)))[0:-1:5])
    ax.set_xticklabels(list(reversed(volumes))[0:-1:5], rotation=45)
    ax.set_xlim(0, len(volumes))

    ax2 = ax.twinx()  # instantiate a second axes that shares the same
    ax2.set_ylabel('Proportion containing regexp')
    for reg in regexes:

        ax2.plot(list(range(len(volumes))),
                list(reversed(perc[source][reg])),
                '.-',
                label=reg)
    ax2.set_ylim((0, ax2.get_ylim()[1]))
    ax2.legend(loc='upper left')
    fig.tight_layout()
    fig.savefig('{}.svg'.format(source))
    plt.close(fig)
