"""Facility to render node graphs using pydot"""
import os

import pydot
from logbook import Logger

from kitchen.settings import STATIC_ROOT, REPO, COLORS
from kitchen.dashboard.chef import get_role_groups

log = Logger(__name__)


def _build_links(nodes):
    """Returns a dictionary of nodes that have links to other nodes
    A node builds its links by looking for other nodes with roles present
    in its 'client_nodes' lists

    """
    linked_nodes = {}
    for node in nodes:
        links = {}
        for attr in node.keys():
            client_roles = []
            try:
                client_roles = node[attr]['client_roles']
            except (TypeError, KeyError):
                pass
            for client_node in nodes:
                if set.intersection(
                        set(client_roles), set(client_node['roles'])):
                    links.setdefault('client_nodes', [])
                    links['client_nodes'].append((client_node['name'], attr))
            needs_roles = []
            try:
                needs_roles = node[attr]['needs_roles']
            except (TypeError, KeyError):
                pass
            for needed_node in nodes:
                if set.intersection(
                        set(needs_roles), set(needed_node['roles'])):
                    links.setdefault('needs_nodes', [])
                    links['needs_nodes'].append((needed_node['name'], attr))
        if (len(links.get('client_nodes', [])) or
                len(links.get('needs_nodes', []))):
            linked_nodes[node['name']] = links
    return linked_nodes


def generate_node_map(nodes, roles, show_hostnames=True):
    """Generates a graphviz node map"""
    graph = pydot.Dot(graph_type='digraph')
    clusters = {}
    graph_nodes = {}

    role_colors = {}
    color_index = 0
    for role in get_role_groups(roles):
        clusters[role] = pydot.Cluster(
            role, label=role, color=COLORS[color_index], fontsize="12")
        graph.add_subgraph(clusters[role])
        role_colors[role] = COLORS[color_index]
        color_index += 1
        if color_index >= len(COLORS):
            color_index = 0

    # Create nodes
    node_labels = {}  # Only used when show_hostnames = False
    for node in nodes:
        color = "lightyellow"
        try:
            role_prefix = node['role'][0].split("_")[0]
            if role_prefix == REPO['EXCLUDE_ROLE_PREFIX']:
                role_prefix = None
                role_prefix = node['role'][1].split("_")[0]
                if role_prefix == REPO['EXCLUDE_ROLE_PREFIX']:
                    role_prefix = None
            color = role_colors[role_prefix]
        except (IndexError, KeyError):
            role_prefix = None
        label = "\n".join([role for role in node['role'] \
                          if not role.startswith(REPO['EXCLUDE_ROLE_PREFIX'])])
        if show_hostnames:
            label = node['name'] + "\n" + label
        else:
            if not label:
                label = "norole"
            if label in node_labels:
                if node_labels[label] == 1:
                    if role_prefix:
                        first_node = clusters[role_prefix].get_node(label)[0]
                    else:
                        first_node = graph.get_node(label)[0]
                    first_node.set_name(label + " (1)")
                node_labels[label] += 1
                label += " ({0})".format(node_labels[label])
            else:
                node_labels[label] = 1

        node_el = pydot.Node(label,
                             shape="box",
                             style="filled",
                             fillcolor=color,
                             fontsize="9")
        graph_nodes[node['name']] = node_el
        if role_prefix:
            clusters[role_prefix].add_node(node_el)
        else:
            graph.add_node(node_el)
    links = _build_links(nodes)
    for node in links:
        for client in links[node].get('client_nodes', []):
            edge = pydot.Edge(
                graph_nodes[client[0]],
                graph_nodes[node],
                fontsize="8",
                arrowsize=.6,
            )
            edge.set_label(client[1])
            graph.add_edge(edge)
        for client in links[node].get('needs_nodes', []):
            edge = pydot.Edge(
                graph_nodes[node],
                graph_nodes[client[0]],
                fontsize="7",
                style="dashed",
                arrowsize=.6,
            )
            edge.set_label(client[1])
            graph.add_edge(edge)
    # Generate graph
    filename = os.path.join(STATIC_ROOT, 'img', 'node_map.svg')
    try:
        graph.write_svg(filename)
    except pydot.InvocationException as e:
        log.error("pydot error: {0}".format(str(e)))
        return False, str(e)
    else:
        return True, filename
