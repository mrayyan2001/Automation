from common.agent.agent_builder import AgentBuilder


class PlannerAgent[OutputT](AgentBuilder[OutputT]):
    """Agent wrapper that labels planning calls separately from builders."""

    def __init__(self, *args, **kwargs):
        kwargs["agent_role"] = "Planner"
        super().__init__(*args, **kwargs)
