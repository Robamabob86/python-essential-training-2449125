# The Beep Test – AI Race Commentator for iRacing

A live, British, slightly-too-honest commentator for your iRacing streams.

While you race, it reads iRacing's telemetry 10 times a second, spots the moments that
matter (overtakes, spins, contact, personal bests, battles, pit stops, the flag), has
Claude write a short punchy line about it, and speaks the line **through its own audio
device**. That way OBS records the commentator on **its own track**, so you can turn it up,
down or off when editing.

```
iRacing ──telemetry──▶ event detector ──▶ director (priority, cooldown, no stale lines)
                                             │
                               Claude writes one line (≤ 20 words)
                                             │
                          voice (edge-tts / ElevenLabs) ──▶ "CABLE Input" ──▶ OBS track
```

You get two commentators, which you pick in `config.yaml`:

| `personality` | Who it is |
|---|---|
| `pro` | A calm-then-erupting Sky F1-style lead commentator: "Lights out and away we go!" |
| `cheeky` | A sarcastic British pundit who roasts you for being a rookie, but is clearly on your side: "The grass is NOT a racing line... that's twice now!" |

---

## What you need

- A Windows 10 or 11 PC running iRacing and OBS
- **Python 3.11 or newer** (free)
- An **Anthropic API key** (pay as you go, roughly a penny per line. See [Costs](#costs))
- **VB-Audio Virtual Cable** (free). It gives the commentator its own "speaker" for OBS to record.
- An internet connection (for the AI and the free voices)

---

## Setup, step by step

### 1. Install Python

1. Go to <https://www.python.org/downloads/> and download the latest Python 3 for Windows.
2. Run the installer. **On the first screen, tick "Add python.exe to PATH"**, then click *Install Now*.

### 2. Get the commentator files

Download this project (on GitHub: **Code ▸ Download ZIP**) and unzip it somewhere easy,
e.g. `Documents\iracing-commentator`. The folder you want is the one that has `main.py` in it.

### 3. Run the one-time setup

Double-click **`setup.bat`**. It creates a private Python environment in the folder and
installs everything. This takes a minute or two. When it says *Setup done!* you're ready.

### 4. Add your Anthropic API key

1. Go to <https://console.anthropic.com/>, sign up, and add some credit under *Billing*
   ($5 lasts a long time).
2. Under *API Keys*, click **Create Key** and copy it (it starts with `sk-ant-`).
3. In the commentator folder, open the file **`.env`** with Notepad (setup.bat created it).
   Paste your key after `ANTHROPIC_API_KEY=` and save.

> Keep `.env` private. Don't show it on stream and don't upload it anywhere.
> No key yet? It still works, using built-in canned lines instead of the AI.

### 5. Install VB-Audio Virtual Cable

1. Download it from <https://vb-audio.com/Cable/> (the *VBCABLE_Driver_Pack* ZIP).
2. Unzip it, right-click **`VBCABLE_Setup_x64.exe`** ▸ *Run as administrator* ▸ *Install Driver*.
3. **Restart your PC.**
4. You now have a playback device called **"CABLE Input (VB-Audio Virtual Cable)"**.
   Windows sometimes makes it your default speaker after installing. If your sound disappears,
   open *Settings ▸ System ▸ Sound* and set your normal headphones/speakers back as the output.

`config.yaml` already points the commentator at it (`output_device: "CABLE Input"`). To check,
double-click **`list_devices.bat`**. You'll see every output device, and the one marked
`<-- COMMENTATOR` is the one it will use.

### 6. Tune the voice (voice test)

Double-click **`voice_test.bat`**. It speaks a sample line for every type of moment (start,
overtake, spin, PB, finish...) with that moment's own speed and pitch.

> Because the voice goes to the virtual cable, **you won't hear it in your headphones yet**.
> For the test, either set up OBS monitoring first (step 8), or temporarily set
> `output_device: ""` in `config.yaml` to use your normal speakers.

Things to try in `config.yaml` under `tts:`:

- `voice:` – `en-GB-RyanNeural` (default, energetic) or `en-GB-ThomasNeural`
- `base_rate:` – overall speed, e.g. `"+12%"` for faster, `"+0%"` for normal
- `base_pitch:` – e.g. `"+3Hz"` for brighter
- `prosody:` – per-moment tweaks. Overtakes are already faster and higher than quiet laps.

Handy extras (type these in a Command Prompt in the folder, after `.venv\Scripts\activate`):

```
python main.py --voice-test --voice en-GB-ThomasNeural   # try another voice
python main.py --voice-test --ai --personality cheeky    # let the AI write the samples
python main.py --voice-test --only incident              # just one kind of moment
```

### 7. Try a pretend race (test mode)

Double-click **`test_mode.bat`**. It plays a scripted 3½-minute race at Okayama (start,
overtakes, a spin, contact, a PB, a pit stop, a battle, the last lap and the flag) through
the real AI and voice, **without iRacing running**. You can also run it at speed:
`python main.py --test --speed 1.5`.

### 8. Set up OBS: the commentator on its own track

**a) Add the commentator as a source**

1. In OBS, in the **Sources** box of your scene, click **+** ▸ **Audio Output Capture**.
2. Name it `Commentator` ▸ OK.
3. For **Device**, choose **CABLE Input (VB-Audio Virtual Cable)** ▸ OK.

A *Commentator* meter now appears in the Audio Mixer and bounces when it talks
(run `test_mode.bat` to check).

**b) Hear it yourself while racing (optional)**

