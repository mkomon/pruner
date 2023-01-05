"""
Pruner - prune backups and keep daily/weekly/monthly/yearly files.

Copyright (c) 2023 Martin Komon <martin@mkomon.cz>
Released under MIT license, see LICENSE.txt.
"""

import argparse
import datetime
import unittest

from .filedata import td, td_result, td_buckets_result
from pruner import create_file_list_from_filenames, create_time_buckets, list_files_to_prune, \
    split_into_buckets, File, RetentionPolicy, human_size, main

# settings used to create test fixtures - must be passed to unit tests
TD_TIMESTAMP = datetime.datetime(2023, 1, 4, 15, 00, 00)
TD_RETENTION = RetentionPolicy(daily=7, weekly=12, monthly=6, yearly=1)

DEF_ARGS = {
    'daily': 7,
    'weekly': 12,
    'monthly': 6,
    'yearly': 5,
    'ext': 'gz.gpg',
    'size': 512*1024,
    'filenames': [],
    'apply': False,
}

class PrunerTestBase(unittest.TestCase):
    def test_regex(self):
        assert File('db-backup_2022-12-16-17-28-25.gz.gpg', min_size=0).date_stamp == '2022-12-16'
        assert File('db-backup_2022-12-16-17:28:25.gz.gpg', min_size=0).date_stamp == '2022-12-16'
        assert File('db-backup_20221216172825.gz.gpg', min_size=0).date_stamp == '2022-12-16'
        assert File('db-backup_2022121617:28:25.gz.gpg', min_size=0).date_stamp == '2022-12-16'
        assert File('2022-12-16-17-28-25_db_backup.gz.gpg', min_size=0).date_stamp == '2022-12-16'
        assert File('2022-12-16-17:28:25_db_backup.gz.gpg', min_size=0).date_stamp == '2022-12-16'
        assert File('20221216172825_db_backup.gz.gpg', min_size=0).date_stamp == '2022-12-16'
        assert File('2022121617:28:25_db_backup.gz.gpg', min_size=0).date_stamp == '2022-12-16'
        assert File('2022-12-16-17-28-25.gz.gpg', min_size=0).date_stamp == '2022-12-16'
        assert File('2022-12-16-17:28:25.gz.gpg', min_size=0).date_stamp == '2022-12-16'
        assert File('20221216172825.gz.gpg', min_size=0).date_stamp == '2022-12-16'
        assert File('2022121617:28:25.gz.gpg', min_size=0).date_stamp == '2022-12-16'
        assert File('db-backup_2022-02-28-17-28-25.gz.gpg', min_size=0).date_stamp == '2022-02-28'
        assert File('db-backup_2022-02-29-17-28-25.gz.gpg', min_size=0).date_stamp == '2022-02-29'
        assert File('db-backup_2022-02-30-17-28-25.gz.gpg', min_size=0).date_stamp == '2022-02-30'
        assert File('db-backup_2022-02-31-17-28-25.gz.gpg', min_size=0).date_stamp == '2022-02-31'
        assert File('db-backup_2022-02-32-17-28-25.gz.gpg', min_size=0).date_stamp == ''

    def test_get_bucket(self):
        """Test get_bucket with various filename formats."""
        assert 'db-backup' == File('db_backup_2022-12-16-17-28-25.gz.gpg', min_size=0).get_bucket()
        assert 'db-backup' == File('db-backup_2022-12-16-17-28-25.gz.gpg', min_size=0).get_bucket()
        assert 'db-backup' == File('db-backup-2022-12-16-17-28-25.gz.gpg', min_size=0).get_bucket()
        assert 'backup-db' == File('2022-12-16-17-28-25-backup-db.gz.gpg', min_size=0).get_bucket()
        assert 'backup-db' == File('2022-12-16-17-28-25-backup_db.gz.gpg', min_size=0).get_bucket()
        assert 'backup-db' == File('2022-12-16-17-28-25_backup_db.gz.gpg', min_size=0).get_bucket()
        assert 'default' == File('2022-12-16-17-28-25.gz.gpg', min_size=0).get_bucket()

    def test_split_into_buckets(self):
        file_list = create_file_list_from_filenames(td)
        assert split_into_buckets(file_list) == td_buckets_result

    def test_create_time_buckets(self):
        file_list = create_file_list_from_filenames(td)
        buckets = split_into_buckets(file_list)
        for bucket_name, files in buckets.items():
            assert create_time_buckets(files, retention_policy=TD_RETENTION, now=TD_TIMESTAMP) == td_result[bucket_name]

        retention_policy = RetentionPolicy(0, 0, 0, 0)
        create_time_buckets(files, retention_policy)

    def test_list_files_to_prune(self):
        with self.assertRaises(AssertionError):
            list_files_to_prune([], TD_RETENTION)

        file_list = create_file_list_from_filenames(td)
        list_files_to_prune(file_list, TD_RETENTION)

    def test_human_size(self):
        assert human_size(24) == '24 B'
        assert human_size(1024) == '1.00 kB'
        assert human_size(2048) == '2.00 kB'
        assert human_size(1212048) == '1.16 MB'
        assert human_size(21212048) == '20.23 MB'
        assert human_size(121212048) == '115.60 MB'
        assert human_size(2121212048) == '1.98 GB'

    def test_args_default_values(self):
        args = argparse.Namespace(**DEF_ARGS)
        with self.assertRaises(SystemExit) as e:
            main(args)
        assert e.exception.code == 0

    def test_args_ext(self):
        args = argparse.Namespace(**DEF_ARGS)
        setattr(args, 'ext', 'tgz')
        with self.assertRaises(SystemExit) as e:
            main(args)
        assert e.exception.code == 0

    def test_args_different_values(self):
        args = argparse.Namespace(**DEF_ARGS)
        setattr(args, 'daily', 0)
        setattr(args, 'weekly', 0)
        setattr(args, 'monthly', 0)
        setattr(args, 'yearly', 0)
        with self.assertRaises(SystemExit) as e:
            main(args)
        assert e.exception.code == 0

        args = argparse.Namespace(**DEF_ARGS)
        setattr(args, 'size', 0)
        with self.assertRaises(SystemExit) as e:
            main(args)
        assert e.exception.code == 0

        args = argparse.Namespace(**DEF_ARGS)
        setattr(args, 'size', 1024)
        with self.assertRaises(SystemExit) as e:
            main(args)
        assert e.exception.code == 0
