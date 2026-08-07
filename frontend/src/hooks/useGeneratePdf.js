import { useMutation } from "@tanstack/react-query";
import { generatePdf } from "@/services/api/pdfApi";

/** Mutation hook for POST /generate-pdf. Returns a downloadable Blob. */
export function useGeneratePdf() {
  return useMutation({
    mutationFn: (payload) => generatePdf(payload),
  });
}
