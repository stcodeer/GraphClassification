"""main functions"""
import torch
import multiprocessing
import warnings

import networkx as nx
import numpy as np
from scipy.sparse.linalg import eigs, expm_multiply, expm
from scipy.sparse import diags
from tqdm import tqdm

PRECISION = 1e-8


class Worker:
    """worker for computing relative dimensions"""

    def __init__(self, graph, laplacian, times, spectral_gap):
        self.laplacian = laplacian
        self.times = times
        self.spectral_gap = spectral_gap
        self.graph = graph

    def __call__(self, initial_measure):
        node_trajectories = compute_node_trajectories(
            self.laplacian, initial_measure, self.times, disable_tqdm=True
        )
        return extract_relative_dimensions(
            self.times, node_trajectories, initial_measure, self.spectral_gap
        )[:2]


def run_all_sources(graph, times, use_spectral_gap=True, n_workers=1, disable_tqdm=False, directed=False):
    """compute relative dimensions of all the nodes in a graph"""
    if directed:
        total_degree = sum(graph.out_degree(u, weight="weight") for u in graph)
    else:
        total_degree = sum(graph.degree(u, weight="weight") for u in graph)
    sources = [get_initial_measure(graph, [node], total_degree, directed) for node in graph]
    return run_several_sources(
        graph,
        times,
        sources,
        use_spectral_gap=use_spectral_gap,
        n_workers=n_workers,
        disable_tqdm=disable_tqdm,
        directed=directed,
    )


def run_several_sources(
    graph, times, sources, use_spectral_gap=True, n_workers=1, disable_tqdm=False, directed=False
):
    """relative dimensions from a list of sources"""
    print("Construct Laplacian Begin.")
    laplacian, spectral_gap = construct_laplacian(graph, use_spectral_gap=use_spectral_gap, directed=directed)
    print("Construct Laplacian Finished.")
    worker = Worker(graph, laplacian, times, spectral_gap)
    print("Calculating relative dimensions ( Workers:", n_workers, ")")
    with multiprocessing.Pool(n_workers) as pool:
        out = np.array(
            list(
                tqdm(
                    pool.imap(worker, sources),
                    total=len(sources),
                    disable=disable_tqdm
                )
            )
        )


    print("Calculating relative dimensions Done ( Workers:", n_workers, ")")

    relative_dimensions = out[:, 0]
    peak_times = out[:, 1]

    np.fill_diagonal(relative_dimensions, np.nan)
    np.fill_diagonal(peak_times, np.nan)

    return relative_dimensions, peak_times


# def run_single_source(graph, times, initial_measure, use_spectral_gap=True):
#     """main function to compute relative dimensions"""
#     laplacian, spectral_gap = construct_laplacian(graph, use_spectral_gap=use_spectral_gap)

#     node_trajectories = compute_node_trajectories(laplacian, initial_measure, times)
#     (
#         relative_dimensions,
#         peak_times,
#         peak_amplitudes,
#         diffusion_coefficient,
#     ) = extract_relative_dimensions(times, node_trajectories, initial_measure, spectral_gap)

#     results = {
#         "relative_dimensions": relative_dimensions,
#         "peak_amplitudes": peak_amplitudes,
#         "peak_times": peak_times,
#         "diffusion_coefficient": diffusion_coefficient,
#         "times": times,
#         "node_trajectories": node_trajectories,
#     }

#     return results


# def run_local_dimension(
#     graph, times, use_spectral_gap=True, n_workers=1, nodes=None, disable_tqdm=False
# ):
#     """computing the local dimensionality of each node"""
#     if nodes is None:
#         nodes = graph
#     total_degree = sum(graph.degree(u, weight="weight") for u in nodes)
#     sources = [get_initial_measure(graph, [node], total_degree) for node in nodes]
#     return run_local_dimension_from_sources(
#         graph,
#         times,
#         sources,
#         use_spectral_gap=use_spectral_gap,
#         n_workers=n_workers,
#         disable_tqdm=disable_tqdm,
#     )


# def run_local_dimension_from_sources(
#     graph, times, sources, use_spectral_gap=True, n_workers=1, disable_tqdm=False
# ):
#     """computing the local dimensionality of each source"""
#     relative_dimensions, peak_times = run_several_sources(
#         graph,
#         times,
#         sources,
#         use_spectral_gap,
#         n_workers,
#         disable_tqdm=disable_tqdm,
#     )

#     local_dimensions = []
#     for time_horizon in times:
#         relative_dimensions_reduced = relative_dimensions.copy()
#         relative_dimensions_reduced[peak_times > time_horizon] = np.nan
#         local_dimensions.append(np.nanmean(relative_dimensions_reduced, axis=1))

