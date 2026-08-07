export function GenerationStatus({ isPending, isSuccess, errorMessage }) {
  if (errorMessage) {
    return <p className="text-sm text-red-600">Failed to generate PDF: {errorMessage}</p>;
  }
  if (isPending) {
    return <p className="text-sm text-muted-foreground">Rendering your study notes...</p>;
  }
  if (isSuccess) {
    return <p className="text-sm text-green-600">Your PDF is ready.</p>;
  }
  return null;
}
