from __future__ import annotations

from dataclasses import dataclass
import inspect
from types import SimpleNamespace
from typing import Any

from fastapi import HTTPException

from src.config import RunConfig, get_settings_service
from src.i18n import t


@dataclass(slots=True)
class GameCommandDependencies:
    static_data: Any
    runtime: Any
    manager: Any
    avatar_assets: dict[str, Any]
    assets_path: str
    model_to_dict: Any
    validate_save_name: Any
    get_init_game_async: Any
    get_apply_runtime_content_locale: Any
    scan_avatar_assets: Any
    start_game_lifecycle: Any
    reinit_game_lifecycle: Any
    cleanup_events_command: Any
    set_world_phenomenon: Any
    create_avatar_in_world: Any
    create_avatar_from_request: Any
    uses_space_separated_names: Any
    language_manager: Any
    alignment_from_str: Any
    get_appearance_by_level: Any
    resolve_avatar_pic_id: Any
    resolve_avatar_action_emoji: Any
    delete_avatar_in_world: Any
    update_avatar_adjustment_in_world: Any
    apply_avatar_adjustment: Any
    update_avatar_portrait_in_world: Any
    generate_custom_content_command: Any
    get_generate_custom_goldfinger_draft: Any
    get_generate_custom_content_draft: Any
    realm_from_str: Any
    create_custom_content_command: Any
    create_custom_goldfinger_from_draft: Any
    create_custom_content_from_draft: Any
    set_long_term_objective_for_avatar: Any
    clear_long_term_objective_for_avatar: Any
    set_user_long_term_objective: Any
    clear_user_long_term_objective: Any
    save_current_game: Any
    save_game_impl: Any
    delete_save_file: Any
    get_config: Any
    get_fallback_saves_dirs: Any
    get_load_game_into_runtime: Any
    get_load_game: Any
    get_events_db_path: Any
    get_roleplay_session: Any
    clear_roleplay_session: Any
    start_roleplay: Any
    stop_roleplay: Any
    submit_roleplay_decision: Any
    submit_roleplay_choice: Any
    submit_roleplay_conversation_turn: Any
    end_roleplay_conversation: Any


