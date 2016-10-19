#!/usr/bin/python3
# -*- coding: utf-8 -*-

# Copyright © 2016 Martin Ueding <dev@martin-ueding.de>

import argparse
import itertools
import os.path
import shlex
import shutil
import subprocess
import sys
import uuid

import matplotlib.pyplot as pl
import numpy as np
import scipy.misc


def print_error(error, printed_errors=[]):
    str_error = str(error)
    if not str_error in printed_errors:
        print(str_error)
        printed_errors.append(str_error)


def print_phase_start(title, phase=[1]):
    print()
    print('=== Phase {}: {} ==='.format(phase[0], title))
    print()
    phase[0] += 1


def print_errors(errors):
    if len(errors) > 0:
        print_phase_start('Print Errors')
        for error in set(map(str, errors)):
            print(error)


def get_difference(filename_1, filename_2):
    filenames = [filename_1, filename_2]
    images = [scipy.misc.imread(name) for name in filenames]
    shapes = [im.shape for im in images]

    if shapes[0] < shapes[1]:
        first = images[0]
        second = scipy.misc.imresize(images[1], shapes[0], 'bilinear')
    else:
        first = images[1]
        second = scipy.misc.imresize(images[0], shapes[1], 'bilinear')

    difference = np.subtract(first.astype(int), second.astype(int))
    average = np.mean(difference**2)
    return average


def get_all_files(dirs):
    print_phase_start('Traverse Paths')

    paths = []
    for dir in dirs:
        for dirpath, dirnames, filenames in os.walk(dir):
            print(dirpath)
            for filename in filenames:
                paths.append(os.path.join(dirpath, filename))

    return paths


def normalize_image(filename):
    image = scipy.misc.imread(filename)
    shape = image.shape
    resized = scipy.misc.imresize(image, (100, 100), 'bilinear')
    return resized, shape


def build_library(paths, limit):
    print_phase_start('Read Images')

    if limit is None:
        limit = len(paths)

    print('Have {} images to read'.format(limit))
    print()

    i = 0
    library = []
    errors = []
    for path in paths[:limit]:
        try:
            normalized, shape = normalize_image(path)
        except ValueError as e:
            errors.append(e)
        except OSError as e:
            errors.append(e)
        else:
            library.append((path, normalized, shape))

        if i % 20 == 0:
            print('{:5d} {}'.format(i, path))
        i += 1

    print_errors(errors)

    return library


def get_doubles(library, max_average):
    print_phase_start('Find Duplicates')

    doubles = {}
    for i in range(len(library)):
        print('Working on {:d} …'.format(i))

        if any(i in seconds for first, seconds in doubles.items()):
            print('Skipping {} because it is marked as a double already'.format(i))
            continue

        doubles_i = get_doubles_of(library, i, max_average)

        if len(doubles_i) > 0:
            doubles[i] = doubles_i

    return doubles


def get_doubles_of(library, i, max_average):
    errors = []

    averages = map(lambda j: get_distance(library, i, j), range(i + 1, len(library)))

    doubles_i = [
        idx
        for idx, average in zip(itertools.count(0), averages)
        if average < max_average
    ]

    return doubles_i


def get_distance(library, i, j):
    filename1, normalized1, shape1 = library[i]
    filename2, normalized2, shape2 = library[j]

    try:
        difference = np.subtract(normalized1.astype(int), normalized2.astype(int))
        average = np.mean(np.abs(difference))
    except ValueError as e:
        print_error(e)
        return float('inf')

    return average


def argmax(iterable):
    '''
    http://stackoverflow.com/a/26726185
    '''
    return max(enumerate(iterable), key=lambda x: x[1])[0]


def find_best_in_set(doubles, library, move_to):
    print_phase_start('Find Best Image in Set')

    moves = []
    for i, js in doubles.items():
        candidate_ids = [i] + js
        shapes = [library[c][2] for c in candidate_ids]
        best_idx = argmax(shapes)
        best_i = candidate_ids[best_idx]
        move_idxs = list(range(len(js) + 1))
        del move_idxs[best_idx]

        del candidate_ids[best_idx]

        shape_keep = shapes[best_idx]
        shapes_move = [shapes[x] for x in move_idxs]

        print('Keeping {}; deleting {}.'.format(best_i, ', '.join(map(str, candidate_ids))))
        print('Keeping {}; deleting {}.'.format(shape_keep, ', '.join(map(str, shapes_move))))

        filename_keep, normalized_keep, shape_keep = library[best_i]
        for candidate_id in candidate_ids:
            filename_move, normalized_move, shape_move = library[candidate_id]

            destination = os.path.join(move_to, os.path.basename(filename_move))
            while os.path.isfile(destination):
                base, ext = os.path.splitext(filename_move)
                destination = os.path.join(
                    move_to,
                    uuid.uuid4().hex + ext)

            moves.append((filename_move, destination))

            base, ext = os.path.splitext(destination)
            subprocess.check_call([
                'montage', filename_keep, filename_move,
                '-geometry', '200x200>+4+3',
                base + '-proof.jpg'])

            scipy.misc.imsave(base + '-keep.jpg', normalized_keep)
            scipy.misc.imsave(base + '-move.jpg', normalized_move)

    return moves


def generate_histogram(averages):
    print_phase_start('Generate Histogram')

    pl.hist(averages, bins=200)
    pl.grid(True)
    ymin, ymax = pl.ylim()
    pl.ylim(0.1, ymax)
    pl.yscale('log')
    pl.savefig('hist.pdf')

    pl.xlim(-1, 50)
    pl.savefig('hist-50.pdf')


def store_move_commands(moves, library):
    print_phase_start('Store Move Script')

    if len(moves) == 0:
        print('Nothing to move!')
        return

    with open('move-all.sh', 'w') as f:
        f.write('#!/bin/bash\n')
        f.write('# Generated by similar-images.py\n\n')
        f.write('set -x\n\n')

        for source, dest in moves:
            f.write('mv -- {} {}\n'.format(shlex.quote(source), shlex.quote(dest)))


def main():
    options = _parse_args()

    paths = get_all_files(options.dirs)
    library = build_library(paths, options.limit)
    doubles = get_doubles(library, options.average)
    moves = find_best_in_set(doubles, library, options.moveto)
    store_move_commands(moves, library)


def _parse_args():
    '''
    Parses the command line arguments.

    :return: Namespace with arguments.
    :rtype: Namespace
    '''
    parser = argparse.ArgumentParser(description='')
    parser.add_argument('dirs', nargs='+')
    parser.add_argument('--limit', type=int)
    parser.add_argument('--moveto')
    parser.add_argument('--average', type=int, default=2, help='default %(default)s')
    options = parser.parse_args()

    return options


if __name__ == '__main__':
    main()
