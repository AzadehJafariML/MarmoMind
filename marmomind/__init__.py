# MarmoMind: AI Agent designed by Azadeh Jafari (jfr.azadeh@gmail.com) for the
# Everling Lab, Centre for Functional and Metabolic Mapping, University of
# Western Ontario. Created May 2026.
"""MarmoMind — a human-in-the-loop fMRI processing agent for awake, head-fixed
marmoset imaging.

The agent processes a BACKLOG of accumulated scanner sessions (experimenters may
upload only every 2-3 sessions), one session at a time, in chronological order.
For each run it logs-and-converts first, then judges quality. It RECOMMENDS and
SORTS; the human decides.
"""

__version__ = "0.1.0"
