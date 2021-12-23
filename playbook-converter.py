#!/usr/bin/env python3

import sys
import itertools
import json
import functools

from ruamel.yaml import YAML

class PlaybookConverter:
    def __init__(self, playbook):
        self._playbook = playbook

    def convert(self):
        return self._transform_graph_sequence(self._playbook['starttaskid'])

    @functools.lru_cache(2**16)
    def _transform_graph_sequence(self, n, stop=None):
        parts = []
        parts.append(self._render_node(n))
        while True:
            node = self._playbook['tasks'][n]
            if 'nexttasks' not in node:
                break
            next_nodes = list(itertools.chain(*node['nexttasks'].values()))
            if len(next_nodes) == 0:
                break
            elif len(next_nodes) == 1:
                # 1:1 link unless n is stop
                n = next_nodes[0]
                if n == stop:
                    break
                parts.append(self._render_node(n))
            else:
                # preserve condition object structure
                # and append to parts recursively
                n = self._get_first_common_node(n)
                parts2 = {}
                for k, v in node['nexttasks'].items():
                    paths = []
                    for n2 in v:
                        if n2 == stop:
                            continue
                        if n2 == n:
                            paths.append([])
                        else:
                            paths.append(self._transform_graph_sequence(n2, n))
                    if len(paths) == 1:
                        parts2[k] = paths[0]
                    elif len(paths) > 1:
                        parts2[k] = paths
                parts.append(parts2)
                if n is None or n == stop:
                    break
                parts.append(self._render_node(n))
        return parts

    def _render_node(self, n):
        return f'{n} - {self._playbook["tasks"][n]["task"]["name"]}'

    def _get_first_common_node(self, n):
        depths = self._get_node_depths(n)
        common = {}
        for depths2 in depths:
            if not common:
                common = depths2
                continue
            common = {
                k: max(common[k], depths2[k])
                for k in common.keys() & depths2.keys()
            }
        argmin = None
        for k in common:
            if common[k] == 0:
                continue
            if argmin is None:
                argmin = k
            elif common[argmin] > common[k]:
                argmin = k
        return argmin

    @functools.lru_cache(2**16)
    def _get_node_depths(self, n, depth=0):
        node = self._playbook['tasks'][n]
        if 'nexttasks' not in node:
            return [{n: depth}]
        out = []
        for n2 in itertools.chain(*node['nexttasks'].values()):
            for depths in self._get_node_depths(n2, depth + 1):
                out.append({n: depth, **depths})
        return out

def main():
    with open(sys.argv[1]) as f:
        yaml = YAML()
        playbook = yaml.load(f)
    playbook_converter = PlaybookConverter(playbook)
    print(json.dumps(playbook_converter.convert(), indent=4))

if __name__ == '__main__':
    main()
