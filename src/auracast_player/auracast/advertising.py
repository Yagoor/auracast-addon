"""The advertising data that announces an Auracast broadcast."""

from __future__ import annotations

from bumble import hci
from bumble.core import AdvertisingData
from bumble.profiles import bap, le_audio, pbp


def build_advertising_data(
    name: str, broadcast_id: int, manufacturer_data: dict[int, bytes] | None
) -> bytes:
    """
    Build the extended advertising data: the name, any manufacturer data and the announcements.

    :param name: The broadcast name.
    :param broadcast_id: The 24-bit broadcast ID.
    :param manufacturer_data: Payloads to advertise, keyed by company ID.
    """
    name_bytes = name.encode()
    structures = [
        (AdvertisingData.COMPLETE_LOCAL_NAME, name_bytes),
        (AdvertisingData.BROADCAST_NAME, name_bytes),
    ]
    structures.extend(
        (AdvertisingData.MANUFACTURER_SPECIFIC_DATA, company_id.to_bytes(2, "little") + payload)
        for company_id, payload in (manufacturer_data or {}).items()
    )
    announcement = bap.BroadcastAudioAnnouncement(broadcast_id=broadcast_id)
    public_announcement = pbp.PublicBroadcastAnnouncement(
        features=pbp.PublicBroadcastAnnouncement.Features(0),
        metadata=le_audio.Metadata(entries=[]),
    )
    return (
        bytes(AdvertisingData(structures))
        + announcement.get_advertising_data()
        + public_announcement.get_advertising_data()
    )


def build_periodic_data(presentation_delay_us: int, octets_per_frame: int, channels: int) -> bytes:
    """
    Build the periodic advertising data: the LC3 codec setup and which channel each BIS carries.

    :param presentation_delay_us: The presentation delay receivers apply.
    :param octets_per_frame: The size of one LC3 frame for one channel.
    :param channels: The number of BIS, one per channel, left then right.
    """
    locations = [bap.AudioLocation.FRONT_LEFT, bap.AudioLocation.FRONT_RIGHT]
    return bap.BasicAudioAnnouncement(
        presentation_delay=presentation_delay_us,
        subgroups=[
            bap.BasicAudioAnnouncement.Subgroup(
                codec_id=hci.CodingFormat(codec_id=hci.CodecID.LC3),
                codec_specific_configuration=bap.CodecSpecificConfiguration(
                    sampling_frequency=bap.SamplingFrequency.FREQ_48000,
                    frame_duration=bap.FrameDuration.DURATION_10000_US,
                    octets_per_codec_frame=octets_per_frame,
                ),
                metadata=le_audio.Metadata(entries=[]),
                bis=[
                    bap.BasicAudioAnnouncement.BIS(
                        index=index + 1,
                        codec_specific_configuration=bap.CodecSpecificConfiguration(
                            audio_channel_allocation=locations[index]
                        ),
                    )
                    for index in range(channels)
                ],
            )
        ],
    ).get_advertising_data()
