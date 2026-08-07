import { create } from "zustand";

/**
 * Global client state, introduced only where React Query + local state
 * aren't enough (e.g. cross-page selection state). Currently minimal —
 * expand as features like multi-chat merging need shared state.
 */
export const useAppStore = create((set) => ({
  conversation: null,
  selectedSectionIds: [],
  setConversation: (conversation) =>
    set({ conversation, selectedSectionIds: [] }),
  toggleSection: (sectionId) =>
    set((state) => ({
      selectedSectionIds: state.selectedSectionIds.includes(sectionId)
        ? state.selectedSectionIds.filter((id) => id !== sectionId)
        : [...state.selectedSectionIds, sectionId],
    })),
  selectAll: (sectionIds) => set({ selectedSectionIds: sectionIds }),
  clearSelection: () => set({ selectedSectionIds: [] }),
}));
