#! /usr/bin/env python3
# -*- coding: utf-8; mode: python -*-
""" Experimental code to perform complete tree exploration for Multi-Player bandits.

- Can use exact formal computations with sympy, or fractions with Fraction, or float number.
- Support Selfish 0-greedy, UCB, and klUCB in 3 differents variants.
- Support export of the tree to a GraphViz dot graph, and can save it to SVG/PNG/PDF etc.
- TODO : add rhoRand, TopBestM etc.
- TODO : implement a parallel loop for what can be parallel.

Requirements:

- 'sympy', 'numpy' and 'graphviz' are required.

About:

- *Date:* 16/09/2017.
- *Author:* Lilian Besson, (C) 2017
- *Licence:* MIT Licence (http://lbesson.mit-license.org).
"""

from __future__ import print_function, division  # Python 2 compatibility if needed
__author__ = "Lilian Besson"
__version__ = "0.2"

import re
from collections import Counter
from collections import deque
from fractions import Fraction
from itertools import product
from textwrap import wrap

try:
    import numpy as np
except ImportError as e:
    print("Warning: the 'numpy' module was not found...\nInstall it with 'sudo pip2/pip3 install numpy'")  # XXX
    raise e
try:
    import sympy
except ImportError:
    print("Warning: the 'sympy' module was not found...\nInstall it with 'sudo pip2/pip3 install sympy'")  # XXX
try:
    from graphviz import Digraph
except ImportError:
    print("Warning: the 'graphviz' module was not found...\nInstall it with 'sudo pip2/pip3 install graphviz'")  # XXX

oo = float('+inf')  #: Shortcut for float('+inf').


def tupleit1(anarray):
    """Convert a non-hashable 1D numpy array to a hashable tuple."""
    return tuple(anarray.tolist())

def tupleit2(anarray):
    """Convert a non-hashable 2D numpy array to a hashable tuple-of-tuples."""
    return tuple([tuple(r) for r in anarray.tolist()])

def prod(iterator):
    """Product of the values in this iterator."""
    p = 1
    for v in iterator:
        p *= v
    return p

def choices_from_indexes(indexes):
    """For deterministic index policies, if more than one index is maximum, return the list of positions attaining this maximum (ties), or only one position."""
    return np.where(indexes == np.max(indexes))[0]


def simplify(proba):
    """Try to simplify the expression of the probability."""
    if hasattr(proba, "simplify"):
        return proba.simplify()
    else:
        return proba

def proba2str(proba, html_in_var_names=False):
    """Pretty print a proba, either a number, a Fraction, or a sympy expression."""
    if isinstance(proba, float):
        str_proba = '{:.3g}'.format(proba)
    elif isinstance(proba, Fraction):
        str_proba = str(proba)
    else:  # a bit of str rewriting
        str_proba = str(simplify(proba))
        if html_in_var_names:
            str_proba = re.sub(r'\*\*([0-9]+)', r'<SUP>\1</SUP>', str_proba)
        else:
            str_proba = str_proba.replace('**', '^')
        str_proba = str_proba.replace('*', '')
        str_proba = re.sub(r'-mu_([0-9]+) \+ 1', r'1-mu_\1', str_proba)
        if html_in_var_names:  # replace mu_12 by mu<sub>12</sub>
            str_proba = re.sub(r'mu_([0-9]+)', r'mu<SUB>\1</SUB>', str_proba)
        else:
            str_proba = re.sub(r'mu_', r'µ', str_proba)
    return str_proba

WIDTH = 100  #: Default value for the ``width`` parameter for :func:`wraptext` and :func:`wraplatex`.

def wraptext(text, width=WIDTH):
    """ Wrap the text, using ``textwrap`` module, and ``width``."""
    return '\n'.join(wrap(text, width=width))

ONLYLEAFS = True  #: By default, aim at the most concise graph representation by only showing the leafs
ONLYABSORBING = False  #: By default, don't aim at the most concise graph representation by only showing the absorbing leafs

# --- Implement the bandit algorithms in a purely functional and memory-less flavor

def FixedArm(j, state):
    """Fake player j that always targets at arm j."""
    return [j]

def UniformExploration(j, state):
    """Fake player j that always targets all arms."""
    return np.arange(state.K)

# --- Selfish 0-greedy variants

