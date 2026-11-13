"""Live 11 XML defaults for audio-only arrangement sets."""
from track_arranger.desktop_export import node


def values(parent, mapping):
    for tag, value in mapping.items():
        node(parent, tag, value)


def parameter(parent, name, value, target_id):
    p = node(parent, name)
    node(p, 'LomId', 0)
    node(p, 'Manual', value)
    node(node(p, 'AutomationTarget', Id=target_id), 'LockEnvelope', 0)
    node(node(p, 'ModulationTarget', Id=target_id + 1), 'LockEnvelope', 0)
    return p


def device_defaults(parent, target_id):
    values(parent, {'LomId': 0, 'LomIdView': 0, 'IsExpanded': 'true'})
    parameter(parent, 'On', 'true', target_id)
    node(parent, 'ParametersListWrapper', LomId=0)
    values(parent, {'LastSelectedTimeableIndex': 0, 'LastSelectedClipEnvelopeIndex': 0})
    node(node(parent, 'LastPresetRef'), 'Value')
    node(parent, 'LockedScripts')
    values(parent, {'IsFolded': 'false', 'ShouldShowPresetName': 'true', 'UserName': '', 'Annotation': ''})
    node(parent, 'SourceContext')


def track_defaults(track, name, index):
    values(track, {'LomId': 0, 'LomIdView': 0, 'IsContentSelected': 'false', 'EnvelopeModePreferred': 'false'})
    values(node(track, 'TrackDelay'), {'Value': 0, 'IsValueSampleBased': 'false'})
    values(node(track, 'Name'), {'EffectiveName': name, 'UserName': name, 'Annotation': '', 'MemorizedFirstClipName': ''})
    values(track, {'Color': index % 70})
    node(node(track, 'AutomationEnvelopes'), 'Envelopes')
    values(track, {'TrackGroupId': -1, 'TrackUnfolded': 'true'})
    node(track, 'DevicesListWrapper', LomId=0)
    node(track, 'ClipSlotsListWrapper', LomId=0)
    values(track, {'ViewData': '{}', 'SavedPlayingSlot': -1, 'SavedPlayingOffset': 0, 'Freeze': 'false',
                   'VelocityDetail': 0, 'NeedArrangerRefreeze': 'true'})
    node(track, 'PostProcessFreezeClips')


def mixer_defaults(chain, index, master=False):
    lanes = node(chain, 'AutomationLanes')
    lane = node(node(lanes, 'AutomationLanes'), 'AutomationLane', Id=0)
    values(lane, {'SelectedDevice': 0, 'SelectedEnvelope': 0, 'IsContentSelected': 'false', 'LaneHeight': 68})
    node(lanes, 'AreAdditionalAutomationLanesFolded', 'true')
    values(node(chain, 'ClipEnvelopeChooserViewState'), {'SelectedDevice': 0, 'SelectedEnvelope': 0})
    mixer = node(chain, 'Mixer')
    base = 1000 + index * 100
    device_defaults(mixer, base)
    node(mixer, 'Sends')
    parameter(mixer, 'Speaker', 'true', base + 2)
    values(mixer, {'SoloSink': 'false', 'PanMode': 0})
    for offset, name, value in [(4, 'Pan', 0), (6, 'SplitStereoPanL', -1), (8, 'SplitStereoPanR', 1), (10, 'Volume', 1)]:
        parameter(mixer, name, value, base + offset)
    values(mixer, {'ViewStateSesstionTrackWidth': 93, 'CrossFadeState': 1})
    node(mixer, 'SendsListWrapper', LomId=0)
    if master:
        parameter(mixer, 'Tempo', 174, base + 12)
        parameter(mixer, 'TimeSignature', 201, base + 14)
        parameter(mixer, 'GlobalGrooveAmount', 100, base + 16)
        parameter(mixer, 'CrossFade', 0, base + 18)
    return mixer


def routing(chain, name, target, upper, lower=''):
    values(node(chain, name), {'Target': target, 'UpperDisplayString': upper, 'LowerDisplayString': lower})


