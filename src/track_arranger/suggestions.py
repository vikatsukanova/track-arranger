from track_arranger.arrangement import TEMPLATES
from track_arranger.desktop_models import Project
from track_arranger.tips import TIPS


def suggestions(project: Project, section_id: str) -> list[dict]:
    section = next((s for s in project.sections if s.id == section_id), None)
    if section is None:
        raise ValueError('Section not found')
    tips = TIPS[project.genre].get(section.name, ('Try removing one layer for contrast.',))
    result = [dict(kind='tip', text=tip) for tip in tips]
    if section.bars < 256 and sum(s.bars for s in project.sections) <= 2040:
        result.append(dict(kind='length', bars=section.bars + 8,
                           text=f'Try eight more bars of {section.name} to give the idea room.'))
    template = list(TEMPLATES[project.genre])
    names = [name for name, _ in template]
    if section.name in names and names.index(section.name) + 1 < len(names) and len(project.sections) < 64:
        name, bars = template[names.index(section.name) + 1]
        result.append(dict(kind='next', name=name, bars=bars,
                           text=f'Try {name} next ({bars} bars). Insert an empty section after this one.'))
    return result
