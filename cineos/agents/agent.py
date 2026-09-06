import os
from datetime import date, timedelta

from dotenv import load_dotenv

from google.adk.agents import Agent, SequentialAgent
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import (
    StreamableHTTPConnectionParams,
)

from agents.tools.production import (
    get_demo_date,
    get_scene,
    get_actor_availability,
    get_location_schedule,
    validate_swap_candidate,
    estimate_schedule_impact,
    estimate_budget_impact,
)


# ============================================================
# ENVIRONMENT / DETERMINISTIC DEMO CLOCK
# ============================================================

load_dotenv()

DEMO_DATE_INFO = get_demo_date()
# get_demo_date() returns the deterministic demo clock information.
# Use the returned "today" value rather than expecting a "demo_date" key.
DEMO_TODAY = date.fromisoformat(DEMO_DATE_INFO["today"])
DEMO_TOMORROW = DEMO_TODAY + timedelta(days=1)

TODAY_STR = DEMO_TODAY.isoformat()
TOMORROW_STR = DEMO_TOMORROW.isoformat()


# ============================================================
# OPTIONAL GRAFANA MCP
# ============================================================
#
# Grafana runs separately on:
#
#     http://localhost:8000/mcp
#
# ADK runs separately on:
#
#     http://127.0.0.1:8080
#
# The MCP server is optional from the decision perspective.
# Never fabricate Grafana evidence if it cannot be queried.
# ============================================================

grafana_tools = []

grafana_url = os.getenv("GRAFANA_MCP_URL", "").strip()

# Support both names so the existing .env works while retaining
# compatibility with the MCP-specific variable.
grafana_token = (
    os.getenv("GRAFANA_MCP_TOKEN", "").strip()
    or os.getenv("GRAFANA_SERVICE_ACCOUNT_TOKEN", "").strip()
)

if grafana_url:
    grafana_headers = {}

    if grafana_token:
        grafana_headers["Authorization"] = f"Bearer {grafana_token}"

    grafana_tools.append(
        McpToolset(
            connection_params=StreamableHTTPConnectionParams(
                url=grafana_url,
                headers=grafana_headers,
                timeout=30,
                sse_read_timeout=60,
            ),
        )
    )


# ============================================================
# 1. INCIDENT INTAKE AGENT
# ============================================================

incident_intake_agent = Agent(
    model="gemini-2.5-flash",
    name="incident_intake_agent",
    description=(
        "Extracts the production incident, affected actor, "
        "affected scene, incident date, recovery date, "
        "known facts and unknowns."
    ),
    instruction=f"""
You are the CineOS Incident Intake Agent.

============================================================
DEMO CLOCK
============================================================

Today:
{TODAY_STR}

Tomorrow:
{TOMORROW_STR}

This CineOS demo uses a deterministic production calendar.

If the user says "tomorrow", it means exactly:

{TOMORROW_STR}

Never substitute the computer's actual calendar date.

============================================================
TASK
============================================================

Extract the production incident from the user's request.

Return:

INCIDENT BRIEF

- Today:
- Tomorrow:
- Affected actor:
- Affected scene:
- Incident:
- Incident date:
- Requested recovery date:
- Known facts:
- Unknowns:

============================================================
STRICT RULES
============================================================

Do NOT invent:

- reason for the actor's absence;
- duration of the absence;
- future actor availability;
- replacement actors;
- recovery dates not supported by the request;
- schedule values;
- budget values;
- Grafana evidence.

If the user says "tomorrow", use:

{TOMORROW_STR}

Keep this short and factual.

Do not recommend a recovery plan.
""",
    output_key="incident_brief",
)


# ============================================================
# 2. SCRIPT INTELLIGENCE AGENT
# ============================================================

script_intelligence_agent = Agent(
    model="gemini-2.5-flash",
    name="script_intelligence_agent",
    description=(
        "Retrieves verified screenplay and production information "
        "for the affected scene without making recovery decisions."
    ),
    instruction=f"""
You are the CineOS Script Intelligence Agent.

============================================================
DEMO CLOCK
============================================================

Today:
{TODAY_STR}

Tomorrow:
{TOMORROW_STR}

============================================================
INPUT
============================================================

Incident brief:

{{incident_brief}}

============================================================
TASK
============================================================

Use ONLY the get_scene tool to inspect the affected scene.

Retrieve and report verified information:

- Scene ID
- Scene title
- Characters
- Location
- Duration
- Equipment
- Dependencies
- Scheduled production day

Determine whether the unavailable actor is required by the
affected scene using the returned scene data.

============================================================
CRITICAL BOUNDARY
============================================================

Your job is SCRIPT INTELLIGENCE ONLY.

You MUST NOT:

- recommend rescheduling;
- recommend swapping;
- recommend rewriting;
- select Scene 47;
- select another replacement scene;
- make a budget decision;
- make the final recovery decision.

Do not say:

"Safest plan is..."
"Recommended plan is..."
"Scene 42 should be postponed..."
"Scene 42 should be swapped..."

Those decisions belong to later agents.

============================================================
FACT SAFETY
============================================================

get_scene is the authoritative source for scene information.

Do NOT invent:

- script constraints;
- actors;
- locations;
- equipment;
- dependencies;
- durations.

Clearly distinguish verified information from unknowns.

============================================================
OUTPUT
============================================================

Return:

SCRIPT ANALYSIS

Affected Scene:
- ID:
- Title:
- Characters:
- Location:
- Duration:
- Equipment:
- Dependencies:
- Scheduled production day:
- Unavailable actor required:

Script Constraints:
- verified facts only

Unknowns:
- genuinely unresolved information

Keep the result compact.
""",
    tools=[
        get_scene,
    ],
    output_key="script_analysis",
)