#     return np.array(local_dimensions)


# def compute_global_dimension(local_dimensions):
#     """Computing the global dimensiona of the graph"""
#     return local_dimensions.mean(1)


def construct_laplacian(graph, laplacian_tpe="normalized", use_spectral_gap=True, directed=False):
    """construct the Laplacian matrix"""
    if laplacian_tpe == "normalized":
        if directed:
            degrees = np.array([graph.out_degree(i, weight="weight") for i in graph.nodes], dtype = float)
            laplacian = diags(1.0 / degrees).dot(nx.directed_laplacian_matrix(graph))
        else:
            degrees = np.array([graph.degree(i, weight="weight") for i in graph.nodes], dtype = float)
            laplacian = diags(1.0 / degrees).dot(nx.laplacian_matrix(graph))
    else:
        raise Exception(
            "Any other laplacian type than normalized are not implemented as they will not work"
        )

    if use_spectral_gap:
        spectral_gap = abs(eigs(laplacian, which="SM", k=2)[0][1])
        # laplacian /= spectral_gap
    else:
        spectral_gap = 1.0

    return laplacian, spectral_gap

import os

def heat_kernel(laplacian, timestep, measure):
    """compute matrix exponential on a measure"""
    # return expm(-timestep * laplacian).dot(measure)
    np.set_printoptions(threshold=np.inf)
    fp=open('/home/tongsu/DynGDim/pyGOD_builtin_datasets/data','a+')
    print(laplacian.data, file=fp)
    print(laplacian.indices, file=fp)
    print(laplacian.indptr, file=fp)
    # print(laplacian.toarray(), file=fp)
    while(1):
        timestep *= 0.1
        print("ok")
    return expm_multiply(-timestep * laplacian, measure)


def compute_node_trajectories(laplacian, initial_measure, times, disable_tqdm=False):
    """compute node trajectories from diffusion dynamics"""
    node_trajectories = [
        heat_kernel(laplacian, times[0], initial_measure),
    ]
    for i in tqdm(range(len(times) - 1), disable=disable_tqdm):
        node_trajectories.append(
            heat_kernel(laplacian, times[i + 1] - times[i], node_trajectories[-1])
        )
    return np.array(node_trajectories)


def extract_relative_dimensions(times, node_trajectories, initial_measure, spectral_gap):
    """compute the relative dimensions from node trajectories."""
    # set the diffusion coefficient
    diffusion_coefficient = 0.5 / spectral_gap

    # uniform stationary state as we do consensus
    stationary_prob = 1 / node_trajectories.shape[1]

    # find the peaks
    peak_amplitudes = np.max(node_trajectories, axis=0)
    peak_pos = np.argmax(node_trajectories, axis=0)
    missed_peaks = np.where(peak_pos[initial_measure == 0] == 0)[0]
    # if len(missed_peaks) > 0:
    #     warnings.warn(
    #         """Please reduce the minimum time because some peaks are not detected
    #                   We will consider them as unreachable."""
    #     )

    peak_times = times[peak_pos]

    # remove unreachable nodes
    peak_times[peak_amplitudes < stationary_prob + PRECISION] = np.nan
    peak_amplitudes[peak_amplitudes < stationary_prob + PRECISION] = np.nan

    # remove missed peaks
    peak_times[missed_peaks] = np.nan
    peak_amplitudes[missed_peaks] = np.nan

    # remove initial measure
    peak_times[initial_measure > 0] = np.nan
    peak_amplitudes[initial_measure > 0] = np.nan

    # compute the effective dimension
    relative_dimensions = (
        -2.0
        * np.log(peak_amplitudes)
        / (1.0 + np.log(peak_times) + np.log(4.0 * diffusion_coefficient * np.pi))
    )

    # set un-defined dimensions to nan
    relative_dimensions[np.isnan(relative_dimensions)] = np.nan

    with np.errstate(invalid="ignore"):
        relative_dimensions[relative_dimensions < 0] = np.nan

    return relative_dimensions, peak_times, peak_amplitudes, diffusion_coefficient


def get_initial_measure(graph, nodes, total_degree, directed=False):
    """create an measure with the correct mass from a list of nodes"""
    measure = np.zeros(len(graph))
    if directed:
        for node in nodes:
            d = graph.out_degree(node, weight="weight")
            measure[node] = total_degree / (len(graph) * d) / len(nodes)
    else:
        for node in nodes:
            d = graph.degree(node, weight="weight")
            measure[node] = total_degree / (len(graph) * d) / len(nodes)
    return measure
