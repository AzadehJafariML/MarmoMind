# MarmoMind : An Agentic AI designed and built by Azadeh Jafari (jfr.azadeh@gmail.com).
# Created May 2026. Developed during my Ph.D. research in computational neuroscience.
# See README for the published protocol this work builds on.
"""MarmoMind — a human-in-the-loop fMRI processing agent for awake, head-fixed
marmoset imaging.

The agent processes a BACKLOG of accumulated scanner sessions (experimenters may
upload only every 2-3 sessions), one session at a time, in chronological order.
For each run it logs-and-converts first, then judges quality. It RECOMMENDS and
SORTS; the human decides.
"""

__version__ = "0.1.0"