# ============================================================
# 3. SCHEDULE AGENT
# ============================================================

schedule_agent = Agent(
    model="gemini-2.5-flash",
    name="schedule_agent",
    description=(
        "Validates production availability and the fixed "
        "Scene 42 -> Scene 47 recovery candidate."
    ),
    instruction=f"""
You are the CineOS Schedule Validation Agent.

============================================================
DEMO CLOCK
============================================================

Today:
{TODAY_STR}

Affected shoot date:
{TOMORROW_STR}

When the incident says "tomorrow", use:

{TOMORROW_STR}

Never substitute the computer's actual date.

============================================================
INPUTS
============================================================

Incident:

{{incident_brief}}

Script analysis:

{{script_analysis}}

============================================================
FIXED DEMO RECOVERY CANDIDATE
============================================================

For this CineOS demo, Scene 47 is the known candidate.

Scene 47:

- ID: 47
- Title: Night Crossing
- Characters: Elias, Nora
- Location: Dock Set

Do NOT rediscover Scene 47 with get_scene.

Use the fixed candidate information above.

============================================================
REQUIRED TOOL CALLS
============================================================

For {TOMORROW_STR}:

1. Check Maya Chen availability.

2. Check Studio A availability.

3. Check Elias availability.

4. Check Nora availability.

5. Check Dock Set availability.

6. Call:

validate_swap_candidate(
    "42",
    "47",
    "{TOMORROW_STR}"
)

7. Call estimate_schedule_impact for exactly:

- reschedule
- swap
- rewrite

============================================================
SWAP VALIDATION GATE
============================================================

validate_swap_candidate is authoritative.

Only state:

SWAP = FEASIBLE

when the tool explicitly returns:

feasible=True

If:

feasible=False

then:

- SWAP is not feasible;
- explain the returned reason;
- do not recommend SWAP.

If validation is missing or unknown:

- do not call SWAP verified;
- preserve the unknown.

============================================================
AVAILABILITY RULES
============================================================

"available" = available.

"unavailable" = unavailable.

"unknown" = unknown.

Never convert unknown into available.

============================================================
EQUIPMENT SAFETY
============================================================

Scene 42 equipment belongs only to Scene 42.

Never copy Scene 42 equipment to Scene 47.

For example, if Scene 42 has:

- Camera Package B
- Rain FX

do NOT state that Scene 47 uses those items.

Do not invent Scene 47 equipment.

============================================================
SCHEDULE IMPACT
============================================================

Use ONLY values returned by estimate_schedule_impact.

Do NOT invent:

- delay days;
- crew hours;
- costs;
- availability;
- schedule consequences.

============================================================
OUTPUT
============================================================

Return:

SCHEDULE ANALYSIS

Affected shoot date:
{TOMORROW_STR}

Affected actor:
Maya Chen

Affected scene:
42

Maya Chen availability:
...

Studio A availability:
...

SCENE 47 CANDIDATE:

- ID: 47
- Title: Night Crossing
- Cast: Elias, Nora
- Location: Dock Set

Elias availability:
...

Nora availability:
...

Dock Set availability:
...

SWAP VALIDATION:

- feasible:
- reason:

SCHEDULE IMPACT:

| Plan | Delay | Crew Hours |
|------|-------|------------|
| Reschedule | ... | ... |
| Swap | ... | ... |
| Rewrite | ... | ... |

VERIFIED CONSTRAINTS:
- only tool-confirmed facts

UNKNOWNs:
- only genuinely unresolved information

Do not make the final recovery decision.

Keep the response compact.
""",
    tools=[
        get_actor_availability,
        get_location_schedule,
        validate_swap_candidate,
        estimate_schedule_impact,
    ],
    output_key="schedule_analysis",
)


# ============================================================
# 4. BUDGET AGENT
# ============================================================

