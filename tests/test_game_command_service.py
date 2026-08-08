import asyncio
from types import SimpleNamespace

import pytest

from src.server.services.game_command_service import GameCommandService
from src.server.runtime import GameSessionRuntime, create_default_game_state


class FakeRuntime:
    def __init__(self):
        self.world_revision = 0

    async def run_mutation_measured(self, operation, *args, **kwargs):
        result = operation(*args, **kwargs)
        self.world_revision += 1
        return result, {"lock_wait_ms": 0, "execution_ms": 1}


class FakeManager:
    def __init__(self):
        self.messages = []

    async def broadcast(self, message):
        self.messages.append(message)


def make_service(*, create_result=None, delete_result=None):
    runtime = FakeRuntime()
    manager = FakeManager()
    dependencies = SimpleNamespace(
        runtime=runtime,
        manager=manager,
        static_data=SimpleNamespace(sects_by_id={}),
        create_avatar_in_world=lambda *_args, **_kwargs: create_result,
        create_avatar_from_request=object(),
        uses_space_separated_names=object(),
        language_manager=object(),
        avatar_assets={},
        alignment_from_str=object(),
        get_appearance_by_level=object(),
        resolve_avatar_pic_id=lambda **_kwargs: 1,
        resolve_avatar_action_emoji=object(),
        delete_avatar_in_world=lambda *_args, **_kwargs: delete_result,
    )
    return GameCommandService(dependencies), runtime, manager


@pytest.mark.asyncio
async def test_create_avatar_broadcasts_current_revision_delta():
    service, _runtime, manager = make_service(
        create_result={"status": "ok", "avatar": {"id": "created-1", "name": "Created"}},
    )

    result = await service.create_avatar(SimpleNamespace())

    assert result["world_revision"] == 1
    assert result["timing"] == {"lock_wait_ms": 0, "execution_ms": 1}
    assert manager.messages == [
        {
            "type": "avatar_delta",
            "avatars": [{"id": "created-1", "name": "Created"}],
            "removed_avatar_ids": [],
            "world_revision": 1,
        }
    ]


@pytest.mark.asyncio
async def test_delete_avatar_broadcasts_current_revision_delta():
    service, _runtime, manager = make_service(
        delete_result={"status": "ok", "removed_avatar_id": "deleted-1"},
    )

    result = await service.delete_avatar(avatar_id="deleted-1")

    assert result["world_revision"] == 1
    assert manager.messages == [
        {
            "type": "avatar_delta",
            "avatars": [],
            "removed_avatar_ids": ["deleted-1"],
            "world_revision": 1,
        }
    ]


@pytest.mark.asyncio
async def test_roleplay_llm_work_does_not_hold_world_mutation_lock():
    runtime = GameSessionRuntime(create_default_game_state())
    started = asyncio.Event()
    release = asyncio.Event()

    async def slow_roleplay(_runtime, **_kwargs):
        started.set()
        await release.wait()
        return {"status": "ok"}

    roleplay_commands = SimpleNamespace(
        submit_decision=lambda **kwargs: slow_roleplay(runtime, **kwargs),
    )
    service = GameCommandService(SimpleNamespace(runtime=runtime, roleplay_commands=roleplay_commands))
    request = asyncio.create_task(
        service.submit_roleplay_decision(avatar_id="a", request_id="r", command_text="wait")
    )
    await started.wait()

    completed = []
    await runtime.run_mutation(lambda: completed.append("world mutation"))
    assert completed == ["world mutation"]

    release.set()
    assert await request == {"status": "ok"}