class GameCommandService:
    """Public-command use-case service.

    The old command handler namespace is retained as a compatibility adapter.
    Public routers should call this service directly.
    """

    def __init__(self, dependencies: GameCommandDependencies):
        self._deps = dependencies

    @classmethod
    def from_dependencies(cls, *, static_data: Any, **dependencies: Any) -> "GameCommandService":
        save_game_impl = dependencies.pop("save_game", None)
        if save_game_impl is None:
            save_game_impl = dependencies.pop("save_game_impl")
        return cls(
            GameCommandDependencies(
                static_data=static_data,
                save_game_impl=save_game_impl,
                **dependencies,
            )
        )

    @property
    def handlers(self) -> Any:
        return SimpleNamespace(
            run_start_game=self.start_game,
            run_reinit_game=self.reinit_game,
            run_reset_game=self.reset_game,
            run_pause_game=self.pause_game,
            run_pause_game_and_drain=self.pause_game_and_drain,
            run_resume_game=self.resume_game,
            run_cleanup_events=self.cleanup_events,
            run_set_phenomenon=self.set_phenomenon,
            run_create_avatar=self.create_avatar,
            run_delete_avatar=self.delete_avatar,
            run_update_avatar_adjustment=self.update_avatar_adjustment,
            run_update_avatar_portrait=self.update_avatar_portrait,
            run_generate_custom_content=self.generate_custom_content,
            run_create_custom_content=self.create_custom_content,
            run_set_long_term_objective=self.set_long_term_objective,
            run_clear_long_term_objective=self.clear_long_term_objective,
            run_save_game=self.save_game,
            run_delete_save=self.delete_save,
            run_load_game=self.load_game,
            run_start_roleplay=self.start_roleplay,
            run_stop_roleplay=self.stop_roleplay,
            run_submit_roleplay_decision=self.submit_roleplay_decision,
            run_submit_roleplay_choice=self.submit_roleplay_choice,
            run_send_roleplay_conversation=self.send_roleplay_conversation,
            run_end_roleplay_conversation=self.end_roleplay_conversation,
        )

    async def start_game(self, req: Any) -> dict:
        run_config = RunConfig(**self._deps.model_to_dict(req))
        return await self._deps.start_game_lifecycle(
            self._deps.runtime,
            run_config=run_config,
            apply_runtime_content_locale=self._deps.get_apply_runtime_content_locale(),
            init_game_async=self._deps.get_init_game_async(),
        )

    async def reinit_game(self) -> dict:
        return await self._deps.reinit_game_lifecycle(
            self._deps.runtime,
            init_game_async=self._deps.get_init_game_async(),
        )

    async def reset_game(self) -> dict:
        self._deps.runtime.request_reset()
        await self._deps.runtime.run_mutation(self._deps.runtime.reset_to_idle)
        return {"status": "ok", "message": "Game reset to idle"}

    async def pause_game(self) -> dict:
        self._deps.runtime.set_paused(True)
        return {"status": "ok", "message": "Game paused"}

    async def pause_game_and_drain(self) -> dict:
        self._deps.runtime.set_paused(True)
        await self._deps.runtime.run_mutation(lambda: None)
        return {"status": "ok", "message": "Game paused"}

    async def resume_game(self) -> dict:
        self._deps.runtime.set_paused(False)
        return {"status": "ok", "message": "Game resumed"}

    async def set_long_term_objective(self, req: Any) -> dict:
        return await self._deps.runtime.run_mutation(
            self._deps.set_long_term_objective_for_avatar,
            self._deps.runtime,
            avatar_id=req.avatar_id,
            content=req.content,
            setter=self._deps.set_user_long_term_objective,
        )

    async def clear_long_term_objective(self, req: Any) -> dict:
        return await self._deps.runtime.run_mutation(
            self._deps.clear_long_term_objective_for_avatar,
            self._deps.runtime,
            avatar_id=req.avatar_id,
            clearer=self._deps.clear_user_long_term_objective,
        )

    async def create_avatar(self, req: Any) -> dict:
        result, timing = await self._deps.runtime.run_mutation_measured(
            self._deps.create_avatar_in_world,
            self._deps.runtime,
            req=req,
            create_avatar_from_request=self._deps.create_avatar_from_request,
            sects_by_id=self._deps.static_data.sects_by_id,
            uses_space_separated_names=self._deps.uses_space_separated_names,
            language_manager=self._deps.language_manager,
            avatar_assets=self._deps.avatar_assets,
            alignment_from_str=self._deps.alignment_from_str,
            get_appearance_by_level=self._deps.get_appearance_by_level,
            resolve_avatar_pic_id=lambda avatar: self._deps.resolve_avatar_pic_id(
                avatar_assets=self._deps.avatar_assets,
                avatar=avatar,
            ),
            resolve_avatar_action_emoji=self._deps.resolve_avatar_action_emoji,
        )
        result["world_revision"] = self._deps.runtime.world_revision
        result["timing"] = timing
        await self._broadcast_avatar_delta(avatars=[result["avatar"]])
        return result

    async def delete_avatar(self, *, avatar_id: str) -> dict:
        result, timing = await self._deps.runtime.run_mutation_measured(
            self._deps.delete_avatar_in_world,
            self._deps.runtime,
            avatar_id=avatar_id,
        )
        result["world_revision"] = self._deps.runtime.world_revision
        result["timing"] = timing
        await self._broadcast_avatar_delta(removed_avatar_ids=[result["removed_avatar_id"]])
        return result

    async def _broadcast_avatar_delta(
        self,
        *,
        avatars: list[dict[str, Any]] | None = None,
        removed_avatar_ids: list[str] | None = None,
    ) -> None:
        broadcast = getattr(self._deps.manager, "broadcast", None)
        if not callable(broadcast):
            return

        result = broadcast(
            {
                "type": "avatar_delta",
                "avatars": avatars or [],
                "removed_avatar_ids": removed_avatar_ids or [],
                "world_revision": self._deps.runtime.world_revision,
            }
        )
        if inspect.isawaitable(result):
            await result

    async def update_avatar_adjustment(self, req: Any) -> dict:
        self._deps.runtime.set_paused(True)
        return await self._deps.runtime.run_mutation(
            self._deps.update_avatar_adjustment_in_world,
            self._deps.runtime,
            avatar_id=req.avatar_id,
            category=req.category,
            target_id=req.target_id,
            persona_ids=req.persona_ids,
            apply_avatar_adjustment=self._deps.apply_avatar_adjustment,
        )

    async def update_avatar_portrait(self, *, avatar_id: str, pic_id: int) -> dict:
        return await self._deps.runtime.run_mutation(
            self._deps.update_avatar_portrait_in_world,
            self._deps.runtime,
            avatar_id=avatar_id,
            pic_id=pic_id,
            avatar_assets=self._deps.avatar_assets,
        )

    async def generate_custom_content(self, req: Any) -> dict:
        run_config = self._deps.runtime.get("run_config") or {}
        if bool(run_config.get("test_mode", False)):
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "TEST_MODE_LLM_UNAVAILABLE",
                    "message": "测试模式下不提供 LLM 内容生成。",
                },
            )
        return await self._deps.generate_custom_content_command(
            category=req.category,
            realm=req.realm,
            user_prompt=req.user_prompt,
            generate_custom_goldfinger_draft=self._deps.get_generate_custom_goldfinger_draft(),
            generate_custom_content_draft=self._deps.get_generate_custom_content_draft(),
            realm_from_str=self._deps.realm_from_str,
        )

    def create_custom_content(self, req: Any) -> dict:
        return self._deps.create_custom_content_command(
            category=req.category,
            draft=req.draft,
            create_custom_goldfinger_from_draft=self._deps.create_custom_goldfinger_from_draft,
            create_custom_content_from_draft=self._deps.create_custom_content_from_draft,
        )

    async def set_phenomenon(self, *, phenomenon_id: int) -> dict:
        return await self._deps.runtime.run_mutation(
            self._deps.set_world_phenomenon,
            self._deps.runtime,
            phenomenon_id=phenomenon_id,
            celestial_phenomena_by_id=self._deps.static_data.celestial_phenomena_by_id,
        )

    async def cleanup_events(
        self,
        *,
        keep_major: bool,
        before_month_stamp: int | None,
    ) -> dict:
        return await self._deps.runtime.run_mutation(
            self._deps.cleanup_events_command,
            self._deps.runtime,
            keep_major=keep_major,
            before_month_stamp=before_month_stamp,
        )

    def save_game(self, *, custom_name: str | None) -> dict:
        return self._deps.save_current_game(
            self._deps.runtime,
            custom_name=custom_name,
            validate_save_name=self._deps.validate_save_name,
            save_game=self._deps.save_game_impl,
            sects_by_id=self._deps.static_data.sects_by_id,
        )

    def delete_save(self, *, filename: str) -> dict:
        return self._deps.delete_save_file(
            filename=filename,
            saves_dir=self._deps.get_config().paths.saves,
            fallback_saves_dirs=self._deps.get_fallback_saves_dirs(),
            get_events_db_path=self._deps.get_events_db_path,
        )

    async def load_game(self, *, filename: str) -> dict:
        from src.sim import get_save_info

        return await self._deps.get_load_game_into_runtime()(
            self._deps.runtime,
            filename=filename,
            saves_dir=self._deps.get_config().paths.saves,
            fallback_saves_dirs=self._deps.get_fallback_saves_dirs(),
            get_save_info=get_save_info,
            language_manager=self._deps.language_manager,
            manager=self._deps.manager,
            t=t,
            apply_runtime_content_locale=self._deps.get_apply_runtime_content_locale(),
            scan_avatar_assets=lambda: self._deps.avatar_assets.update(
                self._deps.scan_avatar_assets(assets_path=self._deps.assets_path)
            ),
            load_game=self._deps.get_load_game(),
            get_settings_service=get_settings_service,
            _model_to_dict=self._deps.model_to_dict,
        )

    async def start_roleplay(self, *, avatar_id: str) -> dict:
        return await self._deps.runtime.run_mutation(
            self._deps.start_roleplay, self._deps.runtime, avatar_id=avatar_id
        )

    async def stop_roleplay(self, *, avatar_id: str | None) -> dict:
        return await self._deps.runtime.run_mutation(
            self._deps.stop_roleplay, self._deps.runtime, avatar_id=avatar_id
        )

    async def submit_roleplay_decision(
        self,
        *,
        avatar_id: str,
        request_id: str,
        command_text: str,
    ) -> dict:
        # The roleplay service performs short prepare/commit mutations around
        # the remote LLM request.  Do not hold the world lock while waiting on
        # the provider: a slow provider must not freeze simulation, saving, or
        # unrelated commands.
        return await self._deps.submit_roleplay_decision(
            self._deps.runtime,
            avatar_id=avatar_id,
            request_id=request_id,
            command_text=command_text,
        )

    async def submit_roleplay_choice(
        self,
        *,
        avatar_id: str,
        request_id: str,
        selected_key: str,
    ) -> dict:
        return await self._deps.runtime.run_mutation(
            self._deps.submit_roleplay_choice,
            self._deps.runtime,
            avatar_id=avatar_id,
            request_id=request_id,
            selected_key=selected_key,
        )

    async def send_roleplay_conversation(
        self,
        *,
        avatar_id: str,
        request_id: str,
        message: str,
    ) -> dict:
        return await self._deps.submit_roleplay_conversation_turn(
            self._deps.runtime,
            avatar_id=avatar_id,
            request_id=request_id,
            message=message,
        )

    async def end_roleplay_conversation(
        self,
        *,
        avatar_id: str,
        request_id: str,
    ) -> dict:
        return await self._deps.end_roleplay_conversation(
            self._deps.runtime,
            avatar_id=avatar_id,
            request_id=request_id,
        )
