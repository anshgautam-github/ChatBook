import { Routes, Route, Navigate } from "react-router-dom";
import { HomePage } from "@/features/home/HomePage";
import { ConversationPreviewPage } from "@/features/conversation-preview/ConversationPreviewPage";
import { PdfGenerationPage } from "@/features/pdf-generation/PdfGenerationPage";

/**
 * Central route table. Add new pages here as features are added
 * (saved documents, auth, settings, etc.).
 */
export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/preview" element={<ConversationPreviewPage />} />
      <Route path="/generate" element={<PdfGenerationPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
