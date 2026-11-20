# Audio pipeline and timing

Audio arrives from the server in bursts and leaves at exactly the radio's pace. The transmitter
sits in between, holding the burst and releasing one 10 ms frame at a time.

## One format end to end

The player tells Sendspin it supports exactly one format, and the broadcast carries the same, so
there is no resampling or channel mixing.

| | |
| --- | --- |
| Input | PCM, 48 000 Hz, 2 channels, 16-bit little-endian, interleaved |
| Frame | 10 ms = 480 samples per channel = 1920 bytes of PCM |
| Codec | LC3, 10 ms frames, 160 kbit/s for both channels: 200 bytes per frame, 100 per channel |
| Broadcast | One BIG with 2 BIS: BIS 1 front left, BIS 2 front right |

## Stages

### 1. Receive

`SendspinPlayer._on_audio_chunk()` passes each chunk to `Transmitter.feed()`, which raises
`begin` on the phase and appends to the `FrameBuffer`. Stream end and stream clear for the player
role call `Transmitter.clear()`, which empties the buffer and raises `reset`.

The player advertises a buffer capacity of one second of audio (`BUFFER_BYTES`, 192 000 bytes).
The server never sends more than that ahead, so the `FrameBuffer` cap of the same size only
bounds a misbehaving server; beyond it the oldest audio is dropped, in whole sample frames so the
channels stay aligned.

### 2. Pace

`Transmitter.run()` loops until cancelled:

```python
while True:
    if sink.queued_seconds >= 0.08:  # the controller queue is full enough
        await asyncio.sleep(0.005)  # half a frame
        continue
    frame = self._next_frame()
    if frame is not None:  # PLAYING
        await sink.send_pcm(apply_gain(frame, gain))
    elif phase.idle.is_active:  # IDLE
        await sink.send_silence()
    else:  # BUFFERING
        await asyncio.sleep(0.005)
```

`queued_seconds` is how much audio Bumble's ISO stream holds that the controller has not yet
transmitted. Holding it at about 80 ms (`QUEUE_TARGET_S`) keeps the radio fed while leaving the
rest of the audio in the transmitter's buffer, where an underrun can be told apart from audio
merely waiting its turn.

### 3. Phase rules

Idle
: No stream. A cached frame of encoded silence goes out whenever there is room, so the broadcast
  stays alive between streams.

Buffering
: A stream started, or its audio ran dry. Nothing is sent until the buffer holds `buffer_ms` of
  audio, then `ready` moves to playing. Sending nothing, rather than silence, lets receivers
  conceal the gap; a decoded frame of silence in the middle of music is heard as a click.

Playing
: One frame per opening. If the buffer is empty, `starve` counts an underrun, logs a warning,
  and returns to buffering.

`allow_event_without_transition` is on, so `begin` on every chunk and `reset` on any stream end
are harmless in the wrong state.

### 4. Volume

Volume and mute are read from `PlayerState` for every frame. Sendspin volume is perceived
loudness, mapped to a linear gain of `(volume / 100) ** 1.5`; mute or volume 0 gives zeros, and
full volume passes the bytes through untouched.

### 5. Encode and submit

`AuracastBroadcaster.send_pcm()` encodes each 1920-byte frame with liblc3 into 200 bytes, splits
it into two 100-byte SDUs, and writes one to each BIS's `IsoPacketStream` concurrently. The
silence frame is encoded once at start, by an encoder that has never seen music, and reused.

## Broadcast parameters

Set in `BroadcastConfig` and `AuracastBroadcaster._create_broadcast()`:

| Parameter | Value |
| --- | --- |
| Presentation delay | 40 000 µs |
| Max transport latency | 65 ms |
| Retransmissions (RTN) | 4 |
| SDU interval | 10 000 µs |
| Max SDU | 100 bytes per BIS |
| Extended advertising | non-connectable, SID 0, interval 60 (× 0.625 ms = 37.5 ms) |
| Periodic advertising | interval 60 (× 1.25 ms = 75 ms) |
| ISO stream queue | 64 SDUs per BIS |

The extended advertising data carries the Complete Local Name and Broadcast Name, any
manufacturer data, a Broadcast Audio Announcement with the persistent 24-bit broadcast ID, and a
Public Broadcast Announcement. The periodic advertising carries the BASE: LC3 at 48 kHz, 10 ms,
the octets per frame, and the channel allocation of each BIS.

## End-to-end latency

What a listener hears is roughly `buffer_ms` (250 ms by default) of prebuffer, plus up to 80 ms
in the controller's queue, plus the 40 ms presentation delay, plus the receiver's own decoding.
The player does not yet align playback to Sendspin timestamps, which is why it should not be
grouped with players in the same room.