def Selfish_0Greedy_U(j, state):
    """Selfish policy + 0-Greedy index + U feedback."""
    indexes = state.S[j] / state.N[j]
    indexes[state.N[j] < 1] = +oo
    return choices_from_indexes(indexes)

def Selfish_0Greedy_Utilde(j, state):
    """Selfish policy + 0-Greedy index + Utilde feedback."""
    indexes = state.Stilde[j] / state.N[j]
    indexes[state.N[j] < 1] = +oo
    return choices_from_indexes(indexes)

def Selfish_0Greedy_Ubar(j, state):
    """Selfish policy + 0-Greedy index + Ubar feedback."""
    indexes = (state.Ntilde[j] / state.N[j]) * (state.S[j] / state.N[j])
    indexes[state.N[j] < 1] = +oo
    return choices_from_indexes(indexes)

default_policy = Selfish_0Greedy_Ubar


# --- Selfish UCB variants
alpha = 0.5

def Selfish_UCB_U(j, state):
    """Selfish policy + UCB_0.5 index + U feedback."""
    indexes = (state[j].S / state.N[j]) + np.sqrt(alpha * np.log(state.t) / state.N[j])
    indexes[state.N[j] < 1] = +oo
    return choices_from_indexes(indexes)

def Selfish_UCB_Utilde(j, state):
    """Selfish policy + UCB_0.5 index + Utilde feedback."""
    indexes = (state.Stilde[j] / state.N[j]) + np.sqrt(alpha * np.log(state.t) / state.N[j])
    indexes[state.N[j] < 1] = +oo
    return choices_from_indexes(indexes)

def Selfish_UCB_Ubar(j, state):
    """Selfish policy + UCB_0.5 index + Ubar feedback."""
    indexes = (state.Ntilde[j] / state.N[j]) * (state.S[j] / state.N[j]) + np.sqrt(alpha * np.log(state.t) / state.N[j])
    indexes[state.N[j] < 1] = +oo
    return choices_from_indexes(indexes)

# default_policy = Selfish_UCB_Ubar

# --- Selfish kl UCB variants

from Policies import klucbBern
tolerance = 1e-6
klucb = np.vectorize(klucbBern)
c = 1

def Selfish_KLUCB_U(j, state):
    """Selfish policy + Bernoulli KL-UCB index + U feedback."""
    indexes = klucb(state.S[j] / state.N[j], c * np.log(state.t) / state.N[j], tolerance)
    indexes[state.N[j] < 1] = +oo
    return choices_from_indexes(indexes)

def Selfish_KLUCB_Utilde(j, state):
    """Selfish policy + Bernoulli KL-UCB index + Utilde feedback."""
    indexes = klucb(state.Stilde[j] / state.N[j], c * np.log(state.t) / state.N[j], tolerance)
    indexes[state.N[j] < 1] = +oo
    return choices_from_indexes(indexes)

def Selfish_KLUCB_Ubar(j, state):
    """Selfish policy + Bernoulli KL-UCB index + Ubar feedback."""
    indexes = klucb((state.Ntilde[j] / state.N[j]) * (state.S[j] / state.N[j]), c * np.log(state.t) / state.N[j], tolerance)
    indexes[state.N[j] < 1] = +oo
    return choices_from_indexes(indexes)

# default_policy = Selfish_KLUCB_Ubar

# --- FIXME write rhoRand, TopBestM, MusicalChair and all variants !
# XXX It is probably harder... rhoRand is NOT memory less!!
# XXX TopBestM and MusicalChair also!!


# --- Generate vector of formal means mu_1,...,mu_K

def symbol_means(K):
    """Better to work directly with symbols and instantiate the results *after*."""
    return sympy.var(['mu_{}'.format(i) for i in range(1, K + 1)], real=True)

def random_uniform_means(K):
    """If needed, generate an array of K (numerical) uniform means in [0, 1]."""
    return np.random.rand(K)


# --- Data representation'

