"""
DeerFlow-style deep research, natively inside Mark LV.

DeerFlow 2.0 (bytedance/deer-flow) is a LangGraph harness — a lead agent, a
sub-agent runtime, a skills format, a sandbox, an MCP gateway and a Next.js
console. Shipping that stack here would mean putting Node, Docker and a second
control plane next to a single-process voice assistant. What is worth taking is
the loop that made it useful, and that is what this package is:

    plan     the topic becomes sub-questions with search queries
    research several readers work in parallel, on real pages, not snippets
    analyse  notes are reconciled — contradictions, gaps, confidence
    critique the claims are checked against the sources they cite
    write    a Markdown report where every claim carries its source

Nothing here imports Qt, nothing touches the network at import time, and the
only dependencies are the ones the app already installs (requests,
beautifulsoup4, ddgs). That keeps action discovery cheap: `actions/` is scanned
on every launch, so a module that opens sockets at import would tax a boot the
user did not ask to pay for.

The model ladder is `core/gemini.py` — this package never names a model. The
output directory, the parallel width and the language are settings in
`config/api_keys.json` (see research/config.py).
"""
