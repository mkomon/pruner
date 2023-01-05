"""
Pruner - prune backups and keep daily/weekly/monthly/yearly files.

Copyright (c) 2023 Martin Komon <martin@mkomon.cz>
Released under MIT license, see LICENSE.txt.
"""

import json
import os

from collections import defaultdict
from pruner import File

this_dir = os.path.dirname(__file__)
data_dir = os.path.join(this_dir, 'data')

with open(os.path.join(data_dir, 'data.input')) as f:
    td = [line.strip() for line in f.readlines()]

with open(os.path.join(data_dir, 'buckets.expected')) as f:
    tmp_data = json.load(f)
    td_buckets_result = {}
    for k, v in tmp_data.items():
        td_buckets_result[k] = []
        for f in v:
            td_buckets_result[k].append(File(f, min_size=0))

with open(os.path.join(data_dir, 'time_buckets.expected')) as f:
    tmp_data = json.load(f)
    td_result = {}
    for k1, v1 in tmp_data.items():
        td_result[k1] = {
            'daily': defaultdict(list),
            'weekly': defaultdict(list),
            'monthly': defaultdict(list),
            'yearly': defaultdict(list),
            'obsolete': defaultdict(list),
        }
        for k2, v2 in v1.items():
            for k3, v3 in v2.items():
                k3 = int(k3)
                for f in v3:
                    td_result[k1][k2][k3].append(File(f, min_size=0))
