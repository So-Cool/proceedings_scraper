import scrap
import sys


sources_dict = {
    'nips': [str(x) for x in range(1987, 2021)],
    'mlr': ['v{}'.format(x) for x in range(1, 161)],
    'aaai': [str(x) for x in range(1980, 2021)],
}

regexes = {
    'calibration': r'calibration',
    'uncertainty': r'uncertainty',
}

for source, volumes in sources_dict.items():
    for volume in volumes:
        print('Proceeding {}, volume {}'.format(source, volume))
        try:
            print('Downloading list of papers')
            proc_info_list = scrap.get_proceedings(source, volume)

            print('Downloading pdfs')
            scrap.download_proceedings(proc_info_list)

            print('Converting to text')
            proc_text = scrap.read_proceedings(proc_info_list)

            print('Counting regular expressions')
            regexes_counts = scrap.regexes_in_proceedings(regexes, proc_text)

            print('Converting counts into a matrix')
            matrix_counts = scrap.regexes_to_matrix(regexes_counts, regexes_in=['calibration'])

            print('Matrix counts')
            print(matrix_counts)
        except:
            print("Unexpected error:", sys.exc_info()[1])
            pass
