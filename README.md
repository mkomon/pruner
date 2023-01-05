# Pruner

*Prune (backup) files, keeping daily/weekly/monthly/yearly backups for a predefined time period based on date in their filename.*

[![CircleCI](https://dl.circleci.com/status-badge/img/gh/mkomon/pruner/tree/master.svg?style=shield)](https://dl.circleci.com/status-badge/redirect/gh/mkomon/pruner/tree/master)
[![ShieldsIO](https://img.shields.io/badge/licence-MIT-blue)](https://github.com/mkomon/pruner/LICENSE.txt)
[![ShieldsIO](https://img.shields.io/badge/python-v3.8-yellowgreen)](https://github.com/mkomon/pruner)

## Who may want to use it (and when)

Anyone who does not use a sophisticated backup solution and periodically dumps their backups into a directory, perhaps daily. After a while the number of files becomes to grow and it may not be necessary to keep daily backups for months. That's when pruner.py comes useful.

Pruner is intended to be run manually every once in a while (e.g. each month) in the interactive mode.

## Filename format requirements

Pruner requires one of the following date formats included in file names:

- YYYY-mm-dd
- YYYY_mm_dd
- YYYYmmdd

There may be also the time of the backup in the file name but it is ignored.

Any other text in the file name is used to group files together so that multiple sets of backups
can be stored in a single directory and pruned all at once.

## Extras

When processing input files Pruner checks the size of each file and can point out when files are too small, potentially indicating a failing backup. The size threshold is 512 kB by default and can be changed using the `-s` option.

## Installation

1. Install the required dependencies

    ```shell
    pip install py-console
    ```

2. and copy the `pruner.py` script wherever you want.

## Usage

Run for all files in the current directory:

```shell
./prune.py [...]
```

Use shell wildcard expansion to run for a subset of the files in the current directory:

```shell
./prune.py [...] db-backup*
```

Or pass a path to a directory and all files in that directory will be processed (respecting the file extension):

```shell
./prune.py [...] ./db-backups/
```

Pruner runs in the interactive mode with human supervision. You will see a list of the files before they are deleted and you will be prompted to confirm the deletion.

Pruner processes only files with a particular extension and ignores all other files. By default this extension is `gz.gpg` but this can be changed by using the `-e` option, e.g. `-e tgz` or `-e zip`.

## Known limitations

- POSIX compliant in theory but not tested on any other system than Debian Linux
- only works in the interactive mode, no quiet or batch mode at the moment
- works only for years 1900-2099 (r_date_stamp regex uses this limitation to reliably find the year and the start of the date in the filename)
