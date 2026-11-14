"""Reads live telemetry from iRacing (via pyirsdk) into a simple Snapshot.

Everything downstream only ever sees Snapshot objects, so the fake test race
can produce exactly the same thing without iRacing running.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

# iRacing SessionState values
STATE_INVALID, STATE_GET_IN_CAR, STATE_WARMUP, STATE_PARADE, STATE_RACING, STATE_CHECKERED, STATE_COOL_DOWN = range(7)

# iRacing SessionFlags bits
FLAG_CHECKERED = 0x0001
FLAG_WHITE = 0x0002
FLAG_GREEN = 0x0004


@dataclass
class Snapshot:
    """One moment of telemetry, reduced to what the commentator cares about."""

    session_time: float = 0.0
    session_type: str = "Race"         # "Race", "Practice", "Qualify", ...
    session_state: int = STATE_INVALID
    session_flags: int = 0
    track_name: str = ""
    car_name: str = ""
    driver_name: str = ""
    lap: int = 0                        # lap currently being driven
    laps_completed: int = 0
    total_laps: Optional[int] = None    # None for timed races
    laps_remaining: Optional[int] = None
    time_remaining: Optional[float] = None
    position: int = 0                   # overall position (0 = not classified yet)
    total_cars: int = 0
    gap_ahead: Optional[float] = None   # seconds to the car in front
    gap_behind: Optional[float] = None  # seconds to the car behind
    car_ahead_name: str = ""
    car_behind_name: str = ""
    last_lap_time: Optional[float] = None
    best_lap_time: Optional[float] = None
    incidents: int = 0
    on_pit_road: bool = False
    starting_position: Optional[int] = None
    extra: dict = field(default_factory=dict)

    @property
    def is_race(self) -> bool:
        return "race" in (self.session_type or "").lower()


def _valid_time(t) -> Optional[float]:
    try:
        t = float(t)
    except (TypeError, ValueError):
        return None
    return t if t > 0 else None


class IRacingSource:
    """Connects to iRacing, survives it not running / restarting / disconnecting."""

    RETRY_SECONDS = 2.0

    def __init__(self, driver_name_override: str = "") -> None:
        import irsdk  # imported here so test mode works without pyirsdk

        self._irsdk = irsdk
        self.ir = irsdk.IRSDK()
        self.connected = False
        self._last_attempt = 0.0
        self._session_info_update = -1
        self._static: dict = {}
        self._driver_override = driver_name_override
        self._lap_estimate: Optional[float] = None

    # -- connection handling ------------------------------------------------
    def _ensure_connected(self) -> bool:
        if self.connected and not (self.ir.is_initialized and self.ir.is_connected):
            print("[iracing] Disconnected from iRacing - waiting for it to come back...")
            self._disconnect()
        if self.connected:
            return True
        now = time.monotonic()
        if now - self._last_attempt < self.RETRY_SECONDS:
            return False
        self._last_attempt = now
        try:
            if self.ir.startup() and self.ir.is_initialized and self.ir.is_connected:
                self.connected = True
                self._session_info_update = -1
                print("[iracing] Connected to iRacing.")
        except Exception as exc:  # pyirsdk raises odd things when the sim is closing
            print(f"[iracing] Connect attempt failed: {exc}")
            self._disconnect()
        return self.connected

    def _disconnect(self) -> None:
        self.connected = False
        try:
            self.ir.shutdown()
        except Exception:
            pass

    def close(self) -> None:
        self._disconnect()

    # -- session info (track, car, drivers) ----------------------------------
    def _refresh_static(self) -> None:
        update = self.ir.session_info_update
        if update == self._session_info_update:
            return
        self._session_info_update = update
        static: dict = {"drivers": {}}
        weekend = self.ir["WeekendInfo"] or {}
        static["track_name"] = weekend.get("TrackDisplayName", "") or weekend.get("TrackName", "")
        driver_info = self.ir["DriverInfo"] or {}
        player_idx = driver_info.get("DriverCarIdx", 0)
        static["player_idx"] = player_idx
        self._lap_estimate = _valid_time(driver_info.get("DriverCarEstLapTime"))
        for d in driver_info.get("Drivers", []) or []:
            if d.get("CarIsPaceCar") or d.get("IsSpectator"):
                continue
            static["drivers"][d.get("CarIdx")] = {
                "name": d.get("UserName", ""),
                "car": d.get("CarScreenName", ""),
            }
        me = static["drivers"].get(player_idx, {})
        static["car_name"] = me.get("car", "")
        static["driver_name"] = self._driver_override or me.get("name", "")

        static["session_type"] = "Race"
        static["total_laps"] = None
        static["starting_position"] = None
        session_info = self.ir["SessionInfo"] or {}
        session_num = self.ir["SessionNum"]
        for s in session_info.get("Sessions", []) or []:
            if s.get("SessionNum") == session_num:
                static["session_type"] = s.get("SessionType", "Race")
                laps = s.get("SessionLaps")
                static["total_laps"] = int(laps) if str(laps).isdigit() else None
        for q in (self.ir["QualifyResultsInfo"] or {}).get("Results", []) or []:
            if q.get("CarIdx") == player_idx:
                static["starting_position"] = int(q.get("Position", 0)) + 1
        self._static = static

    # -- the main read --------------------------------------------------------
    def read(self) -> Optional[Snapshot]:
        """Return a Snapshot, or None if iRacing isn't available right now."""
        if not self._ensure_connected():
            return None
        try:
            self.ir.freeze_var_buffer_latest()
            self._refresh_static()
            return self._build_snapshot()
        except Exception as exc:
            print(f"[iracing] Telemetry read error ({exc}) - reconnecting.")
            self._disconnect()
            return None
        finally:
            try:
                self.ir.unfreeze_var_buffer_latest()
            except Exception:
                pass

    def _build_snapshot(self) -> Snapshot:
        ir, st = self.ir, self._static
        me = st.get("player_idx", 0)
        positions = ir["CarIdxPosition"] or []
        laps_done = ir["CarIdxLapCompleted"] or []
        lap_pct = ir["CarIdxLapDistPct"] or []

        drivers = st.get("drivers", {})
        my_pos = positions[me] if me < len(positions) else 0
        snap = Snapshot(
            session_time=float(ir["SessionTime"] or 0.0),
            session_type=st.get("session_type", "Race"),
            session_state=int(ir["SessionState"] or 0),
            session_flags=int(ir["SessionFlags"] or 0),
            track_name=st.get("track_name", ""),
            car_name=st.get("car_name", ""),
            driver_name=st.get("driver_name", ""),
            lap=int(ir["Lap"] or 0),
            laps_completed=int(ir["LapCompleted"] or 0),
            total_laps=st.get("total_laps"),
            position=int(my_pos or 0),
            total_cars=len(drivers),
            last_lap_time=_valid_time(ir["LapLastLapTime"]),
            best_lap_time=_valid_time(ir["LapBestLapTime"]),
            incidents=int(ir["PlayerCarMyIncidentCount"] or 0),
            on_pit_road=bool(ir["OnPitRoad"]),
            starting_position=st.get("starting_position"),
        )
        remain = ir["SessionLapsRemainEx"]
        if isinstance(remain, int) and 0 <= remain < 10000:
            snap.laps_remaining = remain
        t_remain = ir["SessionTimeRemain"]
        if isinstance(t_remain, (int, float)) and 0 <= t_remain < 86400 * 2:
            snap.time_remaining = float(t_remain)

        # Gaps: race distance between us and the cars one place ahead / behind,
        # converted to seconds with an estimated lap time.
        lap_time = snap.best_lap_time or snap.last_lap_time or self._lap_estimate or 90.0
        if my_pos and me < len(laps_done) and me < len(lap_pct):
            my_progress = laps_done[me] + lap_pct[me]
            for idx, pos in enumerate(positions):
                if idx not in drivers or idx >= len(laps_done) or lap_pct[idx] < 0:
                    continue
                progress = laps_done[idx] + lap_pct[idx]
                if pos == my_pos - 1:
                    snap.gap_ahead = max(0.0, (progress - my_progress) * lap_time)
                    snap.car_ahead_name = drivers[idx]["name"]
                elif pos == my_pos + 1:
                    snap.gap_behind = max(0.0, (my_progress - progress) * lap_time)
                    snap.car_behind_name = drivers[idx]["name"]
        return snap
