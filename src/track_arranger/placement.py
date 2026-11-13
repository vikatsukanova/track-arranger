from track_arranger.desktop_models import Loop, Placement, TimelineSection


def place_loop(sections: list[TimelineSection], loop: Loop):
    matches = {'Drop': {'Drop 1', 'Drop 2'}, 'Intro': {'Intro'}, 'Breakdown': {'Breakdown'}, 'Build': {'Build'}, 'Other': set()}[loop.role]
    return [section.model_copy(update={'clips': [*section.clips, Placement(lane='Loop', loop_id=loop.id)]})
            if section.name in matches and not any(c.lane == 'Loop' for c in section.clips)
            else section.model_copy(deep=True) for section in sections]
