import { apiRequest } from "./client";

/** @param {import("@/types/pdf").GeneratePdfRequest} payload @returns {Promise<Blob>} */
export async function generatePdf(payload) {
  const response = await apiRequest("/generate-pdf", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return response.blob();
}