class State(object):
    """Not space-efficient representation of a state in the system we model.

    - S, Stilde, N, Ntilde: are arrays of size (M, K),
    - depth, t, M, K: integers, to avoid recomputing them,
    - mus: the problem parameters (only for Bernoulli arms),
    - players: is a list of algorithms,
    - probas: list of transition probabilities,
    - children: list of all possible next states (transitions).
    """

    def __init__(self, S, Stilde, N, Ntilde, mus, players, depth=0):
        """Create a new state. Arrays S, Stilde, N, Ntilde are *copied* to avoid modify previous values!"""
        self.S = np.copy(S)  #: sensing feedback
        self.Stilde = np.copy(Stilde)  #: number of sensing trials
        self.N = np.copy(N)  #: number of succesful transmissions
        self.Ntilde = np.copy(Ntilde)  #: number of trials without collisions
        self.mus = mus  # XXX OK memory efficient: only a pointer to the (never modified) list
        self.players = players  # XXX OK memory efficient: only a pointer to the (never modified) list
        # New arguments
        self.depth = depth  #: current depth of the exploration tree
        self.t = np.sum(N)  #: current time step. Simply = sum(N) but easier to compute it
        assert np.shape(S) == np.shape(Stilde) == np.shape(N) == np.shape(Ntilde), "Error: difference in shapes of S, Stilde, N, Ntilde."
        self.M = min(np.shape(S))  #: number of players
        assert len(players) == self.M, "Error: 'players' list is not of size M ..."  # DEBUG
        self.K = max(np.shape(S))  #: number of arms (channels)
        assert len(mus) == self.K, "Error: 'mus' list is not of size K ..."  # DEBUG
        self.children = []  #: list of next state, representing all the possible transitions
        self.probas = []  #: probabilities of transitions

    # --- Utility

    def __str__(self):
        return "    State : M = {}, K = {} and t = {}, depth = {}.\n{} =: S\n{} =: Stilde\n{} =: N\n{} =: Ntilde\n".format(self.M, self.K, self.t, self.depth, self.S, self.Stilde, self.N, self.Ntilde)

    def _to_node(self, concise=True):
        """Print the state as a small string to be attached to a GraphViz node."""
        if concise:
            return "[[" + "], [".join(",".join("{:.3g}/{}".format(st, n) for st, n in zip(st2, n2)) for st2, n2 in zip(self.Stilde, self.N)) + "]]"
        else:
            return "[[" + "], [".join(",".join("{:.3g}:{:.3g}/{}:{}".format(s, st, n, nt) for s, st, n, nt in zip(s2, st2, n2, nt2)) for s2, st2, n2, nt2 in zip(self.S, self.Stilde, self.N, self.Ntilde)) + "]]"

    def to_dot(self,
               title="", name="", comment="",
               html_in_var_names=False, onlyleafs=ONLYLEAFS, onlyabsorbing=ONLYABSORBING):
        """Convert the state to a .dot graph, using GraphViz. See http://graphviz.readthedocs.io/ for more details.

        - onlyleafs: only print the root and the leafs, to see a concise representation of the tree.
        - onlyabsorbing: only print the absorbing leafs, to see a really concise representation of the tree.
        """
        print("Creating a dot graph from the state...")
        dot = Digraph(name=name, comment=comment, format="svg")
        dot.attr(overlap="false")
        if title: dot.attr(label=wraptext(title))
        node_number = 0
        if onlyleafs:
            root_name, root = "0", self
            dot.node(root_name, root._to_node(), color="green")
            complete_probas, leafs = root.get_unique_leafs()
            for proba, leaf in zip(complete_probas, leafs):
                # add a UNIQUE identifier for each node: easy, just do a breath-first search, and use numbers from 0 to big-integer-that-is-computed on the fly
                node_number += 1
                leaf_name = str(node_number)
                if leaf.is_absorbing():
                    dot.node(leaf_name, leaf._to_node(), color="red")
                    dot.edge(root_name, leaf_name, label=proba2str(proba, html_in_var_names=html_in_var_names))
                elif not onlyabsorbing:
                    dot.node(leaf_name, leaf._to_node())
                    dot.edge(root_name, leaf_name, label=proba2str(proba, html_in_var_names=html_in_var_names))
        else:
            to_explore = deque([("0", self)])  # BFS using a deque, DFS using a list/recursive call
            # convert each state to a node and a list of edge
            while len(to_explore) > 0:
                root_name, root = to_explore.popleft()
                if root_name == "0":
                    dot.node(root_name, root._to_node(), color="green")
                elif root.is_absorbing():
                    dot.node(root_name, root._to_node(), color="red")
                else:
                    dot.node(root_name, root._to_node())
                for proba, child in zip(root.probas, root.children):
                    # add a UNIQUE identifier for each node: easy, just do a breath-first search, and use numbers from 0 to big-integer-that-is-computed on the fly
                    node_number += 1
                    child_name = str(node_number)
                    dot.edge(root_name, child_name, label=proba2str(proba, html_in_var_names=html_in_var_names))
                    to_explore.append((child_name, child))
        return dot

    def saveto(self, filename, view=True, title="", name="", comment=""):
        dot = self.to_dot(title=title, name=name, comment=comment)
        print("Saving the dot graph to '{}.svg'...".format(filename))
        dot.render(filename, view=view)

    def copy(self):
        """Get a new copy of that state with same S, Stilde, N, Ntilde but no probas and no children (and depth=0)."""
        return State(S=self.S, Stilde=self.Stilde, N=self.N, Ntilde=self.Ntilde, mus=self.mus, players=self.players, depth=self.depth)

    def __hash__(self, full=False):
        """Hash the matrix Stilde and N of the state."""
        if full:
            return hash(tupleit2(self.S) + tupleit2(self.N) + tupleit2(self.Stilde) + tupleit2(self.Ntilde) + (self.t, self.depth, ))
        else:
            return hash(tupleit2(self.Stilde) + tupleit2(self.N))

    def is_absorbing(self):
        """Try to detect if this state is absorbing, ie only one transition is possible, and again infinitely for the only child.

        .. warning:: Still very experimental!
        """
        # FIXME still not sure about the characterization of absorbing states
        # if at least two players have the same S, Stilde, N, Ntilde lines
        if np.min(self.N) < 1:
            return False
        for j1 in range(self.M):
            for j2 in range(j1 + 1, self.M):
                A = [self.S, self.Stilde, self.N, self.Ntilde]
                are_all_equal = [ tupleit1(a[j1]) == tupleit1(a[j2]) for a in A ]
                if all(are_all_equal):
                    # bad_line = add([tupleit1(a[j1]) for a in A])
                    # bad_line = tupleit1(self.S[j1])
                    bad_line = tupleit1(self.Stilde[j1])
                    # and if that line has only different values
                    if len(set(bad_line)) == len(bad_line):
                        return True
        return False

    # --- High level view of a depth-1 exploration

    def explore_from_node_to_depth(self, depth=1):
        """Compute recursively the one_depth children of the root and its children."""
        print("\nFor depth = {}, exploring from this node :\n{}".format(depth, self))
        if depth == 0:
            return
        self.compute_one_depth()
        self.depth = depth
        if depth > 1:
            for child in self.children:
                child.explore_from_node_to_depth(depth=depth-1)

    def compute_one_depth(self):
        """Use all_deltas to store all the possible transitions and their probabilities. Increase depth by 1 at the end."""
        self.depth += 1
        uniq_children = dict()
        uniq_probas = dict()
        nb_transitions = 0
        for delta, proba in self.all_deltas():
            nb_transitions += 1
            # copy the current state, apply decision of algorithms and random branching
            child = delta(self.copy())
            h = hash(child)  # I guess I could use states directly as key, but this would cost more in terms of memory
            if h in uniq_children:
                uniq_probas[h] += proba
            else:
                assert child.depth == (self.depth - 1)
                uniq_children[h] = child
                uniq_probas[h] = proba
        # print("  we saw {} possible transitions...".format(nb_transitions))
        print("  we saw {} different states...".format(len(uniq_children)))
        self.probas = [simplify(p) for p in uniq_probas.values()]
        self.children = list(uniq_children.values())
        # Done for computing all the children and probability of transitions

    # --- The hard part is this all_deltas *generator*

    def all_deltas(self):
        """Generator that yield lambda functions transforming state to another state."""
        all_decisions = [ player(j, self) for j, player in enumerate(self.players) ]
        number_of_decisions = prod(len(decision) for decision in all_decisions)
        for decisions in product(*all_decisions):
            for coin_flips in product([0, 1], repeat=self.K):
                proba_of_this_coin_flip = prod(mu if b else (1 - mu) for b, mu in zip(coin_flips, self.mus))
                # Create a function to apply this transition
                def delta(s):
                    s.t += 1
                    s.depth -= 1
                    # collisions = [np.count_nonzero(np.array(decisions) == k) >= 2 for k in range(self.K)]
                    counter = Counter(decisions)
                    collisions = [counter.get(k, 0) >= 2 for k in range(self.K)]  # XXX faster with Counter
                    for j, Ij, b in zip(range(self.M), decisions, coin_flips):
                        s.S[j, Ij] += b  # sensing feedback
                        s.N[j, Ij] += 1  # number of sensing trials
                        if not collisions[Ij]:  # no collision, receive this feedback for rewards
                            s.Stilde[j, Ij] += b  # number of succesful transmissions
                            s.Ntilde[j, Ij] += 1  # number of trials without collisions
                    return s
                # Compute the probability of this transition
                proba = proba_of_this_coin_flip / number_of_decisions
                yield (delta, proba)

    # --- Main functions, all explorations are depth first search (not the best, it's just easier...)

    def pretty_print_result_recursively(self):
        """Print all the transitions, depth by depth (recursively)."""
        if self.is_absorbing():
            print("\n\n")
            print("X "*87)
            print("The state:\n{}\nseems to be absorbing...".format(self))
            print("X "*87)
            # return
        if self.depth > 0:
            print("\n\nFrom this state :\n{}".format(self))
            for (proba, child) in zip(self.probas, self.children):
                print("\n- Probability of transition = {} to this other state:\n{}".format(proba, child))
                child.pretty_print_result_recursively()
            print("\n==> Done for the {} children of this state...\n".format(len(self.children)))

    def get_all_leafs(self):
        """Recurse and get all the leafs. Many different state can be present in the list of leafs, with possibly different probabilities (each correspond to a trajectory)."""
        if self.depth <= 1:
            return self.probas, self.children
        else:
            complete_probas, leafs = [], []
            assert len(self.probas) > 0
            for (proba, child) in zip(self.probas, self.children):
                # assert child.depth == (self.depth - 1)
                c, l = child.get_all_leafs()
                # assert all([s.depth == 0 for s in l])
                c = [proba * p for p in c]  # one more step, multiply but a proba
                complete_probas.extend(c)
                leafs.extend(l)
            return complete_probas, leafs

    def get_unique_leafs(self):
        """Compute all the leafs (deepest children) and merge the common one to compute their full probabilities."""
        uniq_complete_probas = dict()
        uniq_leafs = dict()
        complete_probas, leafs = self.get_all_leafs()
        for proba, leaf in zip(complete_probas, leafs):
            h = hash(leaf)
            if h in uniq_leafs:
                uniq_complete_probas[h] += proba
            else:
                uniq_complete_probas[h] = proba
                uniq_leafs[h] = leaf
        return [simplify(p) for p in uniq_complete_probas.values()], list(uniq_leafs.values())


