import { useMutation } from "@tanstack/react-query";
import { parseConversation } from "@/services/api/conversationApi";

/** Mutation hook for POST /parse. */
export function useParseConversation() {
  return useMutation({
    mutationFn: (url) => parseConversation(url),
  });
}
