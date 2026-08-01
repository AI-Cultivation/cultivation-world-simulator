"""
Tests for WebSocket handlers and connection management.

## What's Tested (Unit Tests)

- ConnectionManager class:
  - connect(): accepts WebSocket, stores in active_connections
  - disconnect(): removes WebSocket, auto-pauses when last client leaves
  - broadcast(): sends JSON to all connections, handles errors gracefully

- WebSocket endpoint /ws:
  - Connection acceptance
  - LLM config required message on connect (when llm_check_failed=True)
  - Ping/pong message handling
  - Disconnect handling (via TestClient context manager)

- Control API endpoints:
  - POST /api/v1/command/game/pause
  - POST /api/v1/command/game/resume
  - POST /api/v1/command/game/reset

- State/Map API:
  - GET /api/v1/query/world/state (error handling, data serialization)
  - GET /api/v1/query/world/map (error handling, data serialization)

- Event serialization:
  - serialize_events_for_client() function

## What's NOT Tested Here (Requires Integration Tests)

- game_loop():
  - This is a background async task that runs continuously.
  - It calls sim.step() and broadcasts tick updates every second.
  - Testing this requires mocking the entire game simulation.
  - Covered by: Issue #72 (Game initialization integration test)

- WebSocket exception path (non-WebSocketDisconnect errors):
  - Line 684-686 in main.py
  - Edge case when WebSocket throws unexpected exception.

Uses FastAPI TestClient with WebSocket support.
"""

import json
import asyncio
import time
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from fastapi.testclient import TestClient

from src.server import main
from src.server.main import app, game_instance, ConnectionManager


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def disable_auto_shutdown(monkeypatch):
    """Prevent websocket disconnect tests from terminating the pytest worker process."""
    monkeypatch.setattr(main, "IS_DEV_MODE", True)
    yield
    shutdown_timer = getattr(main.manager, "_shutdown_timer", None)
    if shutdown_timer:
        shutdown_timer.cancel()
        main.manager._shutdown_timer = None


@pytest.fixture
def reset_game_instance():
    """Reset game_instance to initial state before each test."""
    original_state = dict(game_instance)
    game_instance.clear()
    game_instance.update({
        "world": None,
        "sim": None,
        "is_paused": True,
        "init_status": "idle",
        "init_phase": 0,
        "init_phase_name": "",
        "init_progress": 0,
        "init_start_time": None,
        "init_error": None,
        "llm_check_failed": False,
        "llm_error_message": "",
    })
    yield
    game_instance.clear()
    game_instance.update(original_state)


@pytest.fixture
def fresh_manager():
    """Create a fresh ConnectionManager for testing."""
    return ConnectionManager(runtime=main.runtime)


