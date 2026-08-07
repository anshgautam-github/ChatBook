import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { SectionList } from "./components/SectionList";
import { useAppStore } from "@/store/useAppStore";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ROUTES } from "@/utils/constants";

/**
 * Conversation Preview.
 *
 * Consumes the parsed conversation already sitting in the Zustand store
 * (populated by the Home page's call to POST /parse) and lets the user
 * pick which Q&A sections to carry forward. No PDF generation happens
 * here — "Continue" just moves to the (placeholder) generation step.
 */
export function ConversationPreviewPage() {
  const navigate = useNavigate();
  const conversation = useAppStore((state) => state.conversation);
  const selectedSectionIds = useAppStore((state) => state.selectedSectionIds);
  const toggleSection = useAppStore((state) => state.toggleSection);
  const selectAll = useAppStore((state) => state.selectAll);
  const clearSelection = useAppStore((state) => state.clearSelection);

  const sections = conversation?.sections ?? [];
  const totalCount = sections.length;
  const selectedCount = selectedSectionIds.length;

  const allSelected = useMemo(
    () => totalCount > 0 && selectedCount === totalCount,
    [totalCount, selectedCount]
  );

  if (!conversation) {
    return (
      <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed border-border py-16 text-center">
        <p className="text-muted-foreground">No conversation loaded yet.</p>
        <Button variant="outline" size="sm" onClick={() => navigate(ROUTES.HOME)}>
          Back to home
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h1 className="break-words text-2xl font-semibold tracking-tight">
          {conversation.title}
        </h1>
        <p className="text-sm text-muted-foreground">
          {totalCount === 0
            ? "No question-answer sections were found in this conversation."
            : `${totalCount} ${totalCount === 1 ? "section" : "sections"} extracted — choose what to include.`}
        </p>
      </div>

      {totalCount > 0 && (
        <>
          <div className="flex flex-col gap-3 rounded-lg border border-border bg-muted/40 p-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex flex-wrap gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => selectAll(sections.map((section) => section.id))}
                disabled={allSelected}
              >
                Select all
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={clearSelection}
                disabled={selectedCount === 0}
              >
                Deselect all
              </Button>
            </div>

            <Badge variant="secondary" className="w-fit">
              {selectedCount} of {totalCount} selected
            </Badge>
          </div>

          <SectionList
            sections={sections}
            selectedSectionIds={selectedSectionIds}
            onToggle={toggleSection}
          />
        </>
      )}

      <Button
        className="w-full sm:w-auto"
        disabled={selectedCount === 0}
        onClick={() => navigate(ROUTES.GENERATE)}
      >
        Continue with {selectedCount} {selectedCount === 1 ? "section" : "sections"}
      </Button>
    </div>
  );
}
