import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { UrlInputForm } from "./components/UrlInputForm";
import { useParseConversation } from "@/hooks/useParseConversation";
import { useAppStore } from "@/store/useAppStore";
import { ROUTES } from "@/utils/constants";

/**
 * Home Page — placeholder.
 * Accepts a ChatGPT shared URL and kicks off /parse, then routes to preview.
 */
export function HomePage() {
  const [url, setUrl] = useState("");
  const navigate = useNavigate();
  const setConversation = useAppStore((state) => state.setConversation);
  const { mutate: parse, isPending, error } = useParseConversation();

  function handleSubmit(event) {
    event.preventDefault();
    parse(url, {
      onSuccess: (conversation) => {
        setConversation(conversation);
        navigate(ROUTES.PREVIEW);
      },
    });
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Turn a ChatGPT chat into study notes</h1>
        <p className="text-muted-foreground mt-1">
          Paste a shared conversation link to get started.
        </p>
      </div>
      <UrlInputForm
        url={url}
        onUrlChange={setUrl}
        onSubmit={handleSubmit}
        isSubmitting={isPending}
        errorMessage={error?.message}
      />
    </div>
  );
}