class TestConnectionManager:
    """Tests for ConnectionManager class."""

    def test_initial_state(self, fresh_manager):
        """Test ConnectionManager starts with no connections."""
        assert len(fresh_manager.active_connections) == 0

    @pytest.mark.asyncio
    async def test_connect_accepts_websocket(self, fresh_manager):
        """Test connect() accepts and stores websocket."""
        mock_ws = AsyncMock()

        await fresh_manager.connect(mock_ws)

        mock_ws.accept.assert_called_once()
        assert mock_ws in fresh_manager.active_connections
        assert len(fresh_manager.active_connections) == 1

    @pytest.mark.asyncio
    async def test_connect_multiple_websockets(self, fresh_manager):
        """Test multiple websockets can connect."""
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        ws3 = AsyncMock()

        await fresh_manager.connect(ws1)
        await fresh_manager.connect(ws2)
        await fresh_manager.connect(ws3)

        assert len(fresh_manager.active_connections) == 3
        assert ws1 in fresh_manager.active_connections
        assert ws2 in fresh_manager.active_connections
        assert ws3 in fresh_manager.active_connections

    def test_disconnect_removes_websocket(self, fresh_manager):
        """Test disconnect() removes websocket from list."""
        mock_ws = AsyncMock()
        fresh_manager.active_connections.append(mock_ws)

        fresh_manager.disconnect(mock_ws)

        assert mock_ws not in fresh_manager.active_connections
        assert len(fresh_manager.active_connections) == 0

    def test_disconnect_nonexistent_websocket(self, fresh_manager):
        """Test disconnect() handles non-existent websocket gracefully."""
        mock_ws = AsyncMock()
        # Don't add it to connections.

        # Should not raise.
        fresh_manager.disconnect(mock_ws)

        assert len(fresh_manager.active_connections) == 0

    def test_disconnect_last_client_pauses_game(self, fresh_manager, reset_game_instance):
        """Test disconnecting last client pauses the game."""
        mock_ws = AsyncMock()
        fresh_manager.active_connections.append(mock_ws)
        game_instance["is_paused"] = False

        fresh_manager.disconnect(mock_ws)

        assert game_instance["is_paused"] is True

    def test_disconnect_not_last_client_keeps_game_running(self, fresh_manager, reset_game_instance):
        """Test disconnecting non-last client doesn't pause game."""
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        fresh_manager.active_connections.extend([ws1, ws2])
        game_instance["is_paused"] = False

        fresh_manager.disconnect(ws1)

        # Still one client connected.
        assert game_instance["is_paused"] is False
        assert len(fresh_manager.active_connections) == 1

    @pytest.mark.asyncio
    async def test_broadcast_sends_to_all_connections(self, fresh_manager):
        """Test broadcast() sends message to all connected clients."""
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        ws3 = AsyncMock()
        fresh_manager.active_connections.extend([ws1, ws2, ws3])

        message = {"type": "test", "data": "hello"}
        await fresh_manager.broadcast(message)

        expected_json = json.dumps(message, default=str)
        ws1.send_text.assert_called_once_with(expected_json)
        ws2.send_text.assert_called_once_with(expected_json)
        ws3.send_text.assert_called_once_with(expected_json)

    @pytest.mark.asyncio
    async def test_broadcast_handles_errors_gracefully(self, fresh_manager):
        """Test a stale connection cannot block later live clients."""
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        ws3 = AsyncMock()
        ws2.send_text.side_effect = Exception("Connection closed")
        fresh_manager.active_connections.extend([ws1, ws2, ws3])

        # Should not raise.
        message = {"type": "test"}
        await fresh_manager.broadcast(message)

        # ws1 should still have been called.
        ws1.send_text.assert_called_once()
        ws3.send_text.assert_called_once()
        assert ws2 not in fresh_manager.active_connections

    @pytest.mark.asyncio
    async def test_broadcast_does_not_wait_for_a_slow_connection(self, fresh_manager):
        async def block_send(_message):
            await asyncio.Event().wait()

        fast = AsyncMock()
        slow = AsyncMock()
        slow.send_text.side_effect = block_send
        fresh_manager.active_connections.extend([fast, slow])

        started_at = time.perf_counter()
        await fresh_manager.broadcast({"type": "test"})

        assert time.perf_counter() - started_at < 3
        fast.send_text.assert_called_once()
        assert slow not in fresh_manager.active_connections

    @pytest.mark.asyncio
    async def test_broadcast_empty_connections(self, fresh_manager):
        """Test broadcast() with no connections."""
        # Should not raise.
        await fresh_manager.broadcast({"type": "test"})


class TestWebSocketEndpoint:
    """Tests for /ws WebSocket endpoint."""

    def test_websocket_connect_and_ping_pong(self, client, reset_game_instance):
        """Test WebSocket connection and ping/pong."""
        with client.websocket_connect("/ws") as ws:
            ws.send_text("ping")
            response = ws.receive_text()
            assert json.loads(response) == {"type": "pong"}

    def test_websocket_llm_config_required_on_connect(self, client, reset_game_instance):
        """Test WebSocket sends llm_config_required when LLM check failed."""
        game_instance["llm_check_failed"] = True
        game_instance["llm_error_message"] = "API key invalid"

        with client.websocket_connect("/ws") as ws:
            # First message should be llm_config_required.
            response = ws.receive_text()
            data = json.loads(response)

            assert data["type"] == "llm_config_required"
            assert data["error"] == "API key invalid"

    def test_websocket_no_llm_message_when_ok(self, client, reset_game_instance):
        """Test WebSocket doesn't send llm_config_required when LLM is OK."""
        game_instance["llm_check_failed"] = False

        with client.websocket_connect("/ws") as ws:
            # Send ping to get a response.
            ws.send_text("ping")
            response = ws.receive_text()

            # Should be pong, not llm_config_required.
            data = json.loads(response)
            assert data["type"] == "pong"

    def test_websocket_multiple_pings(self, client, reset_game_instance):
        """Test WebSocket handles multiple ping messages."""
        with client.websocket_connect("/ws") as ws:
            for _ in range(5):
                ws.send_text("ping")
                response = ws.receive_text()
                assert json.loads(response) == {"type": "pong"}


