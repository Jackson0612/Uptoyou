"""D63's evaluation rounds: the fixed test set, and the tools that run candidates over it.

The method is the reference repository's, constrained (D63): every round the same labeled
set, the same fixed metrics, each round a public commit plus one evaluation page. What
lives here is code; the set itself is data, committed under `app/api/evaluation/`, and the
labels in it are ruled by a person — never by any candidate model.
"""