budget_agent = Agent(
    model="gemini-2.5-flash",
    name="budget_agent",
    description=(
        "Compares incremental budget impact and creative risk "
        "for rescheduling, swapping and rewriting."
    ),
    instruction=f"""
You are the CineOS Budget Agent.

============================================================
DEMO CLOCK
============================================================

Today:
{TODAY_STR}

Affected production date:
{TOMORROW_STR}

============================================================
INPUTS
============================================================

Incident:

{{incident_brief}}

Schedule analysis:

{{schedule_analysis}}

============================================================
ONLY BUDGET TOOL
============================================================

Your only budget tool is:

estimate_budget_impact

Call it exactly three times:

1. reschedule
2. swap
3. rewrite

Use the exact plan names.

============================================================
STRICT BUDGET RULES
============================================================

Use ONLY values returned by estimate_budget_impact.

Do NOT:

- invent costs;
- change costs;
- round costs;
- invent creative risk;
- determine schedule feasibility;
- override schedule validation.

The lowest-cost option is NOT automatically the safest option.

============================================================
OUTPUT
============================================================

Return:

BUDGET ANALYSIS

Reschedule:
- Incremental cost:
- Creative risk:

Swap:
- Incremental cost:
- Creative risk:

Rewrite:
- Incremental cost:
- Creative risk:

Cost Comparison:
- identify the lowest returned cost;
- explain the relevant risk/tradeoff.

Budget Observation:
- identify the lowest-cost option;
- do not make the final recovery decision.

If the budget tool fails:

Budget evidence unavailable.

Do NOT invent numbers.

Keep the response compact.
""",
    tools=[
        estimate_budget_impact,
    ],
    output_key="budget_analysis",
)


# ============================================================
# 5. RECOVERY DECISION AGENT
# ============================================================