In the Audio Mixer, click the **⋮** (or ⚙) next to *Commentator* ▸ **Advanced Audio Properties**.
Set **Audio Monitoring** to **Monitor and Output**. Then in *Settings ▸ Audio ▸ Advanced* set
**Monitoring Device** to your headphones.

**c) Put it on its own recording track**

Still in **Advanced Audio Properties**, you'll see tick boxes **1–6** (tracks) for every source.
A good layout:

| Source | Tracks ticked |
|---|---|
| Desktop Audio (game) | 1, 2 |
| Mic | 1, 3 |
| Commentator | 1, 4 |

Track 1 is the full mix (for the stream). Tracks 2–4 are each thing on its own (for editing).

**d) Record all the tracks**

1. *Settings ▸ Output*, set **Output Mode** to **Advanced**.
2. **Recording** tab: under **Audio Track**, tick **1, 2, 3 and 4**.
   (Use MKV or *Hybrid MP4* as the recording format so a crash doesn't lose the file. You can
   *File ▸ Remux* to MP4 afterwards.)
3. **Streaming** tab: **Audio Track 1**, so viewers hear everything mixed together.
   If you *don't* want the commentator on the live stream, untick track 1 for the Commentator
   source.

In your video editor (DaVinci Resolve, Premiere and so on), the recording now has four separate
audio tracks. Track 4 is just the commentator.

> Don't also set `also_play_on_default: true` if OBS captures your Desktop Audio, or the
> commentator will be recorded twice (once on track 4 and once inside the game audio).

### 9. Race!

1. Start iRacing and OBS.
2. Double-click **`start_commentator.bat`**. It's fine to start it before iRacing. It waits,
   connects when you load into a session, and copes if iRacing closes or crashes.
3. Drive. Press **Ctrl+C** in the commentator window (or close it) when you're done.

**Hotkeys** (they work while iRacing is focused; change them in `config.yaml`):

| Keys | Does |
|---|---|
| `Ctrl+Shift+M` | Mute / unmute the commentator (stops it mid-sentence) |
| `Ctrl+Shift+L` | Force a line right now, about the current race state |

---

## How it decides what to say

**Moments it detects**

| Moment | Priority |
|---|---|
| Chequered flag (with finishing position and places gained or lost) | 100 |
| Incident points (1x off-track, 2x loss of control, 4x contact) | 90 |
| Position gained or lost (with the new position) | 80 |
| Race start (green flag) | 75 |
| Final lap (white flag) | 70 |
| Battle building ahead, or pressure from behind (gap closing fast, under 1 s) | 60 |
| Pit entry or exit | 50 |
| Personal best lap | 45 |
| Lap much slower than your average | 40 |
| Colour commentary after a long quiet spell | 10 |

Every moment carries the lap, position, total cars, gaps, last and best lap, incidents, track
and car to the AI as structured data, along with ready-made spoken phrases ("fifth",
"half a second", "one thirty-four point eight") so numbers never sound robotic. A final
safety net rewrites any stray "P5" or "0.5s" before the voice reads it.

**Rules**

- **One line per moment**, 20 words at most.
- **Cooldown** (`cooldown_seconds: 8`): after a line, small stuff is dropped for 8 seconds.
  Moments with priority 70 or more (`cooldown_bypass_priority`) can still get in, after a short
  `min_gap_seconds`.
- **Only the most important waiting moment is kept.** If an overtake happens while a PB line is
  being written, the overtake wins.
- **Nothing stale.** If a line isn't ready within `max_line_age_seconds: 4` of the moment
  it describes, it's thrown away instead of being said late.
- **Memory.** The last 10 lines go back to the AI each time, so it doesn't repeat itself, avoids
  opens two lines the same way, and can call back to earlier moments ("that's twice now!").

---

## Optional upgrades

### ElevenLabs voices (the most natural sound)

