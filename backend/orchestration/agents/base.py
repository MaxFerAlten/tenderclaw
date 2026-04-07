"""Base agent class for TenderClaw agents."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger(__name__)


class AgentCapability(Enum):
    READ = "read"
    WRITE = "write"
    EDIT = "edit"
    DELEGATE = "delegate"
    BROWSE = "browse"
    EXECUTE = "execute"


@dataclass
class AgentConfig:
    name: str
    model: str | None = None
    temperature: float = 0.7
    max_tokens: int | None = None
    system_prompt: str | None = None
    tools: list[str] | None = None
    disabled_tools: list[str] | None = None


@dataclass
class AgentResult:
    success: bool
    content: str | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseAgent(ABC):
    """
    Base class for all TenderClaw agents.
    
    Agents are specialized AI workers that handle specific tasks.
    Each agent has distinct expertise, model preferences, and tool permissions.
    """

    def __init__(
        self,
        config: AgentConfig | None = None,
        model: str | None = None,
        **kwargs
    ):
        self.config = config or AgentConfig(name=self.__class__.__name__)
        self.model = model or self.config.model
        self._setup_logging()

    def _setup_logging(self) -> None:
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @property
    @abstractmethod
    def name(self) -> str:
        """Agent name."""
        pass

    @property
    def description(self) -> str:
        """Agent description for helptext."""
        return self.__doc__ or "No description"

    @property
    def system_prompt(self) -> str:
        """Agent system prompt."""
        return self.config.system_prompt or self._get_default_system_prompt()

    @abstractmethod
    def _get_default_system_prompt(self) -> str:
        """Get the default system prompt for this agent."""
        pass

    def get_capabilities(self) -> set[AgentCapability]:
        """Get agent capabilities. Override in subclasses."""
        return {
            AgentCapability.READ,
            AgentCapability.WRITE,
            AgentCapability.EDIT,
            AgentCapability.DELEGATE,
        }

    def get_restricted_tools(self) -> list[str]:
        """Get tools that should be disabled for this agent. Override in subclasses."""
        return []

    @abstractmethod
    async def execute(self, task: str, context: dict[str, Any] | None = None) -> AgentResult:
        """
        Execute a task with the agent.
        
        Args:
            task: The task description
            context: Optional context dictionary
            
        Returns:
            AgentResult with success status and content
        """
        pass

    async def plan(self, goal: str, constraints: list[str] | None = None) -> list[str]:
        """
        Create a plan to achieve a goal.
        
        Args:
            goal: The goal to achieve
            constraints: Optional constraints to consider
            
        Returns:
            List of steps to achieve the goal
        """
        raise NotImplementedError(f"{self.name} does not support planning")

    async def review(self, content: str) -> AgentResult:
        """
        Review content and provide feedback.
        
        Args:
            content: Content to review
            
        Returns:
            AgentResult with review feedback
        """
        raise NotImplementedError(f"{self.name} does not support review")

    def validate_task(self, task: str) -> bool:
        """
        Validate if this agent can handle the task.
        
        Args:
            task: Task description
            
        Returns:
            True if agent can handle the task
        """
        return True

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(model={self.model})>"


class AgentRegistry:
    """Registry for all available agents."""

    _agents: dict[str, type[BaseAgent]] = {}
    _instances: dict[str, BaseAgent] = {}

    @classmethod
    def register(cls, name: str | None = None):
        """Decorator to register an agent class."""
        def decorator(agent_class: type[BaseAgent]):
            agent_name = name or agent_class.__name__.lower()
            cls._agents[agent_name] = agent_class
            return agent_class
        return decorator

    @classmethod
    def get(cls, name: str) -> BaseAgent:
        """Get or create an agent instance by name."""
        if name not in cls._instances:
            if name not in cls._agents:
                raise ValueError(f"Unknown agent: {name}")
            cls._instances[name] = cls._agents[name]()
        return cls._instances[name]

    @classmethod
    def list_agents(cls) -> list[str]:
        """List all registered agent names."""
        return list(cls._agents.keys())

    @classmethod
    def create_all(cls) -> dict[str, BaseAgent]:
        """Create instances of all registered agents."""
        return {name: cls.get(name) for name in cls._agents}


def agent(name: str | None = None):
    """Shorthand decorator for agent registration."""
    return AgentRegistry.register(name)
