# MarmoMind: AI Agent designed by Azadeh Jafari (jfr.azadeh@gmail.com) for the
# Everling Lab, Centre for Functional and Metabolic Mapping, University of
# Western Ontario. Created May 2026.
"""MarmoMind custom in-process tools (deterministic Python).

Each module defines a plain helper (testable directly) plus a thin @tool wrapper.
Tools register via create_sdk_mcp_server(name="marmomind", tools=[...]) and are
exposed to the agent as  mcp__marmomind__<tool_name>.

Division of labor: these tools do the MECHANICAL work (parse, look up, convert,
measure, move). The agent does the JUDGMENT (sort + verdict). No tool ever hands
the agent a brain image.
"""

TOOL_MODULES = [
    "detect",      # detect_ready_run
    "dicom",       # parse_dicom_filenames
    "notes",       # read_note
    "regressors",  # check_regressor_files
    "sheets",      # lookup_monkey_id, get_next_session_number, append_run_rows
    "convert",     # convert_and_rename_run
    "motion",      # motion_check
    "filing",      # file_run_into_folder
]
