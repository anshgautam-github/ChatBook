import { apiRequest } from "./client";

/** @param {string} url @returns {Promise<import("@/types/conversation").ParseConversationResponse>} */
export async function parseConversation(url) {
  const response = await apiRequest("/parse", {
    method: "POST",
    body: JSON.stringify({ url }),
  });
  return response.json();
}
