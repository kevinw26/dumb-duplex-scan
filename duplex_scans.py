# SPDX-FileCopyrightText: 2026 Kevin Wong
# SPDX-License-Identifier: GPL-3

import argparse
import re
import textwrap
from glob import glob
from os import path

import numpy as np
import pandas as pd
import pikepdf
from pikepdf import StreamDecodeLevel, ObjectStreamMode
from tqdm import tqdm


def validate_and_parse(p):
    name = re.sub(r"\.pdf$", "", path.basename(p))
    if re.search(r" backs$", name):
        raise ValueError(f"'{p}': expected 'NAME backs reversed.pdf', not 'NAME backs.pdf'")
    m = re.match(r"^(.+?) (?:fronts|backs( reversed)?)$", name)
    if not m:
        raise ValueError(f"'{name}' does not match: 'NAME fronts.pdf' or 'NAME backs reversed.pdf'")
    return m.group(1)


class DumbPDF:
    def __init__(self, pdf):
        self.pdf = pdf

    @staticmethod
    def from_path(pdf_path):
        return DumbPDF(pikepdf.open(pdf_path))

    def reverse(self):
        self.pdf.pages.reverse()
        return self

    def interleave(self, other: 'DumbPDF'):
        pdf_out = pikepdf.Pdf.new()
        for front, back in zip(self.pdf.pages, other.pdf.pages):
            pdf_out.pages.append(front)
            pdf_out.pages.append(back)
        return DumbPDF(pdf_out)

    def save(self, save_path):
        self.pdf.remove_unreferenced_resources()
        self.pdf.save(
            save_path, compress_streams=True, recompress_flate=True, linearize=True,
            stream_decode_level=StreamDecodeLevel.generalized,
            object_stream_mode=ObjectStreamMode.generate)


if __name__ == '__main__':
    # parse arguments
    parser = argparse.ArgumentParser(
        description='Interleave PDFs',
        epilog=textwrap.dedent('''
        Expected file name convention:
            STEM fronts.pdf
            STEM backs reversed.pdf  # if pages are reversed otherwise
            STEM backs.pdf  # if pages are in encounter order
        STEM is the shared basename.
        ''').strip(),
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        'inputs', nargs='+', metavar='input',
        help='Two PDF files, or a single directory of PDFs')
    args = parser.parse_args()

    if len(args.inputs) == 2 and all(path.isfile(i) for i in args.inputs):
        # get the data
        files = pd.Series(args.inputs, name='path')
        assert len(files) % 2 == 0
    elif len(args.inputs) == 1 and path.isdir(args.inputs[0]):
        # run a glob
        _s = sorted(glob(path.join(args.inputs[0], '*.pdf')))
        files = pd.Series(_s, name='path')
    else:
        raise ValueError('Provide either two PDF files or a single directory')

    # extract the stem and construct a PDF object for each file
    files = files.to_frame()
    files['stem'] = files['path'].apply(validate_and_parse)
    files['status'] = np.where(
        files['path'].apply(path.basename).str.contains(r'\bfronts\b'), 'fronts',
        np.where(files['path'].apply(path.basename).str.contains(r'\bbacks\b'), 'backs', pd.NA)
    )
    files['reversed'] = files['path'].str.contains('backs reversed')

    # for each stem get a cumulative count; they should all be 0
    files['i'] = files.groupby(['stem', 'status']).cumcount()
    if any(files['i'] > 0):
        too_many = files.loc[files['i'] > 0, 'stem'].drop_duplicates().to_list()
        raise ValueError('some stems are duplicated:\n\n{}'.format('\n'.join(too_many)))

    # construct the PDFs and reverse them in place if necessary
    files['pdf'] = files['path'].apply(DumbPDF.from_path)
    for i, row in files.iterrows():
        if row['reversed']:
            files.loc[i, 'pdf'] = row['pdf'].reverse()

    # drop the reverse column; then construct the wide files
    files.drop(columns=['reversed'], inplace=True)
    wide_files: pd.DataFrame = files.set_index(['stem', 'status'])['pdf'].unstack()

    # we should have a front and back for each set; if not, raise
    null_fronts_or_backs = wide_files[wide_files[['fronts', 'backs']].isnull().any(axis=1)]
    if len(null_fronts_or_backs) > 0:
        raise ValueError(rf'found null fronts or backs as follows:\n\n{null_fronts_or_backs}')

    # for each stem create a concat version
    for i, row in tqdm(wide_files.iterrows(), total=len(wide_files), desc='interleaving files'):
        _f, _b = row['fronts'], row['backs']
        wide_files.loc[i, 'concat_pdf'] = _f.interleave(_b)
        tqdm.write(f'interleaved {row.name}')

    # for each save at the stem location
    wide_files.reset_index(inplace=True)

    # construct output paths
    wide_files['output_dir'] = \
        (
            wide_files['stem']
            .map(
                files.loc[files['status'] == 'fronts', ['stem', 'path']].drop_duplicates()
                .set_index('stem')['path'])
            .apply(path.dirname)
        )
    wide_files['output_path'] = np.vectorize(path.join)(
        wide_files['output_dir'], wide_files['stem'] + ' interleaved.pdf')

    # save it
    for i, row in wide_files.iterrows():
        row['concat_pdf'].save(row['output_path'])
