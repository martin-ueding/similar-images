#!/usr/bin/python3
# -*- coding: utf-8 -*-

# Copyright © 2016 Martin Ueding <dev@martin-ueding.de>

import argparse
import itertools
import os.path
import shutil
import sys
import uuid

import matplotlib.pyplot as pl
import numpy as np
import scipy.misc

def normalize_image(filename):
    image = scipy.misc.imread(filename)
    shape = image.shape
    resized = scipy.misc.imresize(image, (100, 100), 'bilinear')
    return resized, shape


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
    average = np.mean(np.abs(difference))
    return average


def main():
    options = _parse_args()

    errors = []

    if options.limit is None:
        limit = len(options.images)
        filenames = options.images
    else:
        limit = options.limit
        filenames = options.images[:options.limit]

    normalized_images = []
    shapes = []
    for i, filename in zip(itertools.count(), filenames):
        try:
            normalized, shape = normalize_image(filename)
        except ValueError as e:
            errors.append(e)
        except OSError as e:
            errors.append(e)
        else:
            normalized_images.append(normalized)
            shapes.append(shape)

        if i % 10 == 0:
            print('{:5d} {}'.format(i, filename))

    averages = []

    for i in range(len(normalized_images)):
        print('Working on {:d} of {:d} …'.format(i, limit))
        first = normalized_images[i]
        for j in range(i + 1, len(normalized_images)):
            second = normalized_images[j]

            try:
                difference = np.subtract(first.astype(int), second.astype(int))
                average = np.mean(np.abs(difference))
            except ValueError as e:
                errors.append(e)
            else:
                averages.append(average)


                if average < 2:
                    print()
                    print('{:5d} {:5d} {:10.1f}'.format(i, j, average))
                    print(options.images[i], filenames[j])

                    print(shapes[i], shapes[j])

                    if shapes[i] < shapes[j]:
                        to_delete = filenames[i]
                    else:
                        to_delete = filenames[j]

                    print('Suggest deletion of', to_delete)

                    if options.moveto is not None:
                        if os.path.isfile(to_delete):
                            destination = os.path.join(options.moveto, os.path.basename(to_delete))
                            while os.path.isfile(destination):
                                base, ext = os.path.splitext(to_delete)
                                destination = os.path.join(
                                    options.moveto,
                                    uuid.uuid4().hex + ext)
                            shutil.move(to_delete, destination)


    pl.hist(averages, bins=200)
    pl.yscale('log')
    pl.savefig('hist.pdf')

    if len(errors) > 0:
        print()
        print('Errors:')
        for error in set(map(str, errors)):
            print(error)

    print()
    print('Done!')


def _parse_args():
    '''
    Parses the command line arguments.

    :return: Namespace with arguments.
    :rtype: Namespace
    '''
    parser = argparse.ArgumentParser(description='')
    parser.add_argument('images', nargs='+')
    parser.add_argument('--limit', type=int)
    parser.add_argument('--moveto')
    options = parser.parse_args()

    return options


if __name__ == '__main__':
    main()