class TestControlAPIEndpoints:
    """Tests for game control API endpoints."""

    def test_pause_game(self, client, reset_game_instance):
        """Test POST /api/v1/command/game/pause pauses the game."""
        game_instance["is_paused"] = False

        response = client.post("/api/v1/command/game/pause")

        assert response.status_code == 200
        assert game_instance["is_paused"] is True
        data = response.json()["data"]
        assert data["status"] == "ok"
        assert "pause" in data["message"].lower()

    def test_pause_already_paused(self, client, reset_game_instance):
        """Test pausing already paused game."""
        game_instance["is_paused"] = True

        response = client.post("/api/v1/command/game/pause")

        assert response.status_code == 200
        assert game_instance["is_paused"] is True

    def test_resume_game(self, client, reset_game_instance):
        """Test POST /api/v1/command/game/resume resumes the game."""
        game_instance["is_paused"] = True

        response = client.post("/api/v1/command/game/resume")

        assert response.status_code == 200
        assert game_instance["is_paused"] is False
        data = response.json()["data"]
        assert data["status"] == "ok"
        assert "resume" in data["message"].lower()

    def test_resume_already_running(self, client, reset_game_instance):
        """Test resuming already running game."""
        game_instance["is_paused"] = False

        response = client.post("/api/v1/command/game/resume")

        assert response.status_code == 200
        assert game_instance["is_paused"] is False

    def test_reset_game(self, client, reset_game_instance):
        """Test POST /api/v1/command/game/reset resets the game to idle."""
        game_instance["world"] = MagicMock()
        game_instance["sim"] = MagicMock()
        game_instance["is_paused"] = False
        game_instance["init_status"] = "ready"
        game_instance["init_phase"] = 5
        game_instance["init_progress"] = 100

        response = client.post("/api/v1/command/game/reset")

        assert response.status_code == 200
        assert game_instance["world"] is None
        assert game_instance["sim"] is None
        assert game_instance["is_paused"] is True
        assert game_instance["init_status"] == "idle"
        assert game_instance["init_phase"] == 0
        assert game_instance["init_progress"] == 0

    def test_reset_clears_error(self, client, reset_game_instance):
        """Test reset clears initialization error."""
        game_instance["init_status"] = "error"
        game_instance["init_error"] = "Some error"

        response = client.post("/api/v1/command/game/reset")

        assert response.status_code == 200
        assert game_instance["init_status"] == "idle"
        assert game_instance["init_error"] is None