1. Make an account at <https://elevenlabs.io>, copy your API key into `.env` as
   `ELEVENLABS_API_KEY=...`.
2. Pick a voice in their Voice Library and copy its **Voice ID** into `config.yaml ▸ tts ▸
   elevenlabs ▸ voice_id`.
3. Set `tts ▸ engine: elevenlabs`.

The default settings are tuned for an excitable commentator: `stability: 0.3` (lots of
variation) and `style: 0.75` (lots of expression). If it gets too wild, raise stability towards
0.5. If ElevenLabs fails for any reason, it falls back to edge-tts automatically.

### Duck the game while it talks

Set `ducking ▸ enabled: true` to turn iRacing's volume down to 35% while the commentator speaks,
then back up afterwards.

### Faster lines

The default model, `claude-opus-5-5` at `effort: low`, writes the best lines. If you often see
`skipped (stale...)` in the window, set `llm ▸ model: claude-haiku-5-5`, which is much quicker
and cheaper.

---

## Logs for editing and Shorts

Every spoken line is saved in `logs\commentary_<date>_<time>.txt`:

```
[20:14:03] +0:12:31.4 | race 11:58.20 | incident        | Oh dear. The grass is NOT a racing line... that's twice now!
```

That's the wall-clock time, the time since you started the commentator (start it when you
start recording and this matches your video timeline), the iRacing session time, the moment
type and the line. Skipped lines are logged too, marked `(skipped...)`. Search the file for
`incident` or `position_gained` to find Shorts material fast.

Set `logging ▸ save_audio_clips: true` to also save every line as a `.wav` file.

---

## Costs

Each line is one small Claude request: about 2,000 tokens in and a few hundred out. With
`claude-opus-5-5` ($4 / $20 per million tokens) that's roughly **1 cent per line**. A 30-minute
race with about 80–100 lines costs about **$1**. `claude-haiku-5-5` costs a small fraction of that.
The edge-tts voices are free.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `'python' is not recognized` | Reinstall Python and tick **Add python.exe to PATH**. |
| `WARNING: no output device matching 'CABLE Input'` | VB-Cable isn't installed, or the PC hasn't been restarted since. Run `list_devices.bat` and copy part of the right name into `output_device`. |
| OBS meter doesn't move | Check the Audio Output Capture device is *CABLE Input*, then run `test_mode.bat`. |
| I can't hear it | That's expected. It's going to the cable. See step 8b, or set `also_play_on_default: true`. |
| `No ANTHROPIC_API_KEY in .env` | The `.env` file is missing or the key isn't pasted in. Check it's called `.env`, not `.env.txt`. In Explorer, turn on *View ▸ File name extensions*. |
| `API key rejected` | Make a new key at console.anthropic.com and check you have credit. |
| Lots of `skipped (stale...)` | The AI or voice is slow. Try `claude-haiku-5-5`, or raise `max_line_age_seconds` to 5. |
| `[tts] Speech failed` | edge-tts needs internet. Check your connection or firewall. |
| Hotkeys don't work | Some PCs need the commentator *Run as administrator*. Or change the key combo in config. |
| Talks too much or too little | Raise or lower `cooldown_seconds` and `quiet_period_seconds`. |
| Wrong name | Set `driver_name:` in `config.yaml`. Otherwise it uses your iRacing name. |

---

## Project layout

```
iracing-commentator/
├─ main.py                  start here: python main.py [--test | --voice-test | --list-devices]
├─ config.yaml              all your settings
├─ .env.example             copy to .env, add API keys
├─ requirements.txt
├─ setup.bat, start_commentator.bat, test_mode.bat, voice_test.bat, list_devices.bat
├─ commentator/
│  ├─ app.py                start-up + main 10 Hz loop
│  ├─ telemetry.py          reads iRacing (pyirsdk), survives disconnects
│  ├─ fake_race.py          the scripted test race
│  ├─ detector.py           turns telemetry into race moments
│  ├─ events.py             moment types + priorities
│  ├─ director.py           priority, cooldown, stale-line rules, memory
│  ├─ llm.py                Claude line writer (+ canned fallback)
│  ├─ personalities.py      the "pro" and "cheeky" system prompts
│  ├─ numbers.py            "P5" -> "fifth", 0.48 -> "half a second"
│  ├─ tts/                  edge-tts and ElevenLabs voices (add more by subclassing TTSEngine)
│  ├─ audio.py              output device selection + playback
│  ├─ ducking.py, hotkeys.py, line_log.py, voice_test.py, fallback_lines.py
└─ tests/                   python -m pytest
```

All command-line options: `python main.py --help`.

For developers: `pip install -r requirements.txt`, then `python -m pytest` runs the tests
(they need no iRacing, audio device or API key).
