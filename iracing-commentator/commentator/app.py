"""Start-up and the main telemetry loop."""

from __future__ import annotations

import argparse
import sys
import time

from .config import load_config
from .personalities import personality_names


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="main.py", description="The Beep Test - live AI race commentator for iRacing")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--test", action="store_true", help="replay a pretend race (no iRacing needed)")
    mode.add_argument("--voice-test", action="store_true", help="speak a sample of every event type")
    mode.add_argument("--list-devices", action="store_true", help="list audio output devices and exit")
    p.add_argument("--ai", action="store_true", help="voice test: have the AI write the sample lines")
    p.add_argument("--only", help="voice test: only event types containing this word, e.g. incident")
    p.add_argument("--speed", type=float, default=1.0, help="test mode: play the fake race faster, e.g. 1.5")
    p.add_argument("--personality", choices=personality_names(), help="override config personality")
    p.add_argument("--voice", help="override the edge-tts voice, e.g. en-GB-ThomasNeural")
    p.add_argument("--silent", action="store_true", help="don't play audio, just print lines")
    p.add_argument("--config", help="path to a different config.yaml")
    return p.parse_args(argv)


class _SilentPlayer:
    available = True

    def play(self, samples, sample_rate):
        time.sleep(len(samples) / float(sample_rate))  # behave as if speaking

    def stop(self):
        pass


def main(argv=None) -> int:
    args = parse_args(argv)
    cfg = load_config(args.config)
    if args.personality:
        cfg["commentator"]["personality"] = args.personality
    if args.voice:
        cfg["tts"]["edge"]["voice"] = args.voice

    from .audio import AudioPlayer, print_output_devices

    if args.list_devices:
        print_output_devices()
        return 0

    print(f"\n=== {cfg.get('channel_name')} - AI Race Commentator ===")
    print(f"Personality: {cfg['commentator']['personality']}   Voice engine: {cfg['tts']['engine']}")
    player = _SilentPlayer() if args.silent else AudioPlayer(cfg["audio"])

    from .tts import make_tts

    tts = make_tts(cfg)

    from .llm import LineWriter

    if args.voice_test:
        from .voice_test import run_voice_test

        run_voice_test(cfg, tts, player, LineWriter(cfg) if args.ai else None, args.only)
        return 0

    from .detector import EventDetector
    from .director import Director
    from .ducking import Ducker
    from .hotkeys import register_hotkeys
    from .line_log import LineLog

    writer = LineWriter(cfg)
    detector = EventDetector(cfg)
    director = Director(cfg, writer, tts, player, Ducker(cfg["ducking"]), LineLog(cfg["logging"]),
                        on_spoken=detector.note_activity)

    if args.test:
        from .fake_race import FakeRaceSource

        source = FakeRaceSource(cfg.get("driver_name") or "", speed=args.speed)
        # shorter quiet period so you hear some colour commentary in the demo
        detector.quiet_period = min(detector.quiet_period, 20)
        detector._next_quiet = detector.quiet_period
        print("[test] Running a pretend race at Okayama (about 3.5 minutes). Ctrl+C to stop.")
    else:
        from .telemetry import IRacingSource

        try:
            source = IRacingSource(cfg.get("driver_name") or "")
        except ImportError:
            print("pyirsdk isn't installed. Run: pip install -r requirements.txt")
            return 1
        print("[iracing] Waiting for iRacing... (start a session; this window can stay open)")

    last_snap = {"s": None}

    def force_line():
        director.submit(detector.force_event(last_snap["s"], time.monotonic()))

    register_hotkeys(cfg["hotkeys"], director.toggle_mute, force_line)
    director.start()

    period = 1.0 / max(1, int(cfg["detection"].get("poll_hz", 10)))
    was_connected = False
    try:
        while True:
            t0 = time.monotonic()
            snap = source.read()
            if snap is not None:
                if not was_connected:
                    writer.set_driver(snap.driver_name)
                    print(f"[race] {snap.session_type} at {snap.track_name or '?'} in the "
                          f"{snap.car_name or '?'} - {snap.total_cars} cars")
                    was_connected = True
                last_snap["s"] = snap
                director.session_time = snap.session_time
                for event in detector.update(snap, time.monotonic()):
                    print(f"[event] {event}")
                    director.submit(event)
            elif was_connected:
                was_connected = False
                detector.reset()
            if args.test and source.finished:
                time.sleep(6)  # let the last line finish
                break
            time.sleep(max(0.0, period - (time.monotonic() - t0)))
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        director.stop()
        source.close()
        s = director.stats
        print(f"Lines spoken: {s['spoken']}   dropped: {s['dropped']}   stale: {s['stale']}")
        if director.log:
            print(f"Log saved to: {director.log.path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
