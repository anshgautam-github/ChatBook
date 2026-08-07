import { SectionItem } from "./SectionItem";

export function SectionList({ sections, selectedSectionIds, onToggle }) {
  return (
    <ul className="space-y-3" role="list">
      {sections.map((section) => (
        <SectionItem
          key={section.id}
          section={section}
          checked={selectedSectionIds.includes(section.id)}
          onToggle={() => onToggle(section.id)}
        />
      ))}
    </ul>
  );
}
