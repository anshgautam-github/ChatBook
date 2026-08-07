import { useEffect, useRef, useState } from "react";
import { GenerationStatus } from "./components/GenerationStatus";
import { Card } from "@/components/ui/card";
import { generatePdf } from "@/services/api/pdfApi";
import { useAppStore } from "@/store/useAppStore";

/**
 * PDF Generation.
 * Shows a loading state while /generate-pdf runs, then an embedded preview
 * of the generated PDF followed by a download button.
 *
 * Deliberately calls `generatePdf` directly with plain async/await + local
 * state, instead of going through `useMutation`. In testing, the mutation's
 * network call and blob parsing completed successfully every time (verified
 * via logging), but `useMutation`'s reactive `data`/`isSuccess` never
 * propagated back to this component afterwards — reproducible in both
 * Safari and Chrome, so not a browser quirk. Rather than chase that down
 * further, this sidesteps it: a plain `useState` + direct async call is a
 * simpler, more predictable pattern for a "fire once on mount" action like
 * this anyway, where nothing else in the app needs to observe or cache the
 * mutation's state.
 */
export function PdfGenerationPage() {
  const conversation = useAppStore((state) => state.conversation);
  const selectedSectionIds = useAppStore((state) => state.selectedSectionIds);
  const [status, setStatus] = useState("idle"); // "idle" | "pending" | "success" | "error"
  const [downloadUrl, setDownloadUrl] = useState(null);
  const [errorMessage, setErrorMessage] = useState(null);
  const hasStarted = useRef(false);

  useEffect(() => {
    if (hasStarted.current || !conversation) return;
    hasStarted.current = true;

    const selectedSections = conversation.sections.filter((section) =>
      selectedSectionIds.includes(section.id)
    );

    setStatus("pending");

    // No cancellation-flag/cleanup pattern here on purpose: the
    // `hasStarted` ref above already guarantees `generatePdf()` is called
    // at most once for this component's lifetime, so there's no stale
    // request to guard against. Adding a `cancelled` flag + cleanup
    // function instead actively breaks this in development — React 18
    // Strict Mode intentionally invokes an effect's cleanup once,
    // immediately, as a test, which would flip `cancelled` to true before
    // this one real request ever resolves, silently discarding a
    // perfectly successful result.
    generatePdf({
      title: conversation.title,
      source_url: conversation.source_url,
      selected_sections: selectedSections,
    })
      .then((blob) => {
        setDownloadUrl(URL.createObjectURL(blob));
        setStatus("success");
      })
      .catch((err) => {
        setErrorMessage(err?.message || "Something went wrong while generating the PDF.");
        setStatus("error");
      });
  }, [conversation, selectedSectionIds]);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Generating your PDF</h1>
      <GenerationStatus
        isPending={status === "pending"}
        isSuccess={status === "success"}
        errorMessage={status === "error" ? errorMessage : null}
      />
      {downloadUrl && (
        <>
          <Card className="overflow-hidden p-0">
            <iframe
              src={downloadUrl}
              title="Generated PDF preview"
              className="h-[80vh] w-full"
            />
          </Card>
          <a
            href={downloadUrl}
            download="study-notes.pdf"
            className="inline-flex items-center justify-center rounded-md px-4 py-2 text-sm font-medium bg-primary text-primary-foreground hover:opacity-90"
          >
            Download PDF
          </a>
        </>
      )}
    </div>
  );
}
