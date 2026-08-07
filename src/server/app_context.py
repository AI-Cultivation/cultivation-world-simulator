from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.server.host_runtime import ConnectionManager
from src.server.runtime import GameSessionRuntime
from src.server.services.game_command_service import GameCommandService
from src.server.services.game_command_service import GameCommandDependencies
from src.server.services.game_query_service import GameQueryService
from src.server.services.game_query_service import GameQueryDependencies


@dataclass(slots=True)
class ServerAppContext:
    """Composition container for the server runtime and public services."""

    runtime: GameSessionRuntime
    manager: ConnectionManager
    game_state: dict[str, Any]
    avatar_assets: dict[str, Any]
    settings_service: Any
    static_data: Any
    query_service: GameQueryService
    command_service: GameCommandService
    version: str = ""


def create_server_context(
    *,
    runtime: GameSessionRuntime,
    manager: ConnectionManager,
    game_state: dict[str, Any],
    avatar_assets: dict[str, Any],
    settings_service: Any,
    static_data: Any,
    query_dependencies: GameQueryDependencies,
    command_dependencies: GameCommandDependencies,
    version: str = "",
) -> ServerAppContext:
    """Build the server composition root from explicit dependency maps."""
    query_service = GameQueryService(query_dependencies)
    command_service = GameCommandService(command_dependencies)
    return ServerAppContext(
        runtime=runtime,
        manager=manager,
        game_state=game_state,
        avatar_assets=avatar_assets,
        settings_service=settings_service,
        static_data=static_data,
        query_service=query_service,
        command_service=command_service,
        version=version,
    )
