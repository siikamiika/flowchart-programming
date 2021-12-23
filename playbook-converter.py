#!/usr/bin/env python3

import sys
import itertools
import json
import functools

from ruamel.yaml import YAML

class Node:
    def __init__(self, node_id, next_nodes):
        self.node_id = node_id
        self.next_nodes = next_nodes

    def get_next_nodes_flat(self):
        return list(itertools.chain(*self.next_nodes.values()))

class GraphSequenceTransformer:
    def __init__(self, nodes):
        self._nodes = nodes

    def transform(self, start_node):
        return self._transform_graph_sequence(start_node.node_id)

    @functools.lru_cache(2**16)
    def _transform_graph_sequence(self, n, stop=None):
        parts = []
        parts.append(n)
        while True:
            node = self._nodes[n]
            next_nodes = node.get_next_nodes_flat()
            if len(next_nodes) == 0:
                break
            elif len(next_nodes) == 1:
                # 1:1 link unless n is stop
                n = next_nodes[0]
                if n == stop:
                    break
                parts.append(n)
            else:
                # preserve condition object structure
                # and append to parts recursively
                n = self._get_first_common_node(n)
                parts2 = {}
                for k, v in node.next_nodes.items():
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
                parts.append(n)
        return parts

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
        node = self._nodes[n]
        if not node.next_nodes:
            return [{n: depth}]
        out = []
        for n2 in node.get_next_nodes_flat():
            for depths in self._get_node_depths(n2, depth + 1):
                out.append({n: depth, **depths})
        return out

class SequenceRenderer:
    def __init__(self, data_sources):
        self._data_sources = data_sources

    def render(self, transform):
        return getattr(self, f'_render_{type(transform).__name__}')(transform)

class PlaybookDictRenderer(SequenceRenderer):
    def _render_str(self, transform):
        task = self._data_sources['playbook']['tasks'][transform]
        return f'{transform} - {task["task"]["name"]}'

    def _render_list(self, transform):
        return [self.render(t) for t in transform]

    def _render_dict(self, transform):
        return {k: self.render(v) for k, v in transform.items()}

def main():
    with open(sys.argv[1]) as f:
        yaml = YAML()
        playbook = yaml.load(f)
    nodes = {
        t['id']: Node(t['id'], t['nexttasks'] if 'nexttasks' in t else {})
        for t in playbook['tasks'].values()
    }
    playbook_transform = GraphSequenceTransformer(nodes).transform(nodes[playbook['starttaskid']])
    playbook_render = PlaybookDictRenderer({'playbook': playbook}).render(playbook_transform)
    print(json.dumps(playbook_render, indent=4))

if __name__ == '__main__':
    main()