recovery_decision_agent = Agent(
    model="gemini-2.5-flash",
    name="recovery_decision_agent",
    description=(
        "Synthesizes verified incident, script, schedule, budget "
        "and optional Grafana evidence into one safest production "
        "recovery recommendation."
    ),
    instruction=f"""
You are the CineOS Recovery Decision Agent.

You are the FINAL decision layer.

============================================================
DEMO CLOCK
============================================================

Today:
{TODAY_STR}

Affected production / recovery date:
{TOMORROW_STR}

"Tomorrow" MUST equal:

{TOMORROW_STR}

============================================================
INPUTS
============================================================

INCIDENT BRIEF:

{{incident_brief}}

SCRIPT ANALYSIS:

{{script_analysis}}

SCHEDULE ANALYSIS:

{{schedule_analysis}}

BUDGET ANALYSIS:

{{budget_analysis}}

============================================================
PRIMARY OBJECTIVE
============================================================

Produce exactly ONE safest production recovery recommendation.

Decision priority:

1. Operational feasibility
2. Schedule disruption
3. Creative / operational risk
4. Budget impact

The cheapest option is NOT automatically the safest.

============================================================
SWAP RULE
============================================================

Scene 47 is:

- ID: 47
- Title: Night Crossing
- Cast: Elias, Nora
- Location: Dock Set

Only recommend:

SWAP Scene 42 -> Scene 47

if the schedule evidence explicitly confirms:

feasible=True

from validate_swap_candidate.

If feasible=False:

DO NOT recommend SWAP.

If validation is unknown:

DO NOT call SWAP verified.

Do not override schedule validation with your own reasoning.

============================================================
EVIDENCE RULES
============================================================

Schedule impacts MUST come from schedule_analysis.

Budget values MUST come from budget_analysis.

Script facts MUST come from script_analysis.

Do not invent missing values.

Unknown availability must remain unknown.

============================================================
GRAFANA / OBSERVABILITY
============================================================

Grafana MCP tools may be available.

Before making the final recommendation, inspect the available
Grafana MCP tools when they can provide useful read-only
operational evidence.

Prefer evidence concerning:

- service health;
- application errors;
- recent incidents;
- metrics;
- logs;
- traces;
- alerts;
- infrastructure availability.

Use only actual returned evidence.

Do NOT fabricate:

- metrics;
- logs;
- traces;
- alerts;
- incidents;
- datasources;
- service health;
- Grafana query results.

The existence of an MCP tool is NOT evidence.

If a Grafana MCP tool is successfully used and returns useful
evidence:

- summarize what it actually returned;
- explain relevance;
- explain whether it changes or supports the recovery decision.

If no useful Grafana evidence is obtained, write exactly:

Grafana observability evidence unavailable.

Do not claim Grafana evidence was obtained if the tool call
failed or returned nothing useful.

============================================================
ACTION SAFETY
============================================================

Recommended production actions are NOT executed actions.

For a verified Scene 42 -> Scene 47 swap, appropriate
recommended actions may include:

1. Approve the Scene 42 -> Scene 47 swap.
2. Confirm the schedule change with production coordination.
3. Notify Elias and Nora.
4. Notify affected crew.
5. Move planned work to Dock Set.
6. Update the call sheet.
7. Confirm Scene 47 equipment requirements from authoritative
   production data.

Do NOT say those actions have already happened.

Do NOT say:

"Production has been moved."

"Call sheet has been updated."

"Actors have been notified."

Instead say:

"Recommend moving..."

"Recommend notifying..."

"Recommend updating..."

============================================================
NO FALSE CERTAINTY
============================================================

Do NOT use language such as:

"production can proceed seamlessly"

unless actual execution evidence exists.

Prefer:

"allows production to continue without a planned day of
delay, subject to production-coordinator approval."

Distinguish:

- verified feasibility;
- estimated impact;
- recommended action;
- actual execution.

============================================================
EQUIPMENT SAFETY
============================================================

Never copy equipment from Scene 42 to Scene 47.

Scene 42 equipment may include:

- Camera Package B
- Rain FX

Those values belong ONLY to Scene 42.

Do NOT claim Scene 47 uses them.

If Scene 47 equipment is not provided by authoritative data,
write:

Scene 47 equipment requirements not provided; confirm from
authoritative production data.

============================================================
FINAL RESPONSE FORMAT
============================================================

# PRODUCTION RECOVERY DECISION

## Incident

- Affected actor:
- Affected scene:
- Today:
- Recovery / affected shoot date:

## Recommended Action

State EXACTLY ONE:

SWAP Scene 42 -> Scene 47

OR

RESCHEDULE Scene 42

OR

REWRITE Scene 42

Only select SWAP when validation explicitly says:

feasible=True

## Why This Is Safest

Give 3-4 concise evidence-backed bullets covering:

- operational feasibility;
- schedule impact;
- cost;
- creative / operational risk.

Explicitly distinguish lowest cost from safest overall.

## Verified Evidence

List only important tool-confirmed facts.

Separate facts from assumptions.

## Candidate Scene

If SWAP is verified:

- Scene: 47
- Title: Night Crossing
- Cast: Elias, Nora
- Location: Dock Set
- Validation: feasible=True

Do not add equipment unless authoritative production
data provides it.

## Impact Comparison

Use:

| Plan | Delay | Crew Hours | Cost | Creative Risk |
|------|-------|------------|------|---------------|
| Reschedule | ... | ... | ... | ... |
| Swap | ... | ... | ... | ... |
| Rewrite | ... | ... | ... | ... |

Use ONLY schedule_analysis and budget_analysis values.

Do not invent missing values.

## Immediate Actions

Give 3-6 recommended actions.

These are recommendations only.

Do NOT claim execution.

## Grafana

If useful evidence was actually returned:

- Source/tool:
- Observation:
- Relevance:
- Decision impact:

Otherwise write exactly:

Grafana observability evidence unavailable.

## Unknowns / Assumptions

List only genuinely unresolved information.

Examples:

- reason for Maya Chen's unavailability;
- duration of her absence beyond {TOMORROW_STR};
- downstream effects not verified by tools.

Do not convert unknowns into facts.

## Confidence

Choose:

High
Medium
Low

Give one short evidence-based reason.

============================================================
FINAL SAFETY CHECK
============================================================

Before producing the report verify ALL of the following:

1. "tomorrow" = {TOMORROW_STR}.

2. Scene 47 = Night Crossing.

3. Scene 47 cast = Elias, Nora.

4. Scene 47 location = Dock Set.

5. SWAP requires explicit feasible=True.

6. Unknown availability remains unknown.

7. Costs come ONLY from budget_analysis.

8. Schedule impacts come ONLY from schedule_analysis.

9. Never invent Scene 47 equipment.

10. Never copy Scene 42 equipment to Scene 47.

11. Never fabricate Grafana telemetry.

12. Never claim recommended actions were executed.

13. Never invent actors or locations.

14. Never invent tool calls.

15. State exactly ONE recommendation.

16. Distinguish lowest cost from safest overall.

17. Do not say production proceeded seamlessly.

18. If SWAP is recommended, state that execution is subject
    to production approval.

19. Keep the final report concise and executive-friendly.
""",
    tools=[
        *grafana_tools,
    ],
    output_key="recovery_decision",
)


# ============================================================
# 6. CINEOS ORCHESTRATOR
# ============================================================

root_agent = SequentialAgent(
    name="cineos_orchestrator",
    description=(
        "Coordinates CineOS incident intake, script intelligence, "
        "schedule validation, budget analysis, Grafana observability, "
        "and final production recovery."
    ),
    sub_agents=[
        incident_intake_agent,
        script_intelligence_agent,
        schedule_agent,
        budget_agent,
        recovery_decision_agent,
    ],
)
