#!/usr/bin/env python3
"""
Pruner - prune backups and keep daily/weekly/monthly/yearly files.

Copyright (c) 2023 Martin Komon <martin@mkomon.cz>
Released under MIT license, see LICENSE.txt.
"""

__version__ = '0.1.0'

import argparse
import datetime
import os
import re
import sys
import time
import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import List, Dict

from py_console import console, bgColor, textColor
from py_console.console import Console

SAFETY_DELAY = 10

console.setShowTimeDefault(False)

def human_size(size: int) -> str:
    """
    Convert file size from bytes into human-friendly format.
    """
    if size < 1024:
        return f'{size} B'
    if size < 1024*1024:
        return f'{size/1024:.2f} kB'
    if size < 1024*1024*1024:
        return f'{size/1024/1024:.2f} MB'
    return f'{size/1024/1024/1024:.2f} GB'

class LoggingProxy:
    def __init__(self, console: Console) -> None:
        self.level = logging.INFO
        self.console = console

    def setLevel(self, level):
        self.level = level

    def debug(self, msg):
        if self.level == logging.DEBUG:
            console.log(msg)

    def info(self, msg):
        console.info(msg)

    def warn(self, msg):
        console.warn(msg)

    def error(self, msg):
        console.error(msg)

    def success(self, msg):
        console.success(msg)
    
    def log(self, msg):
        console.log(msg)

log = LoggingProxy(console=console)

@dataclass()
class RetentionPolicy:
    """Just keep related data together, doing nothing fancy with it."""
    daily: int = 7
    weekly: int = 12
    monthly: int = 6
    yearly: int = 5


class File:
    # this looks ugly but just matches YYYY-mm-dd format, with dashes (or underscores) optional,
    # providing a match object with 5 named groups (year, sep1, month, sep2, day)
    r_date_stamp = re.compile(r'(?P<year>(?:19|20)[0-9][0-9])'
                              r'(?P<sep1>[-_]?)'
                              r'(?P<month>0[1-9]|1[0-2])'
                              r'(?P<sep2>[-_]?)'
                              r'(?P<day>0[1-9]|1[0-9]|2[0-9]|3[01])'
                              r'[0-9:_-]{6,10}')  # optional time, don't match into group
                                                  # (but itbecomes a part of group 0 so don't use group 0)

    def __init__(self, filename, min_size=0) -> None:
        self.original_filename = filename
        self.base_filename = os.path.basename(filename)  # throw away path
        self.filename = self.base_filename.split(os.path.extsep)[0]  # and all file extensions
        self.internal_filename = self.filename.replace('_', '-')
        self.min_size = min_size

        if m := self.r_date_stamp.search(self.base_filename):
            self.ds_start, self.ds_end = m.span()
            self.date_stamp = '-'.join([m.group(1), m.group(3), m.group(5)])
        else:
            self.date_stamp = ''
            self.ds_start, self.ds_end = -1, -1

        if min_size:
            size = os.stat(filename).st_size
            if size < min_size:
                log.warn(f'File {filename} is too small ({human_size(size)}),'
                    ' indicating a potentially failing backup!')

    def __str__(self) -> str:
        return self.base_filename

    def __repr__(self) -> str:
        return f"File('{self.original_filename}', min_size={self.min_size})"

    def __eq__(self, other: object) -> bool:
        return self.original_filename == other.original_filename

    def get_bucket(self):
        """
        Analyze filename and return the name of bucket for the file based on a common part of the filename.
        This is to allow processing of groups of files that belong together and only differ in the numeric
        portion of the filename.
        """

        if self.ds_start == self.ds_end == -1:
            return self.internal_filename

        if self.ds_start > len(self.internal_filename) - self.ds_end:
            if self.ds_start > 1 and self.internal_filename[self.ds_start - 1] == '-':
                self.ds_start -= 1
            return self.internal_filename[:self.ds_start]

        if self.ds_end < len(self.internal_filename) and self.internal_filename[self.ds_end] == '-':
            self.ds_end += 1
        if self.internal_filename[self.ds_end:]:
            return self.internal_filename[self.ds_end:]
        return 'default'


