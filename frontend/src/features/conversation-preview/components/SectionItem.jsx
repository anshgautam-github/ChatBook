import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { cn } from "@/lib/utils";
import { truncate } from "@/utils/formatters";

/**
 * One Q&A section: a checkbox plus the (truncated) question and answer.
 * `question`/`answer` can be null — a conversation can end on an
 * unanswered question, or (rarely) open with an assistant message before
 * any user turn — both are rendered with a clear, muted placeholder
 * instead of crashing or silently showing nothing.
 */
export function SectionItem({ section, checked, onToggle }) {
  const checkboxId = `section-${section.id}`;

  return (
    <li>
      <Card
        className={cn(
          "transition-colors",
          checked ? "border-primary/60 bg-primary/5" : "hover:border-foreground/20"
        )}
      >
        <CardContent className="flex items-start gap-3 p-4">
          <Checkbox
            id={checkboxId}
            checked={checked}
            onCheckedChange={onToggle}
            className="mt-1"
          />
          <label htmlFor={checkboxId} className="min-w-0 flex-1 cursor-pointer space-y-1.5">
            <Badge variant="secondary">Section {section.section_index + 1}</Badge>

            <p className="break-words text-sm font-medium leading-snug">
              {section.question ? (
                truncate(section.question.content)
              ) : (
                <span className="italic text-muted-foreground">
                  No question — conversation opener
                </span>
              )}
            </p>

            <p className="break-words text-sm leading-snug text-muted-foreground">
              {section.answer ? (
                truncate(section.answer.content, 160)
              ) : (
                <span className="italic">Awaiting a response</span>
              )}
            </p>
          </label>
        </CardContent>
      </Card>
    </li>
  );
}
