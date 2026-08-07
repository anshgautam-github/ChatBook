import { Button } from "@/components/ui/button";

export function UrlInputForm({ url, onUrlChange, onSubmit, isSubmitting, errorMessage }) {
  return (
    <form onSubmit={onSubmit} className="space-y-3">
      <input
        type="url"
        required
        placeholder="https://chatgpt.com/share/..."
        value={url}
        onChange={(event) => onUrlChange(event.target.value)}
        className="w-full rounded-md border border-border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
      />
      {errorMessage && <p className="text-sm text-red-600">{errorMessage}</p>}
      <Button type="submit" disabled={isSubmitting}>
        {isSubmitting ? "Fetching..." : "Generate"}
      </Button>
    </form>
  );
}