def split_into_buckets(file_list: List[File]) -> Dict[str, List[File]]:
    """
    Separate files into buckets based on their shared name structure. This allows to process
    multiple time series of backup files stored in a single directory.

    Imagine the following files in a directory:
    |- db-backup-1.tgz
    |- db-backup-2.tgz
    |- db-backup-3.tgz
    |- ...
    |- mail-backup-1.tgz
    |- mail-backup-2.tgz
    |- mail-backup-2.tgz
    |- ...
    |- 2023-01-01.tgz

    then the files will be put in buckets as follows:
    bucket 'db-backup': [db-backup-1.tgz, db-backup-2.tgz, db-backup-3.tgz]
    bucket 'mail-backup': [mail-backup-1.tgz, mail-backup-2.tgz, mail-backup-3.tgz]
    bucket 'default': [2023-01-01.tgz]
    """
    buckets = {}
    for f in file_list:
        try:
            buckets[f.get_bucket()].append(f)
        except KeyError:
            buckets[f.get_bucket()] = [f]
    return buckets


def create_file_list_from_filenames(filenames: List[str], extension='gz.gpg', min_size=0) -> List[File]:
    """
    The point of conversion from filenames to Files, also where filtering by extension happens.
    """

    if filenames and len(filenames) == 1 and os.path.isdir(filenames[0]):
        # user passed a directory path as argument
        filenames_list = sorted([os.path.join(filenames[0], f) for f in os.listdir(filenames[0])])
    else:
        filenames_list = sorted(filenames if filenames else os.listdir())

    filenames_list = [fn for fn in filenames_list if fn.endswith(extension)]
    return [File(filename, min_size=min_size) for filename in filenames_list]


def list_files_to_prune(file_list: List[File], retention_policy: RetentionPolicy) -> List[File]:
    """
    List files to be deleted, keeping the oldest file in every time bucket (daily, weekly, monthly, yearly).
    """
    assert file_list, "file_list is empty"

    buckets = split_into_buckets(file_list)

    log.debug(f'Scanning total of {len(file_list)} files.')
    log.debug(f'Sorted {len(file_list)} files into {len(buckets)} bucket{"s" if len(buckets) > 1 else ""} '
    f'with {"/".join([str(len(b)) for b in buckets.values()])} files in {"them" if len(buckets) > 1 else "it"}.')

    files_to_delete = []
    for bucket_name, files in buckets.items():
        log.debug(f'Checking bucket {bucket_name}')
        file_buckets = create_time_buckets(files, retention_policy)

        # check all time buckets, keep the 1st file in each bucket and the rest are candidates to be deleted
        for bucket_name, time_buckets in file_buckets.items():
            for filenames in time_buckets.values():
                files_to_delete += filenames[1:]
                log.debug(f'keep file {filenames[0]} ({bucket_name})')

    return files_to_delete