def sequencer(chain, index):
    seq = node(chain, 'MainSequencer')
    device_defaults(seq, 1000 + index * 100 + 20)
    node(seq, 'ClipSlotList')
    node(seq, 'MonitoringEnum', 2)
    auto = node(node(seq, 'Sample'), 'ArrangerAutomation')
    events = node(auto, 'Events')
    node(auto, 'AutomationTransformViewState')
    for offset, name in enumerate(['VolumeModulationTarget', 'TranspositionModulationTarget', 'GrainSizeModulationTarget',
                                   'FluxModulationTarget', 'SampleOffsetModulationTarget']):
        node(seq, name, Id=1000 + index * 100 + 30 + offset)
    values(seq, {'PitchViewScrollPosition': -1073741824, 'SampleOffsetModulationScrollPosition': -1073741824})
    values(node(seq, 'Recorder'), {'IsArmed': 'false', 'TakeCounter': 0})
    return events


def clip_defaults(clip, duration, seconds):
    values(clip, {'LomId': 0, 'LomIdView': 0})
    markers = node(clip, 'WarpMarkers')
    node(markers, 'WarpMarker', Id=0, SecTime=0, BeatTime=0)
    node(markers, 'WarpMarker', Id=1, SecTime=seconds, BeatTime=duration)
    ts = node(node(node(clip, 'TimeSignature'), 'TimeSignatures'), 'RemoteableTimeSignature', Id=0)
    values(ts, {'Numerator': 4, 'Denominator': 4, 'Time': 0})
    node(node(clip, 'Envelopes'), 'Envelopes')
    values(node(clip, 'ScrollerTimePreserver'), {'LeftTime': 0, 'RightTime': duration})
    values(node(clip, 'TimeSelection'), {'AnchorTime': 0, 'OtherTime': 0})
    values(clip, {'Annotation': '', 'LaunchMode': 0, 'LaunchQuantisation': 0, 'Legato': 'false', 'Ram': 'false',
                  'VelocityAmount': 0, 'FollowTime': 4, 'FollowActionA': 0, 'FollowActionB': 0,
                  'FollowChanceA': 1, 'FollowChanceB': 0, 'FreezeStart': 0, 'FreezeEnd': 0,
                  'WarpMode': 0, 'HiQ': 'true', 'Fade': 'false', 'MarkerDensity': 2,
                  'AutoWarpTolerance': 4, 'MarkersGenerated': 'true', 'IsSongTempoMaster': 'false'})
    node(node(clip, 'GrooveSettings'), 'GrooveId', -1)
    values(node(clip, 'Grid'), {'FixedNumerator': 1, 'FixedDenominator': 16, 'GridIntervalPixel': 20,
                              'Ntoles': 2, 'SnapToGrid': 'true', 'Fixed': 'true'})
    onsets = node(clip, 'Onsets')
    node(onsets, 'UserOnsets')
    node(onsets, 'HasUserOnsets', 'false')
    node(clip, 'SavedWarpMarkersForStretched')


def live_defaults(live, total_beats):
    values(live, {'LomId': 0, 'LomIdView': 0, 'GlobalQuantisation': 4, 'AutoQuantisation': 0})
    values(node(live, 'Transport'), {'PhaseNudgeTempo': 10, 'LoopOn': 'false', 'LoopStart': 0,
                                   'LoopLength': total_beats, 'LoopIsSongStart': 'true',
                                   'CurrentTime': 0, 'PunchIn': 'false', 'PunchOut': 'false', 'DrawMode': 'false'})
    values(node(live, 'SongMasterValues'), {'SessionScrollerPos': 0})
    node(live, 'SendsPre')
    node(live, 'Scenes')
    node(node(live, 'GroovePool'), 'Grooves')
    values(live, {'Annotation': '', 'SoloOrPflSavedValue': 'false', 'SoloInPlace': 'true',
                  'CrossfadeCurve': 2, 'LatencyCompensation': 2, 'HighlightedTrackIndex': 0,
                  'AutomationMode': 'true', 'SnapAutomationToGrid': 'true', 'ArrangementOverdub': 'false',
                  'ViewData': '{}', 'MidiFoldIn': 'false', 'MidiPrelisten': 'false',
                  'TrackHeaderWidth': 120, 'ViewStateArrangerHasDetail': 'true', 'ViewStateSessionHasDetail': 'true',
                  'ViewStateDetailIsSample': 'false'})
    for name in ['TracksListWrapper', 'VisibleTracksListWrapper', 'ReturnTracksListWrapper', 'ScenesListWrapper', 'CuePointsListWrapper']:
        node(live, name, LomId=0)