# --- Main function

def main(depth=1, players=None, mus=None, M=2, K=2, S=None, Stilde=None, N=None, Ntilde=None):
    """Compute all the transitions, and print them."""
    if S is not None:
        M = min(np.shape(S))
        K = max(np.shape(S))
    if mus is None:
        mus = symbol_means(K=K)
    K = len(mus)
    if players is None:
        players = [default_policy for _ in range(M)]
    M = len(players)
    assert 1 <= M <= K <= 10, "Error: only 1 <= M <= K <= 10 are supported... and M = {}, K = {} here...".format(M, K)  # FIXME
    assert 0 <= depth <= 8, "Error: only 0 <= depth <= 8 is supported... and depth = {} here...".format(depth)  # FIXME
    # Compute starting state
    if S is None:
        S = np.zeros((M, K))
    if Stilde is None:
        Stilde = np.zeros((M, K))
    if N is None:
        N = np.zeros((M, K), dtype=int)
    if Ntilde is None:
        Ntilde = np.zeros((M, K),  dtype=int)
    # Create the root state
    root = State(S=S, Stilde=Stilde, N=N, Ntilde=Ntilde, mus=mus, players=players)
    print("\nStarting to explore every transitions up-to depth {} for this root state:\n{}".format(depth, root))
    print("    Using these policies:")
    for playerId, player in enumerate(players):
        print("  - Player #{}/{} uses {} (which is {})...".format(playerId, M, player.__name__, player))
    print("    Using these arms:")
    for muId, mu in enumerate(mus):
        print("  - Arm #{}/{} has mean {} ...".format(muId, K, mu))
    # Explore from the root
    root.explore_from_node_to_depth(depth=depth)
    # Print everything
    # root.pretty_print_result_recursively()
    # Get all leafs
    complete_probas, leafs = root.get_unique_leafs()
    print("\n\n\nThere are {} unique leafs for depth {}...".format(len(leafs), depth))
    for proba, leaf in zip(complete_probas, leafs):
        print("\n Leaf with probability = {}:\n{}".format(proba, leaf))
        if leaf.is_absorbing():
            print("  At depth {}, this leaf was found to be absorbing !".format(depth))

    # Done
    print("\nDone for exploring every transitions up-to depth {} for this root state:\n{}".format(depth, root))
    print("    Using these policies:")
    for playerId, player in enumerate(players):
        print("  - Player #{}/{} uses {} (which is {})...".format(playerId, M, player.__name__, player))
    print("    Using these arms:")
    for muId, mu in enumerate(mus):
        print("  - Arm #{}/{} has mean {} ...".format(muId, K, mu))
    print("\nThere were {} unique leafs for depth {}...".format(len(leafs), depth))
    return root, complete_probas, leafs


