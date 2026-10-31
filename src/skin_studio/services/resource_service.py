"""Development-only simulated resource adapter."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SimulationResult:
    message: str
    simulated: bool = True


class SimulatedResourceAdapter:
    def preview(self, resource_name: str) -> SimulationResult:
        """Describe a simulated operation without touching the file system."""
        return SimulationResult(f"Preview only: {resource_name}")
