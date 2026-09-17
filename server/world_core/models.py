from dataclasses import dataclass, field


@dataclass
class WorldState:
    signal: float = 0.10
    stability: float = 0.90
    connection: float = 0.35

    def clamp(self) -> None:
        self.signal = max(0.0, min(1.0, self.signal))
        self.stability = max(0.0, min(1.0, self.stability))
        self.connection = max(0.0, min(1.0, self.connection))


@dataclass
class WorldNode:
    id: str
    location: str
    node_type: str
    discovered: bool = False
    active: bool = True
    anomaly_strength: float = 0.50


@dataclass
class NodeBelief:
    agent_id: str
    node_id: str
    believed_location: str
    believed_strength: float
    confidence: float
    source: str
    updated_minute: int


@dataclass
class Agent:
    id: str
    name: str
    faction: str
    location: str
    goal: str
    energy: float = 1.0
    controller_type: str = "AI"
    memory: list[str] = field(default_factory=list)


@dataclass
class ActionIntent:
    actor_id: str
    action: str
    target: str
    source: str = "AI"