# --- Main script

def test(depth=1, M=2, K=2, S=None, Stilde=None, N=None, Ntilde=None, mus=None, debug=True):
    """Test the main exploration function for various policies."""
    results = []
    # for policy in [FixedArm]:  # FIXME just for testing
    # for policy in [UniformExploration]:  # FIXME just for testing
    # for policy in [Selfish_0Greedy_Ubar, Selfish_UCB_Ubar, Selfish_KLUCB_Ubar]:
    for policy in [Selfish_UCB_Ubar]:
        players = [ policy for _ in range(M) ]
        root, complete_probas, leafs = main(depth=depth, players=players, S=S, N=N, Stilde=Stilde, Ntilde=Ntilde, M=M, K=K, mus=mus)
        results.append([root, complete_probas, leafs])
        if debug:
            root.saveto('/tmp/test', view=True, title="Tree exploration for K={} arms and M={} players using {}, for depth={}".format(K, M, policy.__name__, depth))
            print(input("\n\n[Enter] to continue..."))
    return results


if __name__ == '__main__':
    mus = None
    depth = 1

    # # XXX default start state
    # M, K = 1, 1
    # for depth in [8]:
    #     print("For depth = {} ...".format(depth))
    #     results = test(depth=depth, M=M, K=K, mus=mus)

    # # XXX default start state
    # M, K = 2, 2
    # # mus = [0.8, 0.2]
    # # mus = [Fraction(4, 5), Fraction(1, 5)]
    # for depth in [1, 2, 3]:
    #     print("For depth = {} ...".format(depth))
    #     results = test(depth=depth, M=M, K=K, mus=mus)

    # XXX What if we start from an absorbing state?
    M, K = 2, 2
    S = np.array([[1, 0], [1, 0]])
    Stilde = np.array([[1, 0], [1, 0]])
    N = np.array([[2, 1], [2, 1]])
    Ntilde = np.array([[2, 1], [2, 1]])
    for depth in [1, 2, 3]:
        results = test(depth=depth, M=M, K=K, S=S, Stilde=Stilde, N=N, Ntilde=Ntilde, mus=mus)

    # # XXX default start state
    # M, K = 2, 3
    # results = test(depth=depth, M=M, K=K, mus=mus)

    # # XXX What if we start from an absorbing state?
    # M, K = 2, 3
    # # S = np.array([[2, 1, 0], [2, 1, 0]])
    # # Stilde = np.array([[2, 1, 0], [2, 1, 0]])
    # # N = np.array([[4, 3, 1], [4, 3, 1]])
    # # Ntilde = np.array([[4, 3, 1], [4, 3, 1]])
    # # for depth in [1]:
    # for depth in [2, 3]:
    #     results = test(depth=depth, M=M, K=K, mus=mus)
    #     # results = test(depth=depth, M=M, K=K, S=S, Stilde=Stilde, N=N, Ntilde=Ntilde, mus=mus)

    # M, K = 3, 3
    # results = test(depth=depth, M=M, K=K, mus=mus)

# End of complete-tree-exploration-for-MP-bandits.py