def create_time_buckets(files: List[File], retention_policy: RetentionPolicy, now=datetime.datetime.now()) -> Dict[str, Dict[int, List[File]]]:
    """
    Separate Files into daily/weekly/monthly/yearly buckets based on their date and retention policy.
    """
    buckets = {
        'daily': defaultdict(list),
        'weekly': defaultdict(list),
        'monthly': defaultdict(list),
        'yearly': defaultdict(list),
        'obsolete': defaultdict(list),
    }
    days_ago = 0
    max_days = 365*40  # max 40 years history should suffice
    while files:
        d = now - datetime.timedelta(days=days_ago)
        date_stamp = f'{d.year}-{d.month:02}-{d.day:02}'
        days_ago += 1
        if days_ago >= max_days:
            log.warn(f'There are {len(files)} of files that cannot be sorted into time buckets!')
            for f in files:
                log.log(f.filename)
            break

        processed_files = []
        for f in files:
            if date_stamp in f.internal_filename:
                if days_ago <= retention_policy.daily:
                    buckets['daily'][days_ago].append(f)
                    processed_files.append(f)
                elif days_ago <= retention_policy.weekly * 7 + 1:
                    buckets['weekly'][days_ago // 7].append(f)
                    processed_files.append(f)
                elif days_ago <= retention_policy.monthly * 30 + 3:
                    # more than 28 would remove the monthly backup for February
                    buckets['monthly'][days_ago // 28].append(f)
                    processed_files.append(f)
                elif days_ago <= retention_policy.yearly * 365 + 2:
                    buckets['yearly'][days_ago // 365].append(f)
                    processed_files.append(f)
                else:
                    buckets['obsolete'][0].append(f)
        for f in processed_files:
            files.remove(f)

    return buckets


def print_time_buckets(buckets: Dict[str, Dict[str, Dict[int, List[File]]]]) -> None:
    """For debug only; print time buckets in a fancy format."""
    log.log('======BUCKETS======')
    for bucket_name, time_buckets in buckets.items():
        log.log(f'{bucket_name}')
        for bucket_num, files in time_buckets.items():
            if len(files) == 1:
                log.log(f'\t{bucket_num}\t{files[0].base_filename}')
            else:
                log.log(f'\t{bucket_num}')
                for f in files:
                    log.log(f'\t\t{f.base_filename}')


def prune_yes_i_know_what_i_am_doing(files_to_delete: List[File]) -> int:
    """
    Perform the deletion of files given as a list of filenames.
    CAUTION: No confirmations, prompts or other safety mechanisms provided.
    """
    files_deleted = 0
    for f in files_to_delete:
        os.unlink(f.original_filename)
        files_deleted += 1
    return files_deleted

def main(args: argparse.Namespace):

    retention_policy = RetentionPolicy(args.daily, args.weekly, args.monthly, args.yearly)
    log.debug('Using the following retention policy:')
    log.debug(f'- keep up to {retention_policy.daily} daily files')
    log.debug(f'- keep up to {retention_policy.weekly} weekly files')
    log.debug(f'- keep up to {retention_policy.monthly} monthly files')
    log.debug(f'- keep up to {retention_policy.yearly} yearly files')

    file_list = create_file_list_from_filenames(args.filenames, extension=args.ext, min_size=args.size)
    if not file_list:
        log.warn(f'No files found to process. Did you forget to use the -e option? Currently '
            f'using {args.ext} file extension.')
        sys.exit(0)

    files_to_delete = list_files_to_prune(file_list, retention_policy)

    log.info('\nThe following files are to be deleted:')
    if files_to_delete:
        for f in files_to_delete:
            log.log(f.base_filename)
    else:
        console.log('[no files]')

    if args.apply:
        log.warn('\n=============================== WARNING ===============================')
        log.warn(f'You are going to delete all the files listed above ({len(files_to_delete)} files in total).')
        log.warn('Please review them carefully once more and confirm the deletion.')
        message = console.highlight("Do you want to proceed and delete all the files listed above? (y/n): ",
            bgColor=bgColor.RESET, textColor=textColor.RED)
        while (reply := input(message).lower()) not in ("y", "n"): pass
        if reply != 'y':
            log.success('No changes made.')
            sys.exit()
        log.warn(f'Proceeding with removing in {SAFETY_DELAY} seconds, '
                    f'this is your last chance\nto interrupt the script using Ctrl+C!')
        for _ in range(SAFETY_DELAY, SAFETY_DELAY // 2, -1):
            log.warn(_)
            time.sleep(1)
        for _ in range(_ - 1, 0, -1):
            log.error(_)
            time.sleep(1)
        files_deleted = prune_yes_i_know_what_i_am_doing(files_to_delete)
        log.success(f'Deleted {files_deleted} files.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Backup files pruner.')
    parser.add_argument('-e', '--ext', type=str, default="gz.gpg", help='process only files with the given file extension; default = gz.gpg')
    parser.add_argument('-s', '--size', type=int, default=512*1024, help='warn if file has size smaller than x bytes; 0 to disable; default = 512 kB')
    parser.add_argument('-V', '--version', action='store_true', help='display version and quit')
    parser.add_argument('-v', '--verbose', action='store_true', help='enable verbose output')
    parser.add_argument('--apply', action='store_true', default=True, help=argparse.SUPPRESS)

    parser.add_argument('--daily', type=int, default=7, help='the number of daily backups to keep; default = 7')
    parser.add_argument('--weekly', type=int, default=12, help='the number of daily backups to keep; default = 12')
    parser.add_argument('--monthly', type=int, default=6, help='the number of daily backups to keep; default = 6')
    parser.add_argument('--yearly', type=int, default=5, help='the number of daily backups to keep; default = 5')

    # parser.add_argument('-q', '--quiet', action='store_true', help='disable logging below error level')
    parser.add_argument('filenames', nargs='*', default='', type=str, help='Only consider given files.')
    args = parser.parse_args()

    if args.version:
        log.log(f'Pruner version {__version__}')
        log.log(f'https://github.com/mkomon/pruner')
        sys.exit(0)

    if args.verbose:
        log.setLevel(logging.DEBUG)

    log.log(f'Pruner v{__version__} - prune backups and keep daily/weekly/monthly/yearly files.')

    if not args.filenames:
        log.log(f'Not given specific files to process - scanning the current directory for {args.ext} files.')

    main(args)