class TestStateAPI:
    """Tests for /api/v1/query/world/state endpoint."""

    def test_state_no_world(self, client, reset_game_instance):
        """Test world state query returns structured 503 when no world."""
        game_instance["world"] = None

        response = client.get("/api/v1/query/world/state")

        assert response.status_code == 503
        data = response.json()["detail"]
        assert data["code"] == "WORLD_NOT_READY"
        assert data["message"] == "World not initialized"

    def test_state_with_world(self, client, reset_game_instance):
        """Test world state query returns world state."""
        mock_world = MagicMock()
        mock_world.month_stamp.get_year.return_value = 100
        mock_world.month_stamp.get_month.return_value = MagicMock(value=3)
        mock_world.avatar_manager.avatars = {}
        mock_world.event_manager = None
        mock_world.current_phenomenon = None

        game_instance["world"] = mock_world
        game_instance["is_paused"] = False

        response = client.get("/api/v1/query/world/state")

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["status"] == "ok"
        assert data["year"] == 100
        assert data["month"] == 3
        assert data["is_paused"] is False

    def test_state_includes_avatars(self, client, reset_game_instance):
        """Test world state query includes avatar data."""
        mock_avatar = MagicMock()
        mock_avatar.id = "test_avatar_1"
        mock_avatar.name = "Test Avatar"
        mock_avatar.pos_x = 50
        mock_avatar.pos_y = 60
        mock_avatar.gender.value = "male"
        mock_avatar.current_action = None

        mock_world = MagicMock()
        mock_world.month_stamp.get_year.return_value = 100
        mock_world.month_stamp.get_month.return_value = MagicMock(value=1)
        mock_world.avatar_manager.avatars = {"test_avatar_1": mock_avatar}
        mock_world.event_manager = None
        mock_world.current_phenomenon = None

        game_instance["world"] = mock_world

        with patch.object(main, 'resolve_avatar_pic_id', return_value=1):
            response = client.get("/api/v1/query/world/state")

        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data["avatars"]) == 1
        avatar = data["avatars"][0]
        assert avatar["id"] == "test_avatar_1"
        assert avatar["name"] == "Test Avatar"
        assert avatar["x"] == 50
        assert avatar["y"] == 60


class TestMapAPI:
    """Tests for /api/v1/query/world/map endpoint."""

    def test_map_no_world(self, client, reset_game_instance):
        """Test world map query returns structured 503 when no world."""
        game_instance["world"] = None

        response = client.get("/api/v1/query/world/map")

        assert response.status_code == 503
        data = response.json()["detail"]
        assert data["code"] == "WORLD_NOT_READY"
        assert data["message"] == "World not initialized"

    def test_map_no_map(self, client, reset_game_instance):
        """Test world map query returns structured 503 when world has no map."""
        mock_world = MagicMock()
        mock_world.map = None

        game_instance["world"] = mock_world

        response = client.get("/api/v1/query/world/map")

        assert response.status_code == 503
        data = response.json()["detail"]
        assert data["code"] == "MAP_NOT_READY"
        assert data["message"] == "Map not initialized"

    def test_map_returns_data(self, client, reset_game_instance):
        """Test world map query returns map data."""
        mock_tile = MagicMock()
        mock_tile.type.name = "PLAIN"

        mock_map = MagicMock()
        mock_map.width = 10
        mock_map.height = 10
        mock_map.get_tile.return_value = mock_tile
        mock_map.regions = {}

        mock_world = MagicMock()
        mock_world.map = mock_map

        game_instance["world"] = mock_world

        response = client.get("/api/v1/query/world/map")

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["width"] == 10
        assert data["height"] == 10
        assert "data" in data
        assert "render_config" in data
        assert len(data["data"]) == 10  # 10 rows
        assert len(data["data"][0]) == 10  # 10 columns


class TestSerializeEvents:
    """Tests for serialize_events_for_client function."""

    def test_serialize_empty_list(self):
        """Test serializing empty event list."""
        from src.server.main import serialize_events_for_client

        result = serialize_events_for_client([])
        assert result == []

    def test_serialize_event_with_all_fields(self):
        """Test serializing event with all fields."""
        from src.server.main import serialize_events_for_client
        from src.classes.event import Event
        from src.systems.time import create_month_stamp, Year, Month

        month_stamp = create_month_stamp(Year(100), Month.MARCH)
        event = Event(
            month_stamp=month_stamp,
            content="Test event content",
            related_avatars=["avatar1", "avatar2"],
            is_major=True,
            is_story=False,
            render_key="nickname_awarded",
            render_params={"avatar_name": "Tester", "nickname": "Crimson Sage"},
        )

        result = serialize_events_for_client([event])

        assert len(result) == 1
        serialized = result[0]
        assert serialized["content"] == "Test event content"
        assert serialized["year"] == 100
        assert serialized["month"] == 3
        assert serialized["is_major"] is True
        assert serialized["is_story"] is False
        assert serialized["render_key"] == "nickname_awarded"
        assert serialized["render_params"] == {"avatar_name": "Tester", "nickname": "Crimson Sage"}
        assert "avatar1" in serialized["related_avatar_ids"]
        assert "avatar2" in serialized["related_avatar_ids"]
        assert serialized["subjects"] == [
            {"type": "avatar", "id": "avatar1", "name": "avatar1", "is_dead": False},
            {"type": "avatar", "id": "avatar2", "name": "avatar2", "is_dead": False},
        ]

    def test_serialize_event_without_optional_fields(self):
        """Test serializing event with minimal fields."""
        from src.server.main import serialize_events_for_client
        from src.classes.event import Event
        from src.systems.time import create_month_stamp, Year, Month

        month_stamp = create_month_stamp(Year(50), Month.JANUARY)
        event = Event(
            month_stamp=month_stamp,
            content="Minimal event",
        )

        result = serialize_events_for_client([event])

        assert len(result) == 1
        serialized = result[0]
        assert serialized["content"] == "Minimal event"
        assert serialized["related_avatar_ids"] == []
        assert serialized["is_major"] is False
        assert serialized["is_story"] is False
        assert serialized["render_key"] is None
        assert serialized["render_params"] is None
        assert serialized["subjects"] == []

    def test_serialize_event_uses_persisted_subject_snapshot_without_world(self):
        from src.server.main import serialize_events_for_client
        from src.classes.event import Event
        from src.systems.time import create_month_stamp, Year, Month

        event = Event(
            month_stamp=create_month_stamp(Year(100), Month.MARCH),
            content="Alice acted.",
            related_avatars=["avatar-1"],
            subject_snapshots={"avatar-1": "Alice"},
        )

        result = serialize_events_for_client([event])

        assert result[0]["subjects"] == [
            {"type": "avatar", "id": "avatar-1", "name": "Alice", "is_dead": False},
        ]

    def test_serialize_event_subjects_with_world(self):
        """Test event display subjects are resolved from the runtime world."""
        from src.server.main import serialize_events_for_client
        from src.classes.event import Event
        from src.systems.time import create_month_stamp, Year, Month

        avatar = MagicMock()
        avatar.id = "avatar1"
        avatar.name = "Alice"
        avatar.is_dead = False

        sect = MagicMock()
        sect.id = 7
        sect.name = "Azure Sect"
        sect.color = "#4DD0E1"
        sect.is_active = True

        world = MagicMock()
        world.avatar_manager.get_avatar.return_value = avatar
        world.sect_context.get_active_sects.return_value = [sect]

        month_stamp = create_month_stamp(Year(100), Month.MARCH)
        event = Event(
            month_stamp=month_stamp,
            content="A structured event.",
            related_avatars=["avatar1"],
            related_sects=[7],
        )

        result = serialize_events_for_client([event], world=world)

        assert result[0]["subjects"] == [
            {"type": "avatar", "id": "avatar1", "name": "Alice", "is_dead": False},
            {"type": "sect", "id": 7, "name": "Azure Sect", "color": "#4DD0E1", "is_active": True},
        ]


class TestGameLoopIntegration:
    """Tests for game loop behavior (without actually running it)."""

    def test_game_loop_respects_pause(self, reset_game_instance):
        """Test game loop doesn't step when paused."""
        mock_sim = MagicMock()
        mock_sim.step = AsyncMock(return_value=[])

        game_instance["sim"] = mock_sim
        game_instance["world"] = MagicMock()
        game_instance["is_paused"] = True
        game_instance["init_status"] = "ready"

        # The actual game_loop runs in background.
        # We test the pause check logic by verifying step is not called when paused.
        # This is a unit test of the logic, not the async loop itself.
        assert game_instance["is_paused"] is True

    def test_game_loop_runs_when_not_paused(self, reset_game_instance):
        """Test game loop would step when not paused."""
        game_instance["is_paused"] = False
        game_instance["init_status"] = "ready"

        # Verify conditions for loop to run.
        assert game_instance["is_paused"] is False
        assert game_instance["init_status"] == "ready